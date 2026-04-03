"""
Админ-панель для управления возвратами средств
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from datetime import datetime

from app.database.session import async_session
from app.database.unit_of_work import UnitOfWork
from app.database.managers import PaymentManager, BookingManager
from app.database.repositories import RefundRepository, BookingRepository, UserRepository
from app.database.models import RefundStatus, PaymentStatus
from app.utils.logging_config import get_logger
from app.admin_panel.keyboards_adm import (
    back_to_admin_menu, finances_submenu, refunds_list_keyboard,
    refund_detail_actions, refunds_admin_menu, admin_mark_booking_refunded_menu,
    admin_mark_refund_successful_menu
)
from app.admin_panel.states_adm import RefundActions
from app.services.scheduler.bot_instance import get_bot_instance

router = Router(name="admin_refunds")
logger = get_logger(__name__)


@router.callback_query(F.data == "admin_refunds_menu")
async def refunds_menu(callback: CallbackQuery):
    """Меню управления возвратами"""
    await callback.answer()

    text = (
        "Управление возвратами\n\n"
        "Здесь можно просмотреть и обработать возвраты, "
        "которые не удалось выполнить автоматически, "
        "а также выполнить возврат по любому оплаченному бронированию."
    )

    await callback.message.edit_text(text, reply_markup=refunds_admin_menu())


@router.callback_query(F.data == "admin_failed_refunds")
async def failed_refunds_list(callback: CallbackQuery):
    """Список неудачных возвратов"""
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        # Получаем возвраты в статусах FAILED, PROCESSING, PENDING (неуспешные)
        failed_refunds = await refund_repo.get_refunds_by_statuses(
            [RefundStatus.FAILED, RefundStatus.PROCESSING, RefundStatus.PENDING],
            limit=20
        )

        if not failed_refunds:
            await callback.message.edit_text(
                "Нет активных или неудачных возвратов.",
                reply_markup=back_to_admin_menu("admin_refunds_menu")
            )
            return

        text = "Возвраты, требующие внимания:\n\n"

        for refund in failed_refunds:
            text += (
                f"ID возврата: {refund.id}\n"
                f"Бронирование: #{refund.booking_id}\n"
                f"Сумма: {refund.amount} руб.\n"
                f"Статус: {refund.status.value}\n"
                f"Причина: {refund.reason or 'не указана'}\n"
                f"Попыток: {refund.retry_count}\n"
                f"---\n"
            )

        await callback.message.edit_text(
            text,
            reply_markup=refunds_list_keyboard(failed_refunds)
        )


@router.callback_query(F.data == "admin_refund_by_booking")
async def refund_by_booking_start(callback: CallbackQuery, state: FSMContext):
    """Начать возврат по ID бронирования"""
    await callback.answer()
    await callback.message.edit_text(
        "Введите ID бронирования для возврата средств:\n\n"
        "ID можно найти в деталях бронирования.\n\n"
        "Для отмены введите /cancel",
        reply_markup=back_to_admin_menu("admin_refunds_menu")
    )
    await state.set_state(RefundActions.waiting_for_booking_id)


@router.message(RefundActions.waiting_for_booking_id)
async def process_booking_id(message: Message, state: FSMContext):
    """Получен ID бронирования для возврата"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=finances_submenu())
        return

    try:
        booking_id = int(message.text.strip())

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking:
                await message.answer(
                    "Бронирование не найдено. Проверьте ID и попробуйте снова.\n"
                    "Для отмены введите /cancel"
                )
                return

            if booking.payment_status != PaymentStatus.paid:
                await message.answer(
                    f"Бронирование #{booking_id} не оплачено.\n"
                    f"Текущий статус: {booking.payment_status.value}\n\n"
                    "Возврат возможен только для оплаченных бронирований.\n"
                    "Для отмены введите /cancel"
                )
                return

            # Сохраняем данные в состоянии
            await state.update_data(booking_id=booking_id)

            payment_manager = PaymentManager(session)
            refund_amount_kopecks = await payment_manager.calculate_refund_amount(booking)
            refund_amount_rub = refund_amount_kopecks // 100

            await message.answer(
                f"Бронирование #{booking_id}\n"
                f"Сумма к возврату: {refund_amount_rub} руб.\n\n"
                f"Введите сумму возврата в рублях (целое число) или 'все' для полного возврата:\n"
                f"Для отмены введите /cancel"
            )
            await state.set_state(RefundActions.waiting_for_amount)

    except ValueError:
        await message.answer("Пожалуйста, введите число (ID бронирования). Для отмены введите /cancel")
    except Exception as e:
        logger.error(f"Ошибка при обработке ID бронирования: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(RefundActions.waiting_for_amount)
async def process_refund_amount(message: Message, state: FSMContext):
    """Получена сумма для возврата"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=finances_submenu())
        return

    try:
        data = await state.get_data()
        booking_id = data.get("booking_id")

        text = message.text.strip().lower()

        if text == "все":
            amount_kopecks = None
        else:
            amount_rub = int(text)
            if amount_rub <= 0:
                await message.answer("Сумма должна быть положительным числом. Попробуйте снова.")
                return
            amount_kopecks = amount_rub * 100

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                payment_manager = PaymentManager(session)
                booking_manager = BookingManager(session)

                booking = await booking_manager.booking_repo.get_by_id(booking_id)

                if not booking:
                    await message.answer("Бронирование не найдено")
                    await state.clear()
                    return

                await message.answer("Выполняется возврат через ЮKassa...")

                # Пытаемся вернуть через ЮKassa
                success, result_msg, refund_data = await booking_manager.cancel_booking(
                    booking_id=booking_id,
                    auto_refund=True,
                    reason=f"Возврат администратором {message.from_user.id}",
                    force_refund=True
                )

                if success:
                    refund_amount = refund_data.get('amount', 0) if refund_data else 0
                    response_text = (
                        f"Возврат выполнен успешно через ЮKassa!\n\n"
                        f"Бронирование #{booking_id}\n"
                        f"Сумма возврата: {refund_amount} руб.\n"
                        f"{result_msg}"
                    )
                    await message.answer(response_text, reply_markup=finances_submenu())

                    # Уведомляем пользователя
                    user_repo = UserRepository(session)
                    user = await user_repo.get_by_id(booking.adult_user_id)

                    if user and user.telegram_id:
                        bot = get_bot_instance()
                        if bot:
                            await bot.send_message(
                                user.telegram_id,
                                f"Администратор оформил возврат средств за бронирование #{booking_id} через ЮKassa.\n"
                                f"Сумма: {refund_amount} руб.\n"
                                f"Деньги поступят на карту в течение 5-10 рабочих дней."
                            )
                else:
                    # Если через ЮKassa не получилось, предлагаем отметить возврат вручную
                    await message.answer(
                        f"Не удалось выполнить возврат через ЮKassa:\n{result_msg}\n\n"
                        f"Если вы уже вернули деньги клиенту вручную (наличными, переводом на карту и т.д.), "
                        f"вы можете отметить возврат как успешный в системе.\n\n"
                        f"Отметить возврат как успешный?",
                        reply_markup=admin_mark_booking_refunded_menu(booking_id)
                    )

        await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введите число (сумму в рублях) или 'все'")
    except Exception as e:
        logger.error(f"Ошибка при возврате: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("admin_mark_booking_refunded:"))
async def mark_booking_refunded(callback: CallbackQuery):
    """
    Отметить бронирование как возвращенное (ручной возврат)
    Администратор вернул деньги вручную, нужно обновить статусы в системе
    """
    booking_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_repo = BookingRepository(session)
                refund_repo = RefundRepository(session)
                payment_manager = PaymentManager(session)

                booking = await booking_repo.get_by_id(booking_id)

                if not booking:
                    await callback.message.edit_text("Бронирование не найдено.")
                    return

                if booking.payment_status != PaymentStatus.paid:
                    await callback.message.edit_text(
                        f"Бронирование #{booking_id} не оплачено. "
                        f"Текущий статус: {booking.payment_status.value}"
                    )
                    return

                # Получаем все возвраты по этому бронированию
                refunds = await refund_repo.get_refunds_by_booking(booking_id)

                updated_count = 0
                for refund in refunds:
                    if refund.status != RefundStatus.SUCCEEDED:
                        refund.status = RefundStatus.SUCCEEDED
                        refund.completed_at = datetime.now()
                        refund.retry_count = 0
                        updated_count += 1

                # Обновляем статус бронирования
                await booking_repo.update(
                    booking_id,
                    payment_status=PaymentStatus.refunded
                )

                await session.flush()

                response_text = (
                    f"Бронирование #{booking_id} отмечено как возвращенное.\n\n"
                    f"Обновлено возвратов: {updated_count}\n"
                    f"Статус бронирования: {PaymentStatus.refunded.value}\n\n"
                    f"Система больше не будет пытаться обработать эти возвраты автоматически."
                )

                await callback.message.edit_text(response_text, reply_markup=finances_submenu())

                # Уведомляем пользователя (опционально)
                if booking.adult_user.telegram_id:
                    bot = callback.bot
                    if bot:
                        await bot.send_message(
                            booking.adult_user.telegram_id,
                            f"Администратор подтвердил возврат средств за бронирование #{booking_id}.\n"
                            f"Если у вас есть вопросы, свяжитесь с администратором."
                        )

                logger.info(f"Администратор {callback.from_user.id} отметил бронирование #{booking_id} как возвращенное вручную")

    except Exception as e:
        logger.error(f"Ошибка при отметке бронирования как возвращенного: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("admin_retry_refund:"))
async def retry_refund(callback: CallbackQuery):
    """Повторить попытку возврата"""
    refund_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            refund_repo = RefundRepository(session)
            refund = await refund_repo.get_refund_by_id(refund_id)

            if not refund:
                await callback.message.answer("Возврат не найден")
                return

            if refund.status == RefundStatus.SUCCEEDED:
                await callback.message.answer("Этот возврат уже успешно выполнен")
                return

            payment_manager = PaymentManager(session)
            payment = await payment_manager.payment_repo.get_payment_by_id(refund.payment_id)

            if not payment or not payment.yookassa_payment_id:
                await callback.message.answer("Не найден платеж или его ID в YooKassa")
                return

            # Сбрасываем счетчик попыток
            refund.retry_count = 0
            await session.flush()

            amount_kopecks = refund.amount * 100

            await callback.message.edit_text("Повторная попытка выполнения возврата...")

            success, message = await payment_manager._execute_refund_with_retry(
                refund=refund,
                payment=payment,
                amount=amount_kopecks,
                max_retries=1
            )

            if success:
                await callback.message.edit_text(
                    f"Возврат #{refund_id} успешно выполнен!\n\n{message}",
                    reply_markup=back_to_admin_menu("admin_refunds_menu")
                )
            else:
                await callback.message.edit_text(
                    f"Не удалось выполнить возврат #{refund_id}:\n{message}\n\n"
                    f"Вы можете отметить возврат как успешный вручную, если уже вернули деньги клиенту.",
                    reply_markup=admin_mark_refund_successful_menu(refund_id, refund.booking_id)
                )


@router.callback_query(F.data.startswith("admin_mark_refund_successful:"))
async def mark_refund_successful(callback: CallbackQuery):
    """
    Отметить конкретный возврат как успешный (ручной возврат)
    """
    parts = callback.data.split(":")
    refund_id = int(parts[1])
    booking_id = int(parts[2])
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                refund_repo = RefundRepository(session)
                booking_repo = BookingRepository(session)

                refund = await refund_repo.get_refund_by_id(refund_id)

                if not refund:
                    await callback.message.edit_text("Возврат не найден.")
                    return

                refund.status = RefundStatus.SUCCEEDED
                refund.completed_at = datetime.now()
                refund.retry_count = 0
                await session.flush()

                # Проверяем, все ли возвраты по бронированию успешны
                all_refunds = await refund_repo.get_refunds_by_booking(booking_id)
                all_successful = all(r.status == RefundStatus.SUCCEEDED for r in all_refunds)

                if all_successful:
                    await booking_repo.update(
                        booking_id,
                        payment_status=PaymentStatus.refunded
                    )

                await callback.message.edit_text(
                    f"Возврат #{refund_id} отмечен как успешный.\n\n"
                    f"Статус бронирования #{booking_id}: {PaymentStatus.refunded.value if all_successful else 'частично возвращен'}",
                    reply_markup=back_to_admin_menu("admin_refunds_menu")
                )

                logger.info(f"Администратор {callback.from_user.id} отметил возврат #{refund_id} как успешный вручную")

    except Exception as e:
        logger.error(f"Ошибка при отметке возврата как успешного: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("admin_refund_detail:"))
async def refund_detail(callback: CallbackQuery):
    """Детальная информация о возврате"""
    refund_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        refund = await refund_repo.get_refund_by_id(refund_id)

        if not refund:
            await callback.message.answer("Возврат не найден")
            return

        text = (
            f"Детали возврата #{refund.id}\n\n"
            f"Бронирование: #{refund.booking_id}\n"
            f"Платеж: #{refund.payment_id}\n"
            f"Сумма: {refund.amount} руб.\n"
            f"Статус: {refund.status.value}\n"
            f"Причина: {refund.reason or 'не указана'}\n"
            f"Попыток: {refund.retry_count}\n"
            f"Создан: {refund.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

        if refund.completed_at:
            text += f"Завершен: {refund.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

        if refund.yookassa_refund_id:
            text += f"ID в YooKassa: {refund.yookassa_refund_id}\n"

        if refund.cancellation_details_reason:
            text += f"Причина отмены: {refund.cancellation_details_reason}\n"

        await callback.message.edit_text(text, reply_markup=refund_detail_actions(refund.id, refund.booking_id))


@router.callback_query(F.data.startswith("admin_mark_refund_failed:"))
async def mark_refund_failed(callback: CallbackQuery):
    """Отметить возврат как требующий ручного вмешательства"""
    refund_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        refund = await refund_repo.get_refund_by_id(refund_id)

        if not refund:
            await callback.message.answer("Возврат не найден")
            return

        refund.status = RefundStatus.FAILED
        refund.retry_count = 999
        await session.flush()

        await callback.message.edit_text(
            f"Возврат #{refund_id} отмечен как требующий ручного вмешательства.\n\n"
            f"Вы можете:\n"
            f"- Выполнить возврат через ЮKassa вручную\n"
            f"- Вернуть деньги клиенту наличными/переводом и отметить возврат как успешный",
            reply_markup=admin_mark_refund_successful_menu(refund_id, refund.booking_id)
        )
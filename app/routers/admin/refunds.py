"""
Админ-панель для управления возвратами средств
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.database.session import async_session
from app.database.managers import PaymentManager
from app.database.repositories import RefundRepository, BookingRepository, UserRepository
from app.database.models import RefundStatus, PaymentStatus
from app.utils.logging_config import get_logger
from app.admin_panel.keyboards_adm import (
    back_to_admin_menu, finances_submenu, refunds_list_keyboard
)
from app.admin_panel.states_adm import RefundActions
from app.services.scheduler.bot_instance import get_bot_instance

router = Router(name="admin_refunds")
logger = get_logger(__name__)




async def show_refunds_menu(target, is_callback: bool = True):
    """
    Показать меню возвратов.

    Args:
        target: Message или CallbackQuery
        is_callback: True если target это CallbackQuery, False если Message
    """
    text = (
        "Управление возвратами\n\n"
        "Здесь можно просмотреть и обработать возвраты, "
        "которые не удалось выполнить автоматически."
    )

    from app.admin_panel.keyboards_adm import refunds_admin_menu

    if is_callback:
        await target.message.edit_text(text, reply_markup=refunds_admin_menu())
    else:
        await target.answer(text, reply_markup=refunds_admin_menu())

@router.callback_query(F.data == "admin_refunds_menu")
async def refunds_menu(callback: CallbackQuery):
    """Меню управления возвратами"""
    await callback.answer()

    text = (
        "Управление возвратами\n\n"
        "Здесь можно просмотреть и обработать возвраты, "
        "которые не удалось выполнить автоматически."
    )

    from app.admin_panel.keyboards_adm import refunds_admin_menu
    await callback.message.edit_text(text, reply_markup=refunds_admin_menu())


@router.callback_query(F.data == "admin_failed_refunds")
async def failed_refunds_list(callback: CallbackQuery):
    """Список неудачных возвратов"""
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        failed_refunds = await refund_repo.get_failed_refunds(limit=10)

        if not failed_refunds:
            await callback.message.edit_text(
                "Нет неудачных возвратов.",
                reply_markup=back_to_admin_menu("admin_refunds_menu")
            )
            return

        text = "Неудачные возвраты (требуют внимания):\n\n"

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


@router.callback_query(F.data.startswith("admin_retry_refund:"))
async def retry_refund(callback: CallbackQuery):
    """Повторить попытку возврата"""
    refund_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        refund = await refund_repo.get_refund_by_id(refund_id)

        if not refund:
            await callback.message.answer("Возврат не найден")
            return

        if refund.status == RefundStatus.SUCCEEDED:
            await callback.message.answer("Этот возврат уже успешно выполнен")
            return

        # Получаем платеж
        payment_manager = PaymentManager(session)
        payment = await payment_manager.payment_repo.get_payment_by_id(refund.payment_id)

        if not payment or not payment.yookassa_payment_id:
            await callback.message.answer("Не найден платеж или его ID в YooKassa")
            return

        # Сбрасываем счетчик попыток
        refund.retry_count = 0
        await session.flush()

        # Конвертируем сумму в копейки
        amount_kopecks = refund.amount * 100

        # Пытаемся выполнить возврат
        success, message = await payment_manager._execute_refund_with_retry(
            refund=refund,
            payment=payment,
            amount=amount_kopecks,
            max_retries=1
        )

        if success:
            await callback.message.answer(
                f"Возврат #{refund_id} успешно выполнен!\n\n{message}",
                reply_markup=back_to_admin_menu("admin_refunds_menu")
            )
        else:
            await callback.message.answer(
                f"Не удалось выполнить возврат #{refund_id}:\n{message}",
                reply_markup=back_to_admin_menu("admin_refunds_menu")
            )


@router.callback_query(F.data == "admin_manual_refund")
async def manual_refund_start(callback: CallbackQuery, state: FSMContext):
    """Начать ручной возврат (ввод ID бронирования)"""
    await callback.answer()
    await callback.message.edit_text(
        "Введите ID бронирования, для которого нужно вернуть средства:\n\n"
        "ID можно найти в деталях бронирования или в списке неудачных возвратов.\n\n"
        "Для отмены введите /cancel",
        reply_markup=back_to_admin_menu("admin_refunds_menu")
    )
    await state.set_state(RefundActions.waiting_for_refund_id)


@router.message(RefundActions.waiting_for_refund_id)
async def manual_refund_booking_id(message: Message, state: FSMContext):
    """Получен ID бронирования для ручного возврата"""
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
                await message.answer("Бронирование не найдено. Попробуйте еще раз или введите /cancel.")
                return

            if booking.payment_status != PaymentStatus.paid:
                await message.answer(
                    f"Бронирование #{booking_id} не оплачено. "
                    f"Текущий статус: {booking.payment_status.value}"
                )
                return

            # Сохраняем booking_id в состоянии
            await state.update_data(booking_id=booking_id)

            # Получаем сумму для возврата
            payment_manager = PaymentManager(session)
            refund_amount_kopecks = await payment_manager.calculate_refund_amount(booking)
            refund_amount_rub = refund_amount_kopecks // 100

            await message.answer(
                f"Бронирование #{booking_id}\n"
                f"Сумма к возврату: {refund_amount_rub} руб.\n\n"
                f"Введите сумму возврата в рублях (целое число) или 'все' для полного возврата:\n"
                f"Для отмены введите /cancel"
            )
            await state.set_state(RefundActions.waiting_for_manual_refund_amount)

    except ValueError:
        await message.answer("Пожалуйста, введите число (ID бронирования)")
    except Exception as e:
        logger.error(f"Ошибка при ручном возврате: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(RefundActions.waiting_for_manual_refund_amount)
async def manual_refund_amount(message: Message, state: FSMContext):
    """Получена сумма для ручного возврата"""
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
            amount_kopecks = amount_rub * 100

        async with async_session() as session:
            payment_manager = PaymentManager(session)

            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking:
                await message.answer("Бронирование не найдено")
                await state.clear()
                return

            can_refund, reason = await payment_manager.can_refund(booking)

            if not can_refund:
                await message.answer(
                    f"Возврат невозможен по техническим причинам:\n{reason}\n\n"
                    f"Возможно, потребуется возврат вручную через банк."
                )
                await state.clear()
                return

            await message.answer("Выполняется возврат...")

            success, refund_msg, refund = await payment_manager.process_refund(
                booking_id=booking_id,
                reason=f"Ручной возврат администратором {message.from_user.id}",
                amount=amount_kopecks
            )

            if success:
                await message.answer(
                    f"Возврат выполнен успешно!\n\n{refund_msg}",
                    reply_markup=finances_submenu()
                )

                # Уведомляем пользователя
                user_repo = UserRepository(session)
                user = await user_repo.get_by_id(booking.adult_user_id)

                if user and user.telegram_id:
                    bot = get_bot_instance()
                    if bot:
                        await bot.send_message(
                            user.telegram_id,
                            f"Администратор оформил возврат средств за бронирование #{booking_id}.\n"
                            f"Сумма: {refund.amount} руб.\n"
                            f"Деньги поступят на карту в течение 3-5 рабочих дней."
                        )
            else:
                await message.answer(
                    f"Ошибка при возврате:\n{refund_msg}\n\n"
                    f"Возможно, потребуется возврат вручную через банк.",
                    reply_markup=finances_submenu()
                )

        await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введите число (сумму в рублях) или 'все'")
    except Exception as e:
        logger.error(f"Ошибка при ручном возврате: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("admin_mark_refund_failed:"))
async def mark_refund_failed(callback: CallbackQuery):
    """Отметить возврат как окончательно неудачный (требует ручного вмешательства)"""
    refund_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session() as session:
        refund_repo = RefundRepository(session)
        refund = await refund_repo.get_refund_by_id(refund_id)

        if not refund:
            await callback.message.answer("Возврат не найден")
            return

        # Отмечаем, что возврат требует ручного вмешательства
        refund.status = RefundStatus.FAILED
        refund.retry_count = 999
        await session.flush()

        await callback.message.answer(
            f"Возврат #{refund_id} отмечен как требующий ручного вмешательства.\n"
            f"Администратор должен вернуть средства вручную через банк.",
            reply_markup=back_to_admin_menu("admin_refunds_menu")
        )


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

        from app.admin_panel.keyboards_adm import refund_detail_actions
        await callback.message.edit_text(text, reply_markup=refund_detail_actions(refund.id))
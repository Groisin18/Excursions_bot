"""
Роутер для управления бронированиями пользователя
"""
import os

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.database.session import async_session
from app.database.managers import BookingManager, PaymentManager
from app.database.repositories import (
    UserRepository, BookingRepository, RefundRepository
)
from app.database.models import BookingStatus, PaymentStatus
from app.utils.logging_config import get_logger
from app.user_panel.keyboards import (
    main_menu, bookings_main_menu, empty_bookings, back_to_booking,
    bookings_list, paid_booking_actions, cancel_confirmation,
    active_booking_actions, cancel_booking_button, cancel_booking_warning_button,
    back_to_booking_menu
)
from app.utils.admin_notifications import notify_admins
from app.services.scheduler.bot_instance import get_bot_instance

router = Router(name="user_bookings")
logger = get_logger(__name__)


@router.callback_query(F.data == 'user_booking')
async def bookings_main(callback: CallbackQuery):
    """Главное меню раздела 'Мои бронирования'"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} открыл меню бронирований")

    try:
        await callback.answer()
        await callback.message.edit_text(
            "Мои бронирования\n\nВыберите раздел:",
            reply_markup=bookings_main_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка в меню бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'my_active_bookings')
async def active_bookings_list(callback: CallbackQuery):
    """Список активных бронирований пользователя"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} запросил список активных бронирований")

    try:
        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден. Пожалуйста, зарегистрируйтесь.",
                    reply_markup=main_menu()
                )
                return

            booking_manager = BookingManager(session)
            active_bookings = await booking_manager.get_user_active_bookings(user.id)

            if not active_bookings:
                await callback.message.answer(
                    "У вас нет активных бронирований.",
                    reply_markup=empty_bookings()
                )
                return

            text = "Активные бронирования:\n\n"

            for booking in active_bookings:
                slot = booking.slot
                excursion = slot.excursion if slot else None

                if slot and excursion:
                    date_str = slot.start_datetime.strftime("%d.%m.%Y")
                    time_str = slot.start_datetime.strftime("%H:%M")
                    payment_status = "Оплачено" if booking.is_paid else "Ожидает оплаты"

                    text += (
                        f"{excursion.name}\n"
                        f"Дата: {date_str} в {time_str}\n"
                        f"Участников: {booking.people_count}\n"
                        f"Статус: {payment_status}\n"
                        f"Сумма: {booking.total_price} руб.\n\n"
                    )

            await callback.message.edit_text(
                text,
                reply_markup=bookings_list(active_bookings, "booking_detail:")
            )

    except Exception as e:
        logger.error(f"Ошибка получения активных бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке бронирований.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'my_history_bookings')
async def history_bookings_list(callback: CallbackQuery):
    """Список истории бронирований пользователя"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} запросил историю бронирований")

    try:
        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден. Пожалуйста, зарегистрируйтесь.",
                    reply_markup=main_menu()
                )
                return

            booking_manager = BookingManager(session)
            history_bookings = await booking_manager.get_user_history_bookings(user.id)

            if not history_bookings:
                await callback.message.edit_text(
                    "У вас нет бронирований в истории.",
                    reply_markup=empty_bookings()
                )
                return

            text = "История бронирований:\n\n"

            for booking in history_bookings:
                slot = booking.slot
                excursion = slot.excursion if slot else None

                if slot and excursion:
                    date_str = slot.start_datetime.strftime("%d.%m.%Y")
                    time_str = slot.start_datetime.strftime("%H:%M")

                    status_map = {
                        BookingStatus.cancelled: "Отменено",
                        BookingStatus.completed: "Завершено"
                    }
                    status = status_map.get(booking.booking_status, str(booking.booking_status.value))

                    text += (
                        f"{excursion.name}\n"
                        f"Дата: {date_str} в {time_str}\n"
                        f"Статус: {status}\n"
                        f"Сумма: {booking.total_price} руб.\n\n"
                    )

            await callback.message.edit_text(
                text,
                reply_markup=bookings_list(history_bookings, "booking_detail:")
            )

    except Exception as e:
        logger.error(f"Ошибка получения истории бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке истории.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('booking_detail:'))
async def booking_detail(callback: CallbackQuery):
    """Детальная информация о бронировании"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} запросил детали бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking:
                await callback.message.answer(
                    "Бронирование не найдено.",
                    reply_markup=main_menu()
                )
                return

            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user or booking.adult_user_id != user.id:
                logger.warning(f"Пользователь {user_telegram_id} пытается получить чужое бронирование {booking_id}")
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_menu()
                )
                return

            payment_manager = PaymentManager(session)
            payments_info = await payment_manager.get_booking_payments_info(booking_id)

            slot = booking.slot
            excursion = slot.excursion if slot else None

            if not slot or not excursion:
                await callback.message.answer(
                    "Информация о бронировании неполная.",
                    reply_markup=main_menu()
                )
                return

            date_str = slot.start_datetime.strftime("%d.%m.%Y")
            time_str = slot.start_datetime.strftime("%H:%M")

            status_map = {
                BookingStatus.active: "Активно",
                BookingStatus.cancelled: "Отменено",
                BookingStatus.completed: "Завершено"
            }
            booking_status = status_map.get(booking.booking_status, str(booking.booking_status.value))

            payment_status_map = {
                PaymentStatus.not_paid: "Не оплачено",
                PaymentStatus.pending: "Ожидает подтверждения",
                PaymentStatus.paid: "Оплачено",
                PaymentStatus.refunded: "Возврат"
            }
            payment_status = payment_status_map.get(booking.payment_status, str(booking.payment_status.value))

            text = (
                f"Бронирование #{booking.id}\n\n"
                f"Экскурсия: {excursion.name}\n"
                f"Дата и время: {date_str} в {time_str}\n"
                f"Участников: {booking.people_count} (1 взрослый + {booking.children_count} детей)\n"
                f"Сумма: {booking.total_price} руб.\n"
                f"Статус: {booking_status}\n"
                f"Оплата: {payment_status}\n"
            )

            if payments_info['has_payments']:
                text += f"\nПлатежи:\n"
                for payment in payments_info['payments']:
                    payment_date = payment['created_at'].strftime("%d.%m.%Y %H:%M") if payment['created_at'] else "дата неизвестна"
                    text += f"- {payment['amount']} руб. ({payment['payment_method']}), статус: {payment['status'] or 'завершён'}\n"

            if booking.booking_status == BookingStatus.active and booking.payment_status == PaymentStatus.not_paid:
                reply_markup = active_booking_actions(booking_id)
            elif booking.payment_status == PaymentStatus.paid:
                reply_markup = paid_booking_actions(booking_id)
            else:
                reply_markup = bookings_main_menu()

            await callback.message.edit_text(
                text,
                reply_markup=reply_markup
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка получения деталей бронирования для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке деталей бронирования.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('user_cancel_booking:'))
async def cancel_booking_confirm(callback: CallbackQuery):
    """Подтверждение отмены бронирования"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} запросил подтверждение отмены бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking:
                await callback.message.edit_text(
                    "Бронирование не найдено.",
                    reply_markup=main_menu()
                )
                return

            if booking.payment_status == PaymentStatus.paid:
                payment_manager = PaymentManager(session)
                can_refund, reason = await payment_manager.can_refund(booking)

                if can_refund:
                    refund_amount = await payment_manager.calculate_refund_amount(booking)
                    confirm_text = (
                        "Подтверждение отмены\n\n"
                        "Вы уверены, что хотите отменить бронирование?\n\n"
                        f"Сумма к возврату: {refund_amount // 100} руб.\n\n"
                        "Деньги будут возвращены на карту в течение 3-5 рабочих дней."
                    )
                else:
                    user_friendly_reason = _get_user_friendly_refund_reason(reason)
                    confirm_text = (
                        "Подтверждение отмены\n\n"
                        "Вы уверены, что хотите отменить бронирование?\n\n"
                        f"Внимание! Возврат невозможен.\n"
                        f"Причина: {user_friendly_reason}\n\n"
                        "Деньги возвращены не будут."
                    )
            else:
                confirm_text = (
                    "Подтверждение отмены\n\n"
                    "Вы уверены, что хотите отменить бронирование?\n\n"
                    "Это действие нельзя отменить.\n"
                    "Оплата не производилась, возврат не требуется."
                )

            await callback.message.edit_text(
                confirm_text,
                reply_markup=cancel_confirmation(booking_id)
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при запросе подтверждения отмены: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('user_confirm_cancel:'))
async def confirm_cancel_booking(callback: CallbackQuery):
    """Финальная отмена бронирования с автоматическим возвратом"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} подтверждает отмену бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден.",
                    reply_markup=main_menu()
                )
                return

            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking or booking.adult_user_id != user.id:
                logger.warning(f"Пользователь {user_telegram_id} пытается отменить чужое бронирование {booking_id}")
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_menu()
                )
                return

            booking_manager = BookingManager(session)
            success, message, refund_data = await booking_manager.cancel_booking(
                booking_id=booking_id,
                auto_refund=True,
                reason=f"Отмена пользователем {user_telegram_id}"
            )

            if not success:
                await callback.message.answer(
                    f"Ошибка при отмене: {message}",
                    reply_markup=main_menu()
                )
                return

            if refund_data:
                if refund_data.get('refund_id'):
                    response_text = (
                        f"Бронирование отменено.\n\n"
                        f"Запрос на возврат средств в размере {refund_data.get('amount', 0)} руб. принят.\n"
                        f"Деньги поступят на карту в течение 3-5 рабочих дней."
                    )
                elif refund_data.get('needs_manual'):
                    response_text = (
                        f"Бронирование отменено.\n\n"
                        f"Произошла ошибка при автоматическом возврате средств.\n"
                        f"Администратор уже уведомлен. В ближайшее время с вами свяжутся.\n"
                        f"Также вы можете самостоятельно связаться с администратором по поводу возврата.\n\n"
                        f"Приносим извинения за неудобства."
                    )
                else:
                    response_text = f"Бронирование отменено.\n\n{message}"
            else:
                response_text = "Бронирование успешно отменено."

            await callback.message.answer(
                response_text,
                reply_markup=main_menu()
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при отмене бронирования {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при отмене бронирования.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('refund_info:'))
async def refund_info(callback: CallbackQuery):
    """Информация о возврате для оплаченного бронирования"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} запросил информацию о возврате для бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking:
                await callback.message.answer(
                    "Бронирование не найдено.",
                    reply_markup=main_menu()
                )
                return

            payment_manager = PaymentManager(session)
            can_refund, reason = await payment_manager.can_refund(booking)

            if can_refund:
                refund_amount = await payment_manager.calculate_refund_amount(booking)
                text = (
                    f"Возврат средств\n\n"
                    f"Сумма к возврату: {refund_amount // 100} руб.\n\n"
                    f"Для оформления возврата нажмите кнопку 'Отменить бронирование'.\n\n"
                    f"Деньги будут возвращены на карту, с которой производилась оплата, "
                    f"в течение 3-5 рабочих дней."
                )
                reply_markup = cancel_booking_button(booking_id)
            else:
                user_friendly_reason = _get_user_friendly_refund_reason(reason)
                text = (
                    f"Возврат невозможен\n\n"
                    f"Причина: {user_friendly_reason}\n\n"
                    f"Вы можете отменить бронирование, но деньги не будут возвращены."
                )
                reply_markup = cancel_booking_warning_button(booking_id)

            await callback.message.edit_text(
                text,
                reply_markup=reply_markup
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при получении информации о возврате: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

def _get_user_friendly_refund_reason(reason: str) -> str:
    """Преобразует техническую причину в понятное пользователю сообщение"""
    reason_lower = reason.lower()

    if "не оплачено" in reason_lower:
        return "бронирование не было оплачено"
    elif "часов" in reason_lower:
        return "до начала экскурсии осталось менее 4 часов"
    elif "слот" in reason_lower or "информация" in reason_lower:
        return "информация о времени экскурсии отсутствует"
    else:
        return reason

@router.callback_query(F.data == 'back_to_bookings_menu')
async def back_to_bookings_menu(callback: CallbackQuery):
    """Возврат в главное меню бронирований"""
    await callback.answer()
    await bookings_main(callback)

@router.callback_query(F.data == 'back_to_cabinet')
async def back_to_cabinet_from_bookings(callback: CallbackQuery):
    """Возврат в личный кабинет из раздела бронирований"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} возвращается в личный кабинет из раздела бронирований")

    try:
        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Произошла ошибка. Пожалуйста, войдите в личный кабинет заново.",
                    reply_markup=main_menu()
                )
                return

            from app.routers.user.account.personal_cabinet import back_to_cabinet as pc_back_to_cabinet
            await pc_back_to_cabinet(callback)

    except Exception as e:
        logger.error(f"Ошибка возврата в кабинет: {e}")
        await callback.message.answer(
            "Произошла ошибка при возврате в личный кабинет.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('payment_history:'))
async def payment_history(callback: CallbackQuery):
    """История платежей по бронированию (в разработке)"""
    await callback.answer()
    await callback.message.answer(
        "Функция просмотра истории платежей находится в разработке.",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "my_cancelled_paid_bookings")
async def cancelled_paid_bookings_list(callback: CallbackQuery):
    """
    Список отмененных, но оплаченных бронирований (требуют возврата)
    """
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} запросил список отмененных оплаченных бронирований")

    try:
        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден. Пожалуйста, зарегистрируйтесь.",
                    reply_markup=main_menu()
                )
                return

            # Получаем отмененные, но оплаченные бронирования
            booking_repo = BookingRepository(session)
            cancelled_paid_bookings = await booking_repo.get_cancelled_paid_bookings(user.id)

            if not cancelled_paid_bookings:
                await callback.message.edit_text(
                    "Нет отмененных оплаченных бронирований.\n\n"
                    "Если вы отменили оплаченную экскурсию, но деньги не вернулись, "
                    "пожалуйста, свяжитесь с администратором.",
                    reply_markup=back_to_booking_menu()
                )
                return

            text = "Отмененные, но не возвращенные бронирования:\n\n"

            for booking in cancelled_paid_bookings:
                slot = booking.slot
                excursion = slot.excursion if slot else None

                if slot and excursion:
                    date_str = slot.start_datetime.strftime("%d.%m.%Y")
                    time_str = slot.start_datetime.strftime("%H:%M")

                    text += (
                        f"{excursion.name}\n"
                        f"Дата: {date_str} в {time_str}\n"
                        f"Сумма: {booking.total_price} руб.\n"
                        f"Статус: Отменено, ожидает возврата\n\n"
                    )

            from app.user_panel.keyboards import cancelled_paid_bookings_list
            await callback.message.edit_text(
                text,
                reply_markup=cancelled_paid_bookings_list(cancelled_paid_bookings)
            )

    except Exception as e:
        logger.error(f"Ошибка получения отмененных оплаченных бронирований: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке данных.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('request_refund:'))
async def request_refund(callback: CallbackQuery):
    """
    Запрос на возврат средств для отмененного оплаченного бронирования
    """
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} запросил возврат для бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден.",
                    reply_markup=main_menu()
                )
                return

            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_with_slot(booking_id)

            if not booking or booking.adult_user_id != user.id:
                logger.warning(f"Пользователь {user_telegram_id} пытается запросить возврат чужого бронирования {booking_id}")
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_menu()
                )
                return

            # Проверяем, что бронирование отменено и оплачено
            if booking.booking_status != BookingStatus.cancelled:
                await callback.message.answer(
                    "Возврат возможен только для отмененных бронирований.",
                    reply_markup=back_to_booking(booking_id)
                )
                return

            if booking.payment_status != PaymentStatus.paid:
                await callback.message.answer(
                    f"Бронирование не оплачено. Статус: {booking.payment_status.value}",
                    reply_markup=back_to_booking(booking_id)
                )
                return

            # Проверяем время отмены
            refund_hours_before = int(os.getenv('REFUND_HOURS_BEFORE', default=4))

            if booking.cancelled_at:
                time_until_start = booking.slot.start_datetime - booking.cancelled_at
                hours_until_start = time_until_start.total_seconds() / 3600

                if hours_until_start <= refund_hours_before:
                    await callback.message.answer(
                        f"Возврат невозможен, так как бронирование было отменено "
                        f"менее чем за {refund_hours_before} часов до начала экскурсии.\n\n"
                        f"Время отмены: {booking.cancelled_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Время начала: {booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}",
                        reply_markup=back_to_booking(booking_id)
                    )
                    return
            else:
                # Если нет времени отмены (старые бронирования), считаем возврат невозможным
                await callback.message.answer(
                    "Не удается определить время отмены бронирования. "
                    "Пожалуйста, обратитесь к администратору.",
                    reply_markup=back_to_booking(booking_id)
                )
                return

            # Проверяем, не было ли уже возврата
            refund_repo = RefundRepository(session)
            existing_refunds = await refund_repo.get_refunds_by_booking(booking_id)
            successful_refunds = [r for r in existing_refunds if r.status.value == "succeeded"]

            if successful_refunds:
                await callback.message.answer(
                    f"Для этого бронирования уже был выполнен возврат на сумму "
                    f"{successful_refunds[0].amount // 100} руб.\n\n"
                    f"Если деньги не поступили, обратитесь к администратору.",
                    reply_markup=back_to_booking(booking_id)
                )
                return

            # Показываем подтверждение
            payment_manager = PaymentManager(session)
            refund_amount = await payment_manager.calculate_refund_amount(booking)

            text = (
                f"Запрос на возврат средств\n\n"
                f"Бронирование #{booking_id}\n"
                f"Сумма к возврату: {refund_amount // 100} руб.\n\n"
                f"Бронирование было отменено: {booking.cancelled_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Начало экскурсии: {booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"После подтверждения мы инициируем возврат денег.\n"
                f"Деньги поступят на карту в течение 3-5 рабочих дней.\n\n"
                f"Подтверждаете запрос?"
            )

            from app.user_panel.keyboards import refund_request_confirmation
            await callback.message.edit_text(
                text,
                reply_markup=refund_request_confirmation(booking_id)
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при запросе возврата: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data.startswith('confirm_refund_request:'))
async def confirm_refund_request(callback: CallbackQuery):
    """
    Подтверждение запроса на возврат
    """
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} подтвердил запрос на возврат для бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден.",
                    reply_markup=main_menu()
                )
                return

            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_with_slot(booking_id)

            if not booking or booking.adult_user_id != user.id:
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_menu()
                )
                return

            # Повторная проверка статусов
            if booking.booking_status != BookingStatus.cancelled:
                await callback.message.answer(
                    "Возврат возможен только для отмененных бронирований.",
                    reply_markup=main_menu()
                )
                return

            if booking.payment_status != PaymentStatus.paid:
                await callback.message.answer(
                    "Бронирование не оплачено.",
                    reply_markup=main_menu()
                )
                return

            # Инициируем возврат
            payment_manager = PaymentManager(session)
            success, refund_msg, refund = await payment_manager.process_refund(
                booking_id=booking_id,
                reason=f"Запрос пользователя {user_telegram_id}",
                amount=None
            )

            if success:
                await callback.message.delete()
                await callback.message.answer(
                    f"Запрос на возврат принят!\n\n"
                    f"{refund_msg}\n\n"
                    f"Если деньги не поступят в течение 5 рабочих дней, "
                    f"пожалуйста, обратитесь к администратору.",
                    reply_markup=main_menu()
                )

                # Уведомляем админов

                bot = get_bot_instance()
                if bot:
                    admin_message = (
                        f"Пользователь {user.full_name} запросил возврат\n"
                        f"Бронирование #{booking_id}\n"
                        f"Сумма: {booking.total_price} руб.\n"
                        f"Статус: успешно\n\n"
                        f"{refund_msg}"
                    )
                    await notify_admins(bot, session, admin_message)

            else:
                await callback.message.delete()
                await callback.message.answer(
                    f"Не удалось инициировать возврат:\n\n{refund_msg}\n\n"
                    f"Пожалуйста, обратитесь к администратору.",
                    reply_markup=main_menu()
                )

    except Exception as e:
        logger.error(f"Ошибка при подтверждении возврата: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Пожалуйста, обратитесь к администратору.",
            reply_markup=main_menu()
        )

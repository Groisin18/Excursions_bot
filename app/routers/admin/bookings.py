from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database.models import PaymentStatus
from app.database.repositories import BookingRepository
from app.database.managers import SlotManager, BookingManager, PaymentManager
from app.database.session import async_session
from app.database.unit_of_work import UnitOfWork

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger
from app.admin_panel.keyboards_adm import (
    bookings_submenu, cancel_button, admin_cancel_booking_no_refund_menu,
    admin_cancel_booking_with_refund_menu, admin_force_refund_confirmation_menu
)
from app.admin_panel.states_adm import AdminStates


logger = get_logger(__name__)

router = Router(name="admin_bookings")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УПРАВЛЕНИЕ ЗАПИСЯМИ =====

@router.message(F.text == "Активные записи")
async def show_active_bookings(message: Message):
    """Показать все активные записи"""
    logger.info(f"Администратор {message.from_user.id} запросил активные записи")

    try:
        async with async_session() as session:
            slot_manager = SlotManager(session)
            bookings = await slot_manager.get_active_bookings()

            if not bookings:
                logger.debug("Активных записей не найдено")
                await message.answer("Активных записей нет")
                return

            logger.info(f"Найдено активных записей: {len(bookings)}")
            response = "Активные записи:\n\n"
            for booking in bookings[:10]:
                response += (
                    f"ID: {booking.id}\n"
                    f"Клиент: {booking.adult_user.full_name}\n"
                    f"Экскурсия: {booking.slot.excursion.name}\n"
                    f"Время: {booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Капитан: {booking.slot.captain.full_name}\n"
                    f"Людей: {booking.people_count}\n"
                    f"Оплата: {'Оплачено' if booking.payment_status == PaymentStatus.paid else 'Не оплачено'}\n"
                    f"---\n"
                )

            if len(bookings) > 10:
                response += f"\n... и еще {len(bookings) - 10} записей"

            await message.answer(response)
            logger.debug(f"Активные записи отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения активных записей: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка записей", reply_markup=bookings_submenu())

@router.message(F.text == "Неоплаченные")
async def show_unpaid_bookings(message: Message):
    """Показать неоплаченные записи"""
    logger.info(f"Администратор {message.from_user.id} запросил неоплаченные бронирования")

    try:
        async with async_session() as session:
            slot_manager = SlotManager(session)
            bookings = await slot_manager.get_unpaid_bookings()

            if not bookings:
                logger.debug("Неоплаченных записей не найдено")
                await message.answer("Неоплаченных записей нет")
                return

            logger.info(f"Найдено неоплаченных записей: {len(bookings)}")
            response = "Неоплаченные записи:\n\n"
            for booking in bookings:
                response += (
                    f"ID: {booking.id}\n"
                    f"Клиент: {booking.adult_user.full_name}\n"
                    f"Экскурсия: {booking.slot.excursion.name}\n"
                    f"Время: {booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Капитан: {booking.slot.captain.full_name}\n"
                    f"Людей: {booking.people_count}\n"
                    f"Сумма: {booking.total_price} руб.\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список неоплаченных отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения неоплаченных записей: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка неоплаченных записей", reply_markup=bookings_submenu())

@router.message(F.text == "Отменить запись")
async def cancel_booking(message: Message, state: FSMContext):
    """Отмена существующей записи - начало процесса"""
    logger.info(f"Администратор {message.from_user.id} хочет отменить запись")

    try:
        await message.answer(
            "Введите ID бронирования для отмены.\n\n"
            "ID можно найти в деталях бронирования.",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminStates.waiting_for_booking_cancel)
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.message(AdminStates.waiting_for_booking_cancel)
async def process_booking_cancel_id(message: Message, state: FSMContext):
    """Обработка ID бронирования для отмены"""
    try:
        booking_id = int(message.text.strip())
        logger.info(f"Администратор {message.from_user.id} ввел ID {booking_id} для отмены")

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_with_slot(booking_id)

            if not booking:
                await message.answer(
                    f"Бронирование #{booking_id} не найдено.\n"
                    "Проверьте ID и попробуйте снова.",
                    reply_markup=cancel_button()
                )
                await state.clear()
                return

            slot = booking.slot
            excursion = slot.excursion if slot else None

            info_text = (
                f"Бронирование #{booking.id}\n\n"
                f"Клиент: {booking.adult_user.full_name or booking.adult_user.phone_number}\n"
                f"Экскурсия: {excursion.name if excursion else 'Неизвестно'}\n"
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M') if slot else 'Неизвестно'}\n"
                f"Сумма: {booking.total_price} руб.\n"
                f"Статус оплаты: {booking.payment_status.value}\n"
            )

            if booking.payment_status == PaymentStatus.paid:
                await message.answer(
                    info_text + "\nВыберите вариант отмены:",
                    reply_markup=admin_cancel_booking_with_refund_menu(booking_id)
                )
            else:
                await message.answer(
                    info_text + "\nБронирование не оплачено. Отменить без возврата?",
                    reply_markup=admin_cancel_booking_no_refund_menu(booking_id)
                )

            await state.clear()

    except ValueError:
        await message.answer(
            "Неверный формат ID. Введите число.",
            reply_markup=cancel_button()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка обработки ID бронирования: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("admin_cancel_booking:"))
async def admin_cancel_booking_callback(callback: CallbackQuery):
    """Обработка отмены бронирования администратором"""
    parts = callback.data.split(":")
    booking_id = int(parts[1])
    refund_option = parts[2] if len(parts) > 2 else "without_refund"

    # with_force_refund - возврат даже если не положен по правилам
    # with_refund - обычный возврат (только если положен)
    # without_refund - отмена без возврата

    force_refund = (refund_option == "with_force_refund")
    auto_refund = (refund_option in ["with_refund", "with_force_refund"])

    logger.info(f"Администратор {callback.from_user.id} отменяет бронь {booking_id}, "
                f"auto_refund={auto_refund}, force_refund={force_refund}")

    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_manager = BookingManager(session)
                payment_manager = PaymentManager(session)

                booking = await booking_manager.booking_repo.get_with_slot(booking_id)

                if not booking:
                    await callback.message.edit_text("Бронирование не найдено.")
                    return

                # Если обычный возврат (не принудительный), проверяем возможность
                if auto_refund and not force_refund:
                    can_refund, refund_reason = await payment_manager.can_refund(booking)
                    if not can_refund:
                        await callback.message.edit_text(
                            f"Обычный возврат невозможен.\nПричина: {refund_reason}\n\n"
                            f"Вы можете выполнить принудительный возврат (деньги вернутся клиенту "
                            f"в любом случае, но вы берете ответственность на себя).",
                            reply_markup=admin_force_refund_confirmation_menu(booking_id)
                        )
                        return

                # Выполняем отмену
                success, message, refund_data = await booking_manager.cancel_booking(
                    booking_id=booking_id,
                    auto_refund=auto_refund,
                    reason=f"Отмена администратором {callback.from_user.id}",
                    force_refund=force_refund
                )

                if success:
                    response_text = f"Бронирование #{booking_id} успешно отменено."

                    if auto_refund and refund_data:
                        if force_refund:
                            response_text += f"\nПринудительный возврат средств инициирован."
                        else:
                            response_text += f"\nВозврат средств инициирован."

                    await callback.message.edit_text(response_text)

                    # Отправляем уведомление клиенту
                    bot = callback.bot
                    if booking.adult_user.telegram_id:
                        try:
                            slot = booking.slot
                            excursion = slot.excursion if slot else None
                            notification_text = (
                                f"Ваше бронирование #{booking.id} было отменено администратором.\n\n"
                                f"Экскурсия: {excursion.name if excursion else 'Неизвестно'}\n"
                                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M') if slot else 'Неизвестно'}"
                            )

                            if auto_refund:
                                notification_text += "\n\nСредства будут возвращены на вашу карту в течение 5-10 рабочих дней."
                                if force_refund:
                                    notification_text += "\nВозврат средств выполнен принудительно по решению администратора."
                            else:
                                notification_text += "\n\nОплата не производилась, возврат не требуется."

                            await bot.send_message(
                                chat_id=booking.adult_user.telegram_id,
                                text=notification_text
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления клиенту: {e}")
                else:
                    await callback.message.edit_text(f"Ошибка отмены: {message}")

    except Exception as e:
        logger.error(f"Ошибка отмены бронирования {booking_id}: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка при отмене бронирования.")


@router.callback_query(F.data.startswith("admin_cancel_booking_from_list:"))
async def admin_cancel_booking_from_list_callback(callback: CallbackQuery):
    """Отмена бронирования из списка (inline)"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет отменить бронирование {booking_id} из списка")

    await callback.answer()

    try:
        async with async_session() as session:
            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_with_slot(booking_id)

            if not booking:
                await callback.message.edit_text("Бронирование не найдено.")
                return

            if booking.payment_status == PaymentStatus.paid:
                await callback.message.edit_text(
                    f"Бронирование #{booking_id}\n\n"
                    f"Сумма: {booking.total_price} руб.\n"
                    f"Выберите вариант отмены:",
                    reply_markup=admin_cancel_booking_with_refund_menu(booking_id)
                )
            else:
                await callback.message.edit_text(
                    f"Бронирование #{booking_id} не оплачено.\nОтменить без возврата?",
                    reply_markup=admin_cancel_booking_no_refund_menu(booking_id)
                )

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка при загрузке информации о бронировании.")
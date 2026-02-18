'''
Роутер для управления бронированиями пользователя
'''
from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.database.session import async_session
from app.database.managers import BookingManager, PaymentManager
from app.database.repositories import UserRepository, BookingRepository
from app.database.models import BookingStatus, PaymentStatus
from app.utils.logging_config import get_logger
from app.user_panel import keyboards as kb
from app.user_panel.keyboards import main as main_keyboard

router = Router(name="user_bookings")
logger = get_logger(__name__)


@router.callback_query(F.data == 'user_booking')
async def bookings_main_menu(callback: CallbackQuery):
    """Главное меню раздела 'Мои бронирования'"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} открыл меню бронирований")

    try:
        await callback.answer()
        await callback.message.edit_text(
            "Мои бронирования\n\nВыберите раздел:",
            reply_markup=kb.bookings_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка в меню бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_keyboard
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
                    reply_markup=main_keyboard
                )
                return

            booking_manager = BookingManager(session)
            active_bookings = await booking_manager.get_user_active_bookings(user.id)

            if not active_bookings:
                await callback.message.answer(
                    "У вас нет активных бронирований.",
                    reply_markup=kb.empty_bookings_keyboard()
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
                reply_markup=kb.bookings_list_keyboard(active_bookings, "booking_detail:")
            )

    except Exception as e:
        logger.error(f"Ошибка получения активных бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке бронирований.",
            reply_markup=main_keyboard
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
                    reply_markup=main_keyboard
                )
                return

            booking_manager = BookingManager(session)
            history_bookings = await booking_manager.get_user_history_bookings(user.id)

            if not history_bookings:
                await callback.message.edit_text(
                    "У вас нет бронирований в истории.",
                    reply_markup=kb.empty_bookings_keyboard()
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
                reply_markup=kb.bookings_list_keyboard(history_bookings, "booking_detail:")
            )

    except Exception as e:
        logger.error(f"Ошибка получения истории бронирований для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке истории.",
            reply_markup=main_keyboard
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
                    reply_markup=main_keyboard
                )
                return

            # Проверяем принадлежность
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user or booking.adult_user_id != user.id:
                logger.warning(f"Пользователь {user_telegram_id} пытается получить чужое бронирование {booking_id}")
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_keyboard
                )
                return

            # Получаем информацию о платежах
            payment_manager = PaymentManager(session)
            payments_info = await payment_manager.get_booking_payments_info(booking_id)

            slot = booking.slot
            excursion = slot.excursion if slot else None

            if not slot or not excursion:
                await callback.message.answer(
                    "Информация о бронировании неполная.",
                    reply_markup=main_keyboard
                )
                return

            # Формируем детальную информацию
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

            # Определяем, какие кнопки показывать
            show_cancel = (
                booking.booking_status == BookingStatus.active and
                booking.payment_status == PaymentStatus.not_paid
            )
            show_refund_info = (booking.payment_status == PaymentStatus.paid)
            show_pay = True

            await callback.message.edit_text(
                text,
                reply_markup=kb.booking_detail_keyboard(
                    booking_id,
                    show_cancel=show_cancel,
                    show_refund_info=show_refund_info,
                    show_pay=show_pay
                )
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка получения деталей бронирования для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке деталей бронирования.",
            reply_markup=main_keyboard
        )


@router.callback_query(F.data.startswith('cancel_booking:'))
async def cancel_booking_confirm(callback: CallbackQuery):
    """Подтверждение отмены бронирования"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} запросил подтверждение отмены бронирования {booking_id}")

        await callback.answer()
        await callback.message.edit_text(
            "Вы уверены, что хотите отменить бронирование?\n\n"
            "Если бронирование оплачено и до начала экскурсии осталось больше 4 часов, "
            "деньги будут возвращены.",
            reply_markup=kb.cancel_confirmation_keyboard(booking_id)
        )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при запросе подтверждения отмены: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_keyboard
        )


@router.callback_query(F.data.startswith('confirm_cancel:'))
async def confirm_cancel_booking(callback: CallbackQuery):
    """Финальная отмена бронирования"""
    user_telegram_id = callback.from_user.id

    try:
        booking_id = int(callback.data.split(':')[1])
        logger.info(f"Пользователь {user_telegram_id} подтверждает отмену бронирования {booking_id}")

        await callback.answer()

        async with async_session() as session:
            # Проверяем принадлежность
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_telegram_id)

            if not user:
                await callback.message.answer(
                    "Пользователь не найден.",
                    reply_markup=main_keyboard
                )
                return

            booking_repo = BookingRepository(session)
            booking = await booking_repo.get_by_id(booking_id)

            if not booking or booking.adult_user_id != user.id:
                logger.warning(f"Пользователь {user_telegram_id} пытается отменить чужое бронирование {booking_id}")
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_keyboard
                )
                return

            # Отменяем бронирование через менеджер
            booking_manager = BookingManager(session)
            success, message, refund_data = await booking_manager.cancel_booking(booking_id)

            if not success:
                await callback.message.answer(
                    f"Ошибка при отмене: {message}",
                    reply_markup=main_keyboard
                )
                return

            # Если есть данные для возврата, инициируем возврат
            if refund_data:
                payment_manager = PaymentManager(session)
                can_refund, refund_reason = await payment_manager.can_refund(booking)

                if can_refund:
                    refund_amount = await payment_manager.calculate_refund_amount(booking)
                    await payment_manager.process_refund(booking_id, refund_amount)

                    await callback.message.answer(
                        f"Бронирование отменено.\n"
                        f"Запрос на возврат средств в размере {refund_amount} руб. принят в обработку.\n"
                        f"Деньги поступят на карту в течение 3-5 рабочих дней.",
                        reply_markup=main_keyboard
                    )
                else:
                    await callback.message.answer(
                        f"Бронирование отменено.\n"
                        f"Возврат невозможен: {refund_reason}",
                        reply_markup=main_keyboard
                    )
            else:
                await callback.message.answer(
                    "Бронирование успешно отменено.",
                    reply_markup=main_keyboard
                )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при отмене бронирования {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при отмене бронирования.",
            reply_markup=main_keyboard
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
                    reply_markup=main_keyboard
                )
                return

            payment_manager = PaymentManager(session)
            can_refund, reason = await payment_manager.can_refund(booking)

            if can_refund:
                refund_amount = await payment_manager.calculate_refund_amount(booking)

                text = (
                    f"Возврат средств\n\n"
                    f"Сумма к возврату: {refund_amount} руб.\n"
                    f"Для оформления возврата нажмите кнопку 'Отменить бронирование' в деталях.\n\n"
                    f"Деньги будут возвращены на карту, с которой производилась оплата, "
                    f"в течение 3-5 рабочих дней."
                )
            else:
                text = (
                    f"Возврат невозможен\n\n"
                    f"Причина: {reason}\n\n"
                    f"Вы можете отменить бронирование, но деньги не будут возвращены."
                )

            await callback.message.edit_text(
                text,
                reply_markup=kb.back_to_booking_keyboard(booking_id)
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer("Ошибка: некорректный идентификатор бронирования")
    except Exception as e:
        logger.error(f"Ошибка при получении информации о возврате: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_keyboard
        )


@router.callback_query(F.data == 'back_to_bookings_menu')
async def back_to_bookings_menu(callback: CallbackQuery):
    """Возврат в главное меню бронирований"""
    await callback.answer()
    await bookings_main_menu(callback)


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
                    reply_markup=main_keyboard
                )
                return

            # Импортируем функцию из personal_cabinet
            from app.routers.user.account.personal_cabinet import back_to_cabinet as pc_back_to_cabinet
            await pc_back_to_cabinet(callback)

    except Exception as e:
        logger.error(f"Ошибка возврата в кабинет: {e}")
        await callback.message.answer(
            "Произошла ошибка при возврате в личный кабинет.",
            reply_markup=main_keyboard
        )


# TODO: Хэндлер для оплаты (будет реализован позже)
@router.callback_query(F.data.startswith('pay_booking:'))
async def pay_booking(callback: CallbackQuery):
    """Оплата бронирования (в разработке)"""
    await callback.answer()
    await callback.message.answer(
        "Функция оплаты находится в разработке. Пожалуйста, воспользуйтесь другими способами оплаты.",
        reply_markup=main_keyboard
    )


# TODO: Хэндлер для истории платежей (будет реализован позже)
@router.callback_query(F.data.startswith('payment_history:'))
async def payment_history(callback: CallbackQuery):
    """История платежей по бронированию (в разработке)"""
    await callback.answer()
    await callback.message.answer(
        "Функция просмотра истории платежей находится в разработке.",
        reply_markup=main_keyboard
    )
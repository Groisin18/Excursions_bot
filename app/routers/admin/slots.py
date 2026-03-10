'''
Роутер для управления слотами (админ-панель)
'''
import re
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import (
    UserRepository, SlotRepository, ExcursionRepository
)
from app.database.managers import SlotManager
from app.database.session import async_session

from app.admin_panel.states_adm import RescheduleSlot
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu, excursions_submenu,
    slot_actions_menu, slots_conflict_keyboard,
    captains_selection_menu, slot_action_confirmation_menu,
    no_captains_options_menu, captain_conflict_keyboard,
    schedule_date_management_menu
)
from app.middlewares import AdminMiddleware
from app.services.redis import redis_client
from app.utils.logging_config import get_logger
from app.utils.validation import validate_slot_date, validate_slot_time


logger = get_logger(__name__)


router = Router(name="admin_slots")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УПРАВЛЕНИЕ СЛОТОМ =====


@router.callback_query(F.data.startswith("cancel_slot:"))
async def cancel_slot_callback(callback: CallbackQuery):
    """Отмена слота"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет отменить слот {slot_id}")

    try:
        await callback.answer()

        await callback.message.answer(
            "Вы уверены, что хотите отменить этот слот?\n"
            "Все бронирования будут отменены автоматически.",
            reply_markup=slot_action_confirmation_menu(
                slot_id=slot_id,
                action="cancel",
                back_callback=f"manage_slot:{slot_id}"
            )
        )

    except Exception as e:
        logger.error(f"Ошибка начала отмены слота {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("confirm_cancel_slot:"))
async def confirm_cancel_slot_callback(callback: CallbackQuery):
    """Подтверждение отмены слота"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} подтвердил отмену слота {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)

                # Получаем полную информацию о слоте до отмены (чтобы были данные для уведомлений)
                slot_full_info = await slot_manager.get_slot_full_info(slot_id)

                if not slot_full_info:
                    await callback.message.answer("Слот не найден.")
                    return

                slot = slot_full_info['slot']

                # Отменяем слот
                success, cancelled_slot = await slot_manager.cancel_slot(slot_id)

                if not success:
                    await callback.message.answer("Не удалось отменить слот.")
                    return

                # Уведомляем клиентов о отмене
                notified_count = 0
                failed_notifications = []
                no_telegram_clients = []

                # Используем активные бронирования из slot_full_info
                active_bookings = slot_full_info.get('active_bookings', [])

                if active_bookings:
                    logger.info(f"Слот {slot_id} отменен. Активных бронирований для уведомления: {len(active_bookings)}")

                    bot = callback.bot
                    slot_datetime = slot.start_datetime.strftime('%d.%m.%Y %H:%M')
                    excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

                    for booking in active_bookings:
                        # Получаем клиента из бронирования
                        client = booking.adult_user

                        if client and client.telegram_id:
                            try:
                                # Проверяем, не отправляли ли уже уведомление для этого бронирования
                                notification_key = f"notification:slot_cancel:{booking.id}"
                                already_sent = await redis_client.client.get(notification_key)

                                if already_sent:
                                    logger.debug(f"Уведомление для брони #{booking.id} уже отправлено")
                                    continue

                                # Формируем текст уведомления
                                notification_text = [
                                    "ОТМЕНА ЭКСКУРСИИ",
                                    "",
                                    f"Уважаемый клиент, сообщаем вам об отмене экскурсии:",
                                    f"",
                                    f"Экскурсия: {excursion_name}",
                                    f"Дата и время: {slot_datetime}",
                                    f"",
                                    f"К сожалению, по техническим причинам мы вынуждены отменить данную экскурсию.",
                                    f"",
                                    f"Если вы производили оплату, средства будут возвращены в ближайшее время.",
                                    f"",
                                    f"Приносим извинения за доставленные неудобства.",
                                    f"Для уточнения информации свяжитесь с администратором."
                                ]
                                # TODO Добавить отмену оплаты
                                # Добавляем информацию о детях, если они есть
                                if booking.booking_children:
                                    children_names = []
                                    for bc in booking.booking_children:
                                        if bc.child and bc.child.full_name:
                                            children_names.append(bc.child.full_name)

                                    if children_names:
                                        # Вставляем после строки с датой
                                        notification_text.insert(5, f"Дети: {', '.join(children_names)}")

                                await bot.send_message(
                                    chat_id=client.telegram_id,
                                    text="\n".join(notification_text)
                                )

                                # Сохраняем флаг отправки на 24 часа (86400 секунд)
                                await redis_client.client.setex(notification_key, 86400, "1")
                                notified_count += 1
                                logger.info(f"Уведомление об отмене слота отправлено клиенту {client.telegram_id} (бронь #{booking.id})")

                            except Exception as e:
                                error_msg = f"Ошибка отправки уведомления клиенту {client.telegram_id} (бронь #{booking.id}): {e}"
                                logger.error(error_msg, exc_info=True)
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                                failed_notifications.append(client_info)
                        else:
                            # Клиент без telegram_id
                            if client:
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                            else:
                                client_info = "Клиент не найден"
                            no_telegram_clients.append(client_info)

                # Формируем ответ администратору
                response_parts = [
                    f"Слот #{slot_id} успешно отменен.",
                    f"Все связанные бронирования отменены."
                ]

                if notified_count > 0:
                    response_parts.append(f"")
                    response_parts.append(f"Уведомления отправлены: {notified_count} клиентам")

                if failed_notifications:
                    # Убираем дубликаты
                    failed_unique = list(set(failed_notifications))
                    response_parts.append(f"")
                    response_parts.append(f"Не удалось отправить уведомления:")
                    for client_info in failed_unique[:5]:
                        response_parts.append(f"• {client_info}")
                    if len(failed_unique) > 5:
                        response_parts.append(f"• и еще {len(failed_unique) - 5}")

                if no_telegram_clients:
                    # Убираем дубликаты
                    no_telegram_unique = list(set(no_telegram_clients))
                    response_parts.append(f"")
                    response_parts.append(f"Клиенты без Telegram ID (уведомления не отправлены):")
                    for client_info in no_telegram_unique[:5]:
                        response_parts.append(f"• {client_info}")
                    if len(no_telegram_unique) > 5:
                        response_parts.append(f"• и еще {len(no_telegram_unique) - 5}")

                await callback.message.answer("\n".join(response_parts))

                logger.info(f"Слот {slot_id} отменен администратором {callback.from_user.id}. "
                          f"Уведомлено клиентов: {notified_count}, "
                          f"ошибок: {len(failed_notifications)}, "
                          f"без Telegram ID: {len(no_telegram_clients)}")

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=schedule_exc_management_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка отмены слота {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при отмене слота",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("assign_captain:"))
async def assign_captain_callback(callback: CallbackQuery):
    """Назначение капитана на слот"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет назначить капитана на слот {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            user_repo = UserRepository(session)
            captains = await user_repo.get_all_captains()

            if not captains:
                await callback.message.answer(
                    "Нет доступных капитанов. Сначала добавьте капитанов через меню 'Капитаны'."
                )
                return

            await callback.message.answer(
                "Выберите капитана для назначения:",
                reply_markup=captains_selection_menu(
                    item_id=slot_id,
                    captains=captains,
                    callback_prefix="select_captain_for_slot",
                    include_back=True,
                    back_callback=f"manage_slot:{slot_id}",
                    include_remove=False
                )
            )

    except Exception as e:
        logger.error(f"Ошибка назначения капитана: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("select_captain_for_slot:"))
async def select_captain_for_slot(callback: CallbackQuery):
    """Обработка выбора капитана для слота"""
    data_parts = callback.data.split(":")
    slot_id = int(data_parts[1])
    captain_id = int(data_parts[2])

    logger.info(f"Администратор {callback.from_user.id} выбрал капитана {captain_id} для слота {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)
                user_repo = UserRepository(uow.session)

                # Получаем информацию о слоте до назначения (для уведомления)
                slot_info = await slot_manager.get_slot_full_info(slot_id)

                if not slot_info:
                    await callback.message.answer("Не удалось получить информацию о слоте.")
                    return

                slot = slot_info['slot']

                # Назначаем капитана
                success = await slot_manager.slot_repo.assign_captain(slot_id, captain_id)

                if not success:
                    await callback.message.answer("Не удалось назначить капитана.")
                    return

                # Получаем информацию о капитане
                captain = await user_repo.get_by_id(captain_id)

                if slot and captain:
                    # Формируем базовую информацию для ответа и уведомления
                    slot_datetime = slot.start_datetime.strftime('%d.%m.%Y %H:%M')
                    excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

                    # Отправляем уведомление капитану
                    notification_status = "Уведомление не отправлено"
                    if captain.telegram_id:
                        try:
                            # Получаем информацию о забронированных местах и весе
                            booked_places = slot_info.get('booked_places', 0)
                            current_weight = slot_info.get('current_weight', 0)

                            notification_text = [
                                "НАЗНАЧЕНИЕ НА ЭКСКУРСИЮ",
                                "",
                                f"Уважаемый {captain.full_name}, вы назначены капитаном на экскурсию:",
                                f"",
                                f"Экскурсия: {excursion_name}",
                                f"Дата и время: {slot_datetime}",
                                f"",
                                f"Информация о слоте:",
                                f"• Всего мест: {slot.max_people}",
                                f"• Забронировано мест: {booked_places}",
                                f"• Максимальный вес: {slot.max_weight} кг",
                                f"• Текущий вес: {current_weight} кг",
                                f"",
                                f"Пожалуйста, будьте готовы провести экскурсию.",
                                f"Свяжитесь с администратором если у вас возникли вопросы."
                            ]

                            await callback.bot.send_message(
                                chat_id=captain.telegram_id,
                                text="\n".join(notification_text)
                            )

                            logger.info(f"Уведомление о назначении отправлено капитану {captain.telegram_id} (слот #{slot_id})")
                            notification_status = "Уведомление отправлено"

                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления капитану {captain.telegram_id}: {e}", exc_info=True)
                            notification_status = "Ошибка отправки уведомления"
                    else:
                        notification_status = "У капитана нет Telegram ID"
                        logger.info(f"Капитан {captain_id} не имеет Telegram ID")

                    # Формируем ответ администратору
                    await callback.message.answer(
                        f"Капитан успешно назначен!\n\n"
                        f"Слот: #{slot_id}\n"
                        f"Экскурсия: {excursion_name}\n"
                        f"Дата и время: {slot_datetime}\n\n"
                        f"Капитан: {captain.full_name}\n"
                        f"Телефон: {captain.phone_number}\n"
                        f"Telegram ID: {captain.telegram_id or 'Не указан'}\n\n"
                        f"Статус уведомления: {notification_status}"
                    )
                else:
                    await callback.message.answer(
                        f"Капитан назначен, но не удалось получить детальную информацию.\n"
                        f"Слот #{slot_id}, капитан ID {captain_id}"
                    )

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=slot_actions_menu(slot_id)
        )

    except Exception as e:
        logger.error(f"Ошибка назначения капитана {captain_id} на слот {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при назначении капитана",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("manage_slot:"))
async def manage_slot_callback(callback: CallbackQuery):
    """Управление конкретным слотом"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} управляет слотом {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info:
                await callback.message.answer(f"Слот {slot_id} не найден.")
                return

            slot = slot_info['slot']
            booked_places = slot_info['booked_places']
            current_weight = slot_info['current_weight']
            active_bookings = slot_info['active_bookings']

            response_lines = [
                f"Управление слотом #{slot.id}",
                f"",
                f"Экскурсия: {slot.excursion.name if slot.excursion else 'Неизвестно'}",
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}",
                f"Продолжительность: {slot.excursion.base_duration_minutes if slot.excursion else '?'} мин.",
                f"Свободные места: {slot.max_people - booked_places}/{slot.max_people}",
                f"Занятость по весу: {current_weight}/{slot.max_weight}",
                f"Статус: {slot.status.value}",
                f"Капитан: {slot.captain.full_name if slot.captain else 'не назначен'}"
            ]

            if active_bookings:
                response_lines.extend([
                    f"",
                    f"Активных бронирований: {len(active_bookings)}",
                    f"Бронирования:"
                ])
                for booking in active_bookings[:5]:
                    client = booking.adult_user if hasattr(booking, 'adult_user') else None
                    if client:
                        response_lines.append(
                            f"• {client.full_name} ({booking.adults_count}+{booking.children_count})"
                        )
                if len(active_bookings) > 5:
                    response_lines.append(f"... и еще {len(active_bookings) - 5}")

            await callback.message.answer("\n".join(response_lines))
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slot_actions_menu(slot_id)
            )

    except Exception as e:
        logger.error(f"Ошибка управления слотом {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при управлении слотом",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("slot_details:"))
async def show_slot_details(callback: CallbackQuery):
    """Показать детальную информацию о слотe"""
    slot_id = int(callback.data.split(":")[1])

    try:
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info:
                await callback.message.answer(f"Слот {slot_id} не найден.")
                return

            slot = slot_info['slot']
            booked_places = slot_info['booked_places']
            current_weight = slot_info['current_weight']
            active_bookings = slot_info.get('active_bookings', [])

            response_lines = [
                f"Детальная информация о слотe #{slot.id}",
                f"",
                f"Экскурсия: {slot.excursion.name if slot.excursion else 'Неизвестно'}",
                f"Описание: {slot.excursion.description if slot.excursion else 'Нет'}",
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}",
                f"Продолжительность: {slot.excursion.base_duration_minutes if slot.excursion else '?'} минут",
                f"Макс. людей: {slot.max_people} человек",
                f"Макс. вес: {slot.max_weight} кг",
                f"Текущий вес: {current_weight} кг",
                f"Доступный вес: {max(0, slot.max_weight - current_weight)} кг",
                f"Свободные места: {slot.max_people - booked_places}/{slot.max_people}",
                f"Статус: {slot.status.value}"
            ]

            if slot.captain:
                response_lines.extend([
                    f"",
                    f"Капитан: {slot.captain.full_name}",
                    f"Телефон: {slot.captain.phone_number}"
                ])
                if slot.captain.email:
                    response_lines.append(f"Email: {slot.captain.email}")
            else:
                response_lines.append(f"Капитан: не назначен")

            if hasattr(slot, 'bookings') and slot.bookings:
                response_lines.extend([
                    f"",
                    f"Бронирования ({len(slot.bookings)}):"
                ])
                if active_bookings:
                    response_lines.append(f"Активные: {len(active_bookings)}")
                    for booking in active_bookings[:10]:
                        client = booking.adult_user if hasattr(booking, 'adult_user') else None
                        if client:
                            response_lines.append(f"• {client.full_name}: {booking.adults_count}+{booking.children_count}")
                    if len(active_bookings) > 10:
                        response_lines.append(f"... и еще {len(active_bookings) - 10}")
                else:
                    response_lines.append("Активных бронирований нет")

                status_counts = {}
                for booking in slot.bookings:
                    status = booking.booking_status.value
                    status_counts[status] = status_counts.get(status, 0) + 1
                if status_counts:
                    response_lines.extend([f"", "Статистика бронирований:"])
                    for status, count in status_counts.items():
                        response_lines.append(f"{status}: {count}")

            await callback.message.answer("\n".join(response_lines))
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slot_actions_menu(slot_id)
            )

    except Exception as e:
        logger.error(f"Ошибка показа деталей слота {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при получении информации о слотe",
            reply_markup=excursions_submenu()
        )

@router.callback_query(F.data.startswith("manage_date_slots:"))
async def manage_date_slots_callback(callback: CallbackQuery):
    """Управление слотами на конкретную дату"""
    try:
        await callback.answer()
        date_str = callback.data.split(":")[1]
        logger.info(f"Администратор {callback.from_user.id} выбрал управление слотом на дату {date_str}")
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with async_session() as session:
            slot_repo = SlotRepository(session)
            slots = await slot_repo.get_for_date(target_date)

            if not slots:
                await callback.message.answer(
                    f"На {target_date.strftime('%d.%m.%Y')} больше нет слотов."
                )
                return

            response = f"Слоты на {target_date.strftime('%d.%m.%Y')}:\n\n"
            for slot in slots:
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная"
                response += f"• {slot.start_datetime.strftime('%H:%M')} - {excursion_name} (ID: {slot.id})\n"

            await callback.message.answer(response)
            await callback.message.answer(
                "Выберите слот для управления:",
                reply_markup=schedule_date_management_menu(slots, target_date)
            )

    except Exception as e:
        logger.error(f"Ошибка управления слотами на дату: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )


# ===== ПЕРЕНОС СЛОТА НА НОВЫЕ ДАТУ/ВРЕМЯ =====


@router.callback_query(F.data.startswith("reschedule_slot:"))
async def reschedule_slot_callback(callback: CallbackQuery, state: FSMContext):
    """Начало переноса слота"""
    slot_id = int(callback.data.split(":")[1])

    try:
        await callback.answer()
        await state.update_data(slot_id=slot_id)
        await state.set_state(RescheduleSlot.waiting_for_new_datetime)

        await callback.message.answer(
            "Введите новую дату и время для слота в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 15.01.2024 14:30\n\n"
            "Или /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка начала переноса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.message(RescheduleSlot.waiting_for_new_datetime)
async def handle_reschedule_datetime(message: Message, state: FSMContext):
    """Обработка ввода новой даты/времени для переноса"""
    try:
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer("Перенос отменен.")
            return

        try:
            parts = message.text.strip().split()
            if len(parts) != 2:
                await message.answer(
                    "Неверный формат. Введите дату и время через пробел:\n"
                    "ДД.ММ.ГГГГ ЧЧ:ММ\n"
                    "Например: 15.01.2024 14:30"
                )
                return
            date_str, time_str = parts

            try:
                date_obj = validate_slot_date(date_str)
                time_obj = validate_slot_time(time_str)
            except ValueError as e:
                await message.answer(str(e))
                return

            new_datetime = datetime.combine(date_obj, time_obj)

        except Exception as e:
            logger.error(f"Ошибка парсинга даты/времени: {e}")
            await message.answer(
                "Неверный формат. Введите:\n"
                "ДД.ММ.ГГГГ ЧЧ:ММ\n"
                "Например: 15.01.2024 14:30"
            )
            return

        if new_datetime < datetime.now():
            await message.answer("Нельзя перенести слот на прошедшее время.")
            return

        await state.update_data(new_datetime=new_datetime)
        await state.set_state(RescheduleSlot.waiting_for_confirmation)

        data = await state.get_data()
        slot_id = data['slot_id']

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data=f"confirm_reschedule_yes:{slot_id}"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data=f"confirm_reschedule_no:{slot_id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"Перенести слот #{slot_id} на {new_datetime.strftime('%d.%m.%Y %H:%M')}?\n\n"
            f"Все бронирования сохранятся.\n"
            f"Капитан останется прежним.",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка обработки даты переноса: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке даты",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("confirm_reschedule_"))
async def confirm_reschedule(callback: CallbackQuery, state: FSMContext):
    """Подтверждение переноса слота"""
    try:
        await callback.answer()

        parts = callback.data.split(":")
        action = parts[0]
        slot_id = int(parts[1])

        if action == "confirm_reschedule_no":
            await callback.message.answer("Перенос отменен.")
            await state.clear()
            return

        data = await state.get_data()
        new_datetime = data.get('new_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            await state.clear()
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)

                # Получаем информацию о слоте до переноса (для уведомлений)
                slot_info_before = await slot_manager.get_slot_full_info(slot_id)

                if not slot_info_before:
                    await callback.message.answer("Не удалось получить информацию о слоте.")
                    return

                slot_before = slot_info_before['slot']
                old_datetime = slot_before.start_datetime

                # Переносим слот
                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
                    if "Конфликт" in error_message:
                        await state.update_data(
                            error_type="slot_conflict",
                            error_message=error_message,
                            retry_slot_id=slot_id,
                            retry_datetime=new_datetime
                        )
                        match = re.search(r'слотом #(\d+)', error_message)
                        if match:
                            conflict_slot_id = int(match.group(1))
                            await state.update_data(conflict_slot_id=conflict_slot_id)

                        await callback.message.answer(
                            f"{error_message}\n\n"
                            "Выберите действие:",
                            reply_markup=slots_conflict_keyboard(slot_id)
                        )
                    elif "Капитан" in error_message and "занят" in error_message:
                        await state.update_data(
                            error_type="captain_busy",
                            error_message=error_message,
                            retry_slot_id=slot_id,
                            retry_datetime=new_datetime
                        )
                        await callback.message.answer(
                            f"{error_message}\n\n"
                            "Выберите действие:",
                            reply_markup=captain_conflict_keyboard(slot_id)
                        )
                    else:
                        await callback.message.answer(
                            f"Не удалось перенести слот.\n"
                            f"Причина: {error_message}\n\n"
                            "Попробуйте ввести другое время."
                        )
                        await state.set_state(RescheduleSlot.waiting_for_new_datetime)
                        await callback.message.answer(
                            "Введите новую дату и время (ДД.ММ.ГГГГ ЧЧ:ММ):"
                        )
                    return

                # Уведомляем клиентов о переносе
                notified_count = 0
                failed_notifications = []
                no_telegram_clients = []

                # Используем активные бронирования из slot_info_before
                active_bookings = slot_info_before.get('active_bookings', [])

                if active_bookings:
                    logger.info(f"Слот {slot_id} перенесен. Активных бронирований для уведомления: {len(active_bookings)}")

                    bot = callback.bot
                    old_datetime_str = old_datetime.strftime('%d.%m.%Y %H:%M')
                    new_datetime_str = new_datetime.strftime('%d.%m.%Y %H:%M')
                    excursion_name = slot_before.excursion.name if slot_before.excursion else "Экскурсия"

                    for booking in active_bookings:
                        # Получаем клиента из бронирования
                        client = booking.adult_user

                        if client and client.telegram_id:
                            try:
                                # Формируем текст уведомления
                                notification_text = [
                                    "ПЕРЕНОС ЭКСКУРСИИ",
                                    "",
                                    f"Уважаемый клиент, время проведения экскурсии изменено:",
                                    f"",
                                    f"Экскурсия: {excursion_name}",
                                    f"Было запланировано: {old_datetime_str}",
                                    f"Перенесено на: {new_datetime_str}",
                                    f"",
                                    f"Приносим извинения за возможные неудобства."
                                ]

                                # Добавляем информацию о детях, если они есть
                                if booking.booking_children:
                                    children_names = []
                                    for bc in booking.booking_children:
                                        if bc.child and bc.child.full_name:
                                            children_names.append(bc.child.full_name)

                                    if children_names:
                                        notification_text.insert(5, f"Дети: {', '.join(children_names)}")

                                await bot.send_message(
                                    chat_id=client.telegram_id,
                                    text="\n".join(notification_text)
                                )

                                notified_count += 1
                                logger.info(f"Уведомление о переносе отправлено клиенту {client.telegram_id} (бронь #{booking.id})")

                            except Exception as e:
                                error_msg = f"Ошибка отправки уведомления клиенту {client.telegram_id} (бронь #{booking.id}): {e}"
                                logger.error(error_msg, exc_info=True)
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                                failed_notifications.append(client_info)
                        else:
                            # Клиент без telegram_id
                            if client:
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                            else:
                                client_info = "Клиент не найден"
                            no_telegram_clients.append(client_info)

                # Уведомляем капитана, если он назначен
                captain_notification_status = ""
                if slot_before.captain_id:
                    try:
                        captain = await slot_manager.user_repo.get_by_id(slot_before.captain_id)
                        if captain and captain.telegram_id:
                            captain_text = [
                                "ПЕРЕНОС ЭКСКУРСИИ",
                                "",
                                f"Уважаемый {captain.full_name}, время проведения экскурсии изменено:",
                                f"",
                                f"Экскурсия: {excursion_name}",
                                f"Было запланировано: {old_datetime_str}",
                                f"Перенесено на: {new_datetime_str}",
                                f"",
                                f"Пожалуйста, скорректируйте свои планы."
                            ]

                            await bot.send_message(
                                chat_id=captain.telegram_id,
                                text="\n".join(captain_text)
                            )
                            captain_notification_status = "Капитан уведомлен"
                            logger.info(f"Уведомление о переносе отправлено капитану {captain.telegram_id}")
                        elif captain and not captain.telegram_id:
                            captain_notification_status = "У капитана нет Telegram ID"
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления капитану: {e}", exc_info=True)
                        captain_notification_status = "Ошибка уведомления капитана"

                # Формируем ответ администратору
                response_parts = [
                    f"Слот #{slot_id} успешно перенесен.",
                    f"Новое время: {new_datetime_str}"
                ]

                if notified_count > 0:
                    response_parts.append(f"")
                    response_parts.append(f"Уведомления клиентам отправлены: {notified_count}")

                if failed_notifications:
                    failed_unique = list(set(failed_notifications))
                    response_parts.append(f"")
                    response_parts.append(f"Не удалось отправить уведомления:")
                    for client_info in failed_unique:
                        response_parts.append(f"• {client_info}")

                if no_telegram_clients:
                    no_telegram_unique = list(set(no_telegram_clients))
                    response_parts.append(f"")
                    response_parts.append(f"Клиенты без Telegram ID:")
                    for client_info in no_telegram_unique:
                        response_parts.append(f"• {client_info}")

                if captain_notification_status:
                    response_parts.append(f"")
                    response_parts.append(f"{captain_notification_status}")

                await callback.message.answer("\n".join(response_parts))

                logger.info(f"Слот {slot_id} перенесен администратором {callback.from_user.id}. "
                          f"Уведомлено клиентов: {notified_count}")

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=schedule_exc_management_menu()
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка подтверждения переноса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при переносе слота",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("reschedule_new_time:"))
async def handle_new_time_request(callback: CallbackQuery, state: FSMContext):
    """Запрос нового времени при конфликте"""
    try:
        await callback.answer()

        slot_id = int(callback.data.split(":")[1])
        await state.update_data(slot_id=slot_id)

        await callback.message.answer(
            "Введите новую дату и время (ДД.ММ.ГГГГ ЧЧ:ММ):\n"
            "Например: 15.01.2024 14:30"
        )
        await state.set_state(RescheduleSlot.waiting_for_new_datetime)

    except Exception as e:
        logger.error(f"Ошибка запроса нового времени: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("show_conflict_slot:"))
async def show_conflict_slot(callback: CallbackQuery, state: FSMContext):
    """Показать информацию о конфликтном слоте"""
    try:
        await callback.answer()

        data = await state.get_data()
        conflict_slot_id = data.get('conflict_slot_id')
        slot_id = int(callback.data.split(":")[1])

        if not conflict_slot_id:
            await callback.message.answer("Информация о конфликте не найдена.")
            return

        async with async_session() as session:
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(conflict_slot_id)

            if slot_info:
                slot = slot_info['slot']
                booked_places = slot_info['booked_places']

                message_lines = [
                    f"Конфликтный слот #{slot.id}:",
                    f"Экскурсия: {slot.excursion.name if slot.excursion else 'Неизвестно'}",
                    f"Время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}",
                    f"Статус: {slot.status.value}",
                    f"Капитан: {slot.captain.full_name if slot.captain else 'не назначен'}",
                    f"Забронировано мест: {booked_places}/{slot.max_people}"
                ]

                await callback.message.answer("\n".join(message_lines))
            else:
                await callback.message.answer("Конфликтный слот не найден.")

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=slots_conflict_keyboard(slot_id)
        )

    except Exception as e:
        logger.error(f"Ошибка показа конфликтного слота: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("change_captain:"))
async def handle_change_captain(callback: CallbackQuery, state: FSMContext):
    """Начать процесс смены капитана при переносе"""
    try:
        await callback.answer()

        slot_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        new_datetime = data.get('retry_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            return

        async with async_session() as session:
            slot_repo = SlotRepository(session)
            excursion_repo = ExcursionRepository(session)
            user_repo = UserRepository(session)

            slot = await slot_repo.get_by_id(slot_id)
            if not slot:
                await callback.message.answer("Слот не найден.")
                return

            excursion = await excursion_repo.get_by_id(slot.excursion_id)
            if not excursion:
                await callback.message.answer("Экскурсия не найдена.")
                return

            new_end_datetime = new_datetime + timedelta(
                minutes=excursion.base_duration_minutes
            )

            available_captains = await user_repo.get_available_captains(
                new_datetime,
                new_end_datetime
            )

            await state.update_data(
                slot_id=slot_id,
                new_datetime=new_datetime,
                new_end_datetime=new_end_datetime,
                available_captains=[c.id for c in available_captains]
            )

            if available_captains:
                await callback.message.answer(
                    f"Доступные капитаны на {new_datetime.strftime('%d.%m.%Y %H:%M')}:",
                    reply_markup=captains_selection_menu(
                        item_id=slot_id,
                        captains=available_captains,
                        callback_prefix="select_captain_for_reschedule",
                        include_back=True,
                        back_callback=f"back_to_conflict_resolution:{slot_id}",
                        include_remove=False
                    )
                )
            else:
                await callback.message.answer(
                    "Нет свободных капитанов на указанное время.\n"
                    "Вы можете:\n"
                    "1. Выбрать другое время\n"
                    "2. Создать слот без капитана\n"
                    "3. Отменить перенос",
                    reply_markup=no_captains_options_menu(
                        slot_id=slot_id,
                        context="reschedule"
                    )
                )

    except Exception as e:
        logger.error(f"Ошибка смены капитана: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("select_captain_for_reschedule:"))
async def select_captain_for_reschedule(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора капитана при переносе слота"""
    data_parts = callback.data.split(":")
    slot_id = int(data_parts[1])
    captain_id = int(data_parts[2])

    logger.info(f"Выбран капитан {captain_id} для переноса слота {slot_id}")

    try:
        await callback.answer()

        data = await state.get_data()
        new_datetime = data.get('new_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            await state.clear()
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)
                user_repo = UserRepository(uow.session)

                # Получаем информацию о слоте до переноса (для уведомлений)
                slot_info_before = await slot_manager.get_slot_full_info(slot_id)

                if not slot_info_before:
                    await callback.message.answer("Не удалось получить информацию о слоте.")
                    return

                slot_before = slot_info_before['slot']
                old_datetime = slot_before.start_datetime
                old_captain_id = slot_before.captain_id

                available_captains = data.get('available_captains', [])
                if captain_id not in available_captains:
                    await callback.message.answer(
                        "Капитан больше не доступен на это время. Выберите другого капитана."
                    )
                    return

                # Переносим слот
                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
                    await callback.message.answer(
                        f"Не удалось перенести слот.\nПричина: {error_message}"
                    )
                    if "Конфликт" in error_message:
                        await state.update_data(
                            error_type="slot_conflict",
                            error_message=error_message
                        )
                        await callback.message.answer(
                            "Выберите действие:",
                            reply_markup=slots_conflict_keyboard(slot_id)
                        )
                    else:
                        await callback.message.answer("Попробуйте ввести другое время:")
                        await state.set_state(RescheduleSlot.waiting_for_new_datetime)
                    return

                # Назначаем нового капитана
                captain_assigned = await slot_manager.slot_repo.assign_captain(slot_id, captain_id)

                # Получаем информацию о новом капитане
                new_captain = await user_repo.get_by_id(captain_id)
                new_captain_name = new_captain.full_name if new_captain else f"ID {captain_id}"

                # Уведомляем клиентов о переносе
                notified_clients = []
                failed_client_notifications = []
                no_telegram_clients = []

                # Используем активные бронирования из slot_info_before
                active_bookings = slot_info_before.get('active_bookings', [])

                if active_bookings:
                    logger.info(f"Слот {slot_id} перенесен. Активных бронирований для уведомления: {len(active_bookings)}")

                    bot = callback.bot
                    old_datetime_str = old_datetime.strftime('%d.%m.%Y %H:%M')
                    new_datetime_str = new_datetime.strftime('%d.%m.%Y %H:%M')
                    excursion_name = slot_before.excursion.name if slot_before.excursion else "Экскурсия"

                    for booking in active_bookings:
                        client = booking.adult_user

                        if client and client.telegram_id:
                            try:
                                notification_text = [
                                    "ПЕРЕНОС ЭКСКУРСИИ",
                                    "",
                                    f"Уважаемый клиент, время проведения экскурсии изменено:",
                                    f"",
                                    f"Экскурсия: {excursion_name}",
                                    f"Было запланировано: {old_datetime_str}",
                                    f"Перенесено на: {new_datetime_str}",
                                    f"",
                                    f"Приносим извинения за возможные неудобства."
                                ]

                                if booking.booking_children:
                                    children_names = []
                                    for bc in booking.booking_children:
                                        if bc.child and bc.child.full_name:
                                            children_names.append(bc.child.full_name)

                                    if children_names:
                                        notification_text.insert(5, f"Дети: {', '.join(children_names)}")

                                await bot.send_message(
                                    chat_id=client.telegram_id,
                                    text="\n".join(notification_text)
                                )

                                notified_clients.append(client.full_name or client.phone_number or f"ID {client.id}")
                                logger.info(f"Уведомление о переносе отправлено клиенту {client.telegram_id} (бронь #{booking.id})")

                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления клиенту {client.telegram_id}: {e}")
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                                failed_client_notifications.append(client_info)
                        else:
                            if client:
                                client_info = client.full_name or client.phone_number or f"ID {client.id}"
                                no_telegram_clients.append(client_info)

                # Уведомления капитанам
                captain_notifications = []

                # Уведомляем старого капитана (если был)
                if old_captain_id and old_captain_id != captain_id:
                    old_captain = await user_repo.get_by_id(old_captain_id)
                    if old_captain and old_captain.telegram_id:
                        try:
                            old_captain_text = [
                                "ОТМЕНА НАЗНАЧЕНИЯ",
                                "",
                                f"Уважаемый {old_captain.full_name}, ваше назначение на экскурсию отменено:",
                                f"",
                                f"Экскурсия: {excursion_name}",
                                f"Ранее запланированное время: {old_datetime_str}",
                                f"",
                                f"Экскурсия перенесена на другое время и назначен другой капитан."
                            ]

                            await bot.send_message(
                                chat_id=old_captain.telegram_id,
                                text="\n".join(old_captain_text)
                            )
                            captain_notifications.append(f"Старый капитан {old_captain.full_name} уведомлен")
                            logger.info(f"Уведомление об отмене отправлено старому капитану {old_captain.telegram_id}")
                        except Exception as e:
                            logger.error(f"Ошибка уведомления старого капитана: {e}")
                            captain_notifications.append(f"Ошибка уведомления старого капитана {old_captain.full_name}")
                    elif old_captain and not old_captain.telegram_id:
                        captain_notifications.append(f"У старого капитана {old_captain.full_name} нет Telegram ID")

                # Уведомляем нового капитана
                if new_captain and new_captain.telegram_id:
                    try:
                        # Получаем информацию о слоте после переноса
                        slot_info_after = await slot_manager.get_slot_full_info(slot_id)
                        booked_places = slot_info_after.get('booked_places', 0) if slot_info_after else 0
                        current_weight = slot_info_after.get('current_weight', 0) if slot_info_after else 0

                        new_captain_text = [
                            "НАЗНАЧЕНИЕ НА ЭКСКУРСИЮ (ПЕРЕНОС)",
                            "",
                            f"Уважаемый {new_captain.full_name}, вы назначены капитаном на перенесенную экскурсию:",
                            f"",
                            f"Экскурсия: {excursion_name}",
                            f"Дата и время: {new_datetime_str}",
                            f"",
                            f"Информация о слоте:",
                            f"• Всего мест: {slot_before.max_people}",
                            f"• Забронировано мест: {booked_places}",
                            f"• Максимальный вес: {slot_before.max_weight} кг",
                            f"• Текущий вес: {current_weight} кг",
                            f"",
                            f"Пожалуйста, будьте готовы провести экскурсию."
                        ]

                        await bot.send_message(
                            chat_id=new_captain.telegram_id,
                            text="\n".join(new_captain_text)
                        )
                        captain_notifications.append(f"Новый капитан {new_captain.full_name} уведомлен")
                        logger.info(f"Уведомление о назначении отправлено новому капитану {new_captain.telegram_id}")
                    except Exception as e:
                        logger.error(f"Ошибка уведомления нового капитана: {e}")
                        captain_notifications.append(f"Ошибка уведомления нового капитана {new_captain.full_name}")
                elif new_captain and not new_captain.telegram_id:
                    captain_notifications.append(f"У нового капитана {new_captain.full_name} нет Telegram ID")

                # Формируем ответ администратору
                response_parts = [
                    f"Слот #{slot_id} успешно перенесен.",
                    f"Новое время: {new_datetime_str}",
                    f"Новый капитан: {new_captain_name}"
                ]

                if captain_notifications:
                    response_parts.append(f"")
                    response_parts.append(f"Уведомления капитанам:")
                    for notification in captain_notifications:
                        response_parts.append(f"  • {notification}")

                if notified_clients:
                    response_parts.append(f"")
                    response_parts.append(f"Уведомления клиентам отправлены ({len(notified_clients)}):")
                    for client_info in notified_clients:
                        response_parts.append(f"  • {client_info}")

                if failed_client_notifications:
                    response_parts.append(f"")
                    response_parts.append(f"Не удалось отправить уведомления клиентам ({len(failed_client_notifications)}):")
                    for client_info in failed_client_notifications:
                        response_parts.append(f"  • {client_info}")

                if no_telegram_clients:
                    response_parts.append(f"")
                    response_parts.append(f"Клиенты без Telegram ID (уведомления не отправлены, {len(no_telegram_clients)}):")
                    for client_info in no_telegram_clients:
                        response_parts.append(f"  • {client_info}")

                await callback.message.answer("\n".join(response_parts))

                logger.info(f"Слот {slot_id} перенесен администратором {callback.from_user.id}. "
                          f"Новый капитан: {captain_id}, уведомлено клиентов: {len(notified_clients)}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при выборе капитана для переноса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("back_to_conflict_resolution:"))
async def back_to_conflict_resolution(callback: CallbackQuery, state: FSMContext):
    """Возврат к меню разрешения конфликта"""
    try:
        await callback.answer()

        slot_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        error_type = data.get('error_type')

        if error_type == "slot_conflict":
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slots_conflict_keyboard(slot_id)
            )
        elif error_type == "captain_busy":
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=captain_conflict_keyboard(slot_id)
            )
        else:
            await callback.message.answer(
                "Возникла ошибка. Попробуйте ввести другое время:"
            )
            await state.set_state(RescheduleSlot.waiting_for_new_datetime)

    except Exception as e:
        logger.error(f"Ошибка возврата к разрешению конфликта: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("show_available_captains:"))
async def show_available_captains(callback: CallbackQuery, state: FSMContext):
    """Показать свободных капитанов"""
    try:
        await callback.answer()

        slot_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        new_datetime = data.get('retry_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            return

        async with async_session() as session:
            slot_repo = SlotRepository(session)
            excursion_repo = ExcursionRepository(session)
            user_repo = UserRepository(session)

            slot = await slot_repo.get_by_id(slot_id)
            if not slot:
                await callback.message.answer("Слот не найден.")
                return

            excursion = await excursion_repo.get_by_id(slot.excursion_id)
            if not excursion:
                await callback.message.answer("Экскурсия не найдена.")
                return

            new_end_datetime = new_datetime + timedelta(
                minutes=excursion.base_duration_minutes
            )

            available_captains = await user_repo.get_available_captains(
                new_datetime, new_end_datetime
            )

            if available_captains:
                captains_list = "\n".join(
                    f"• {captain.full_name} (ID: {captain.id}) - {captain.phone_number}"
                    for captain in available_captains[:10]
                )
                message = (
                    f"Свободные капитаны на {new_datetime.strftime('%d.%m.%Y %H:%M')}:\n\n"
                    f"{captains_list}\n\n"
                )
                if len(available_captains) > 10:
                    message += f"И еще {len(available_captains) - 10} капитанов...\n\n"
                message += "Для назначения используйте меню 'Назначить другого капитана'"

                await callback.message.answer(message)
                # Показываем меню снова
                await callback.message.answer(
                        "Выберите действие:",
                        reply_markup=captain_conflict_keyboard(slot_id)
                )
            else:
                await callback.message.answer(
                    "Нет свободных капитанов на это время.",
                    reply_markup=no_captains_options_menu(
                        slot_id=slot_id,
                        context="reschedule"
                    )
                )

    except Exception as e:
        logger.error(f"Ошибка показа свободных капитанов: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("reschedule_without_captain:"))
async def reschedule_without_captain(callback: CallbackQuery, state: FSMContext):
    """Перенос слота без капитана"""
    try:
        await callback.answer()

        slot_id = int(callback.data.split(":")[1])
        logger.info(f"Админ {callback.from_user.id} переносит слот {slot_id} без капитана")
        data = await state.get_data()
        new_datetime = data.get('retry_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            await state.clear()
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_repo = SlotRepository(uow.session)
                user_repo = UserRepository(uow.session)
                slot_manager = SlotManager(uow.session)

                slot = await slot_repo.get_by_id(slot_id)
                if not slot:
                    await callback.message.answer("Слот не найден.")
                    await state.clear()
                    return

                original_captain_id = slot.captain_id
                captain_was_assigned = original_captain_id is not None
                captain_name = ""
                captain_notification_status = ""

                # Получаем информацию об экскурсии для уведомления
                excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
                old_datetime_str = slot.start_datetime.strftime('%d.%m.%Y %H:%M')
                new_datetime_str = new_datetime.strftime('%d.%m.%Y %H:%M')

                if captain_was_assigned:
                    captain = await user_repo.get_by_id(original_captain_id)
                    captain_name = captain.full_name if captain else f"ID {original_captain_id}"

                    await slot_repo.assign_captain(slot_id, None)

                    if captain and captain.telegram_id:
                        try:
                            notification_text = [
                                "ОТМЕНА НАЗНАЧЕНИЯ",
                                "",
                                f"Уважаемый {captain.full_name}, ваше назначение на экскурсию отменено:",
                                f"",
                                f"Экскурсия: {excursion_name}",
                                f"Дата и время: {old_datetime_str}",
                                f"",
                                f"Причина: перенос экскурсии на другое время.",
                                f"Новое время: {new_datetime_str}",
                                f"",
                                f"Экскурсия будет проведена с другим капитаном либо вас переназначат."
                            ]

                            await callback.bot.send_message(
                                chat_id=captain.telegram_id,
                                text="\n".join(notification_text)
                            )

                            captain_notification_status = f"Капитан {captain_name} уведомлен об отмене"
                            logger.info(f"Уведомление об отмене отправлено капитану {captain.telegram_id} (слот #{slot_id})")

                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления капитану {captain.telegram_id}: {e}", exc_info=True)
                            captain_notification_status = f"Ошибка уведомления капитана {captain_name}"
                    else:
                        captain_notification_status = f"У капитана {captain_name} нет Telegram ID"

                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
                    # Если не удалось перенести, капитана уже сняли - он остается снятым
                    # Но сообщаем админу об ошибке
                    await callback.message.answer(
                        f"Не удалось перенести слот. Капитан был снят.\n"
                        f"Причина: {error_message}\n\n"
                        f"Назначьте нового капитана или попробуйте другое время.",
                        reply_markup=schedule_exc_management_menu()
                    )
                    return

                # Формируем ответ администратору
                response_parts = [
                    f"Слот #{slot_id} перенесен на {new_datetime_str}"
                ]

                if captain_was_assigned:
                    response_parts.append(f"")
                    response_parts.append(f"Капитан {captain_name} был снят со слота.")
                    if captain_notification_status:
                        response_parts.append(f"{captain_notification_status}")
                    response_parts.append(f"Назначьте нового капитана, если нужно.")
                else:
                    response_parts.append(f"Слот перенесен без капитана.")

                await callback.message.answer(
                    "\n".join(response_parts),
                    reply_markup=schedule_exc_management_menu()
                )

            await state.clear()

    except Exception as e:
        logger.error(f"Ошибка переноса слота без капитана {slot_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при переносе",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("cancel_reschedule:"))
async def cancel_reschedule_process(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса переноса"""
    try:
        logger.info(f"Админ {callback.from_user.id} отменяет процесс переноса слота")
        await callback.answer()
        await state.clear()
        await callback.message.answer("Перенос отменен.")
    except Exception as e:
        logger.error(f"Ошибка отмены переноса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()
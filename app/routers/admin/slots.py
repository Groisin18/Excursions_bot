from aiogram import F, Router
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.admin_panel.states_adm import RescheduleSlot
from app.database.requests import DatabaseManager
from app.database.models import async_session, SlotStatus, BookingStatus
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu,
    slot_actions_menu, slots_conflict_keyboard,
    captains_selection_menu, slot_action_confirmation_menu,
    no_captains_options_menu, captain_conflict_keyboard,
    schedule_date_management_menu
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_admin_logger


router = Router(name="admin_slots")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = get_admin_logger()


# ===== УПРАВЛЕНИЕ СЛОТОМ =====


@router.callback_query(F.data.startswith("cancel_slot:"))
async def cancel_slot_callback(callback: CallbackQuery):
    """Отмена слота"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет отменить слот {slot_id}")

    try:
        await callback.answer()

        # Используем универсальную клавиатуру
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
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data.startswith("confirm_cancel_slot:"))
async def confirm_cancel_slot_callback(callback: CallbackQuery):
    """Подтверждение отмены слота"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} подтвердил отмену слота {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_slot_status(slot_id, SlotStatus.cancelled)

            if success:
                slot = await db_manager.get_slot_with_bookings(slot_id)

                # Уведомляем клиентов о отмене
                if slot and slot.bookings:
                    logger.info(f"Слот {slot_id} отменен. Бронирований для отмены: {len(slot.bookings)}")
                    # TODO: Добавить уведомления клиентам

                await callback.message.answer(
                    f"Слот #{slot_id} успешно отменен.\n"
                    f"Все связанные бронирования отменены."
                )

                logger.info(f"Слот {slot_id} отменен администратором {callback.from_user.id}")
            else:
                await callback.message.answer("Не удалось отменить слот.")

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=schedule_exc_management_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка отмены слота {slot_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при отмене слота")

@router.callback_query(F.data.startswith("assign_captain:"))
async def assign_captain_callback(callback: CallbackQuery):
    """Назначение капитана на слот"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет назначить капитана на слот {slot_id}")

    try:
        await callback.answer()

        # Получаем список капитанов
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            captains = await db_manager.get_all_captains()

            if not captains:
                await callback.message.answer(
                    "Нет доступных капитанов. Сначала добавьте капитанов через меню 'Капитаны'."
                )
                return

            # Используем универсальную клавиатуру из keyboards_adm.py
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
        await callback.message.answer("Произошла ошибка")

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
            db_manager = DatabaseManager(session)

            # Назначаем капитана на слот
            success = await db_manager.assign_captain_to_slot(slot_id, captain_id)

            if success:
                # Получаем обновленную информацию о слотe
                slot = await db_manager.get_slot_with_bookings(slot_id)
                captain = await db_manager.get_user_by_id(captain_id)

                if slot and captain:
                    await callback.message.answer(
                        f"Капитан успешно назначен!\n\n"
                        f"Слот: #{slot_id}\n"
                        f"Капитан: {captain.full_name}\n"
                        f"Телефон: {captain.phone_number}\n\n"
                        f"Капитан будет уведомлен о назначении."
                    )

                    # TODO: Добавить уведомление капитану
                else:
                    await callback.message.answer("Капитан назначен, но не удалось получить детальную информацию.")
            else:
                await callback.message.answer("Не удалось назначить капитана.")

        # Возвращаемся к управлению слотом
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=slot_actions_menu(slot_id)
        )

    except Exception as e:
        logger.error(f"Ошибка назначения капитана {captain_id} на слот {slot_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при назначении капитана")

@router.callback_query(F.data == "manage_slots")
async def manage_slots_callback(callback: CallbackQuery):
    """Управление слотами"""
    logger.info(f"Администратор {callback.from_user.id} открыл управление слотами")

    try:
        await callback.answer()

        # Получаем слоты на ближайшие 3 дня для управления
        date_from = datetime.now()
        date_to = date_from + timedelta(days=3)

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайшие 3 дня нет слотов для управления.\n"
                    "Вы можете добавить новые слоты через меню 'Добавить в расписание'."
                )
                return

            # Показываем меню выбора слота
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            builder = InlineKeyboardBuilder()
            for slot in slots:
                excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
                excursion_name = excursion.name if excursion else "Неизвестная"

                builder.button(
                    text=f"{slot.start_datetime.strftime('%d.%m %H:%M')} - {excursion_name}",
                    callback_data=f"manage_slot:{slot.id}"
                )

            builder.button(
                text="Назад",
                callback_data="back_to_schedule_menu"
            )
            builder.adjust(1)

            await callback.message.answer(
                "Выберите слот для управления:",
                reply_markup=builder.as_markup()
            )

    except Exception as e:
        logger.error(f"Ошибка открытия управления слотами: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data.startswith("manage_slot:"))
async def manage_slot_callback(callback: CallbackQuery):
    """Управление конкретным слотом"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} управляет слотом {slot_id}")

    try:
        await callback.answer()

        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Используем существующий метод с предзагрузкой
            slot = await db_manager.get_slot_with_bookings(slot_id)

            if not slot:
                await callback.message.answer(f"Слот {slot_id} не найден.")
                return

            # Проверяем, что excursion загружен
            if not slot.excursion:
                # На всякий случай загружаем
                slot.excursion = await db_manager.get_excursion_by_id(slot.excursion_id)

            excursion = slot.excursion
            response = (
                f"Управление слотом #{slot.id}\n\n"
                f"Экскурсия: {excursion.name if excursion else 'Неизвестно'}\n"
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"Продолжительность: {excursion.base_duration_minutes if excursion else '?'} мин.\n"
                f"Количество свободных мест: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}/{slot.max_people}\n"
                f"Занятость по максимально допустимому весу: {await db_manager.get_current_weight_for_slot(slot.id)}/{slot.max_weight}\n"
                f"Статус: {slot.status.value}\n"
            )

            # Информация о капитане (уже предзагружен)
            if slot.captain:
                response += f"Капитан: {slot.captain.full_name}\n"
            else:
                response += "Капитан: не назначен\n"

            # Информация о бронированиях (уже предзагружены)
            if slot.bookings:
                active_bookings = [b for b in slot.bookings if b.booking_status == BookingStatus.active]
                response += f"\nАктивных бронирований: {len(active_bookings)}\n"
                if active_bookings:
                    response += f"Бронирования:\n"
                    for booking in active_bookings[:5]:  # Показываем первые 5
                        client = booking.client
                        if client:
                            response += (
                                f"• {client.full_name} "
                                f"({booking.adults_count}+{booking.children_count})\n"
                            )
                    if len(active_bookings) > 5:
                        response += f"... и еще {len(active_bookings) - 5}\n"

            await callback.message.answer(response)

            # Используем клавиатуру из keyboards_adm.py
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slot_actions_menu(slot_id)
            )

    except Exception as e:
        logger.error(f"Ошибка управления слотом {slot_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при управлении слотом")

@router.callback_query(F.data.startswith("slot_details:"))
async def show_slot_details(callback: CallbackQuery):
    """Показать детальную информацию о слотe"""
    slot_id = int(callback.data.split(":")[1])

    try:
        await callback.answer()

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slot = await db_manager.get_slot_with_bookings(slot_id)

            if not slot:
                await callback.message.answer(f"Слот {slot_id} не найден.")
                return

            excursion = slot.excursion
            response = (
                f"Детальная информация о слотe #{slot.id}\n\n"
                f"Экскурсия: {excursion.name}\n"
                f"Описание: {excursion.description}\n"
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"Продолжительность: {excursion.base_duration_minutes} минут\n"
                f"Макс. людей: {slot.max_people} человек\n"
                f"Макс. вес: {slot.max_weight} кг\n"
                f"Текущий вес: {await db_manager.get_current_weight_for_slot(slot.id)} кг\n"
                f"Доступный вес: {max(0, slot.max_weight - await db_manager.get_current_weight_for_slot(slot.id))} кг\n"
                f"Свободные места: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}\n"
                f"Статус: {slot.status.value}\n"
            )

            # Информация о капитане
            if slot.captain:
                response += f"\nКапитан: {slot.captain.full_name}\n"
                response += f"Телефон: {slot.captain.phone_number}\n"
                if slot.captain.email:
                    response += f"Email: {slot.captain.email}\n"
            else:
                response += "\nКапитан: не назначен\n"

            # Информация о бронированиях
            if slot.bookings:
                response += f"\nБронирования ({len(slot.bookings)}):\n"

                active_bookings = [b for b in slot.bookings if b.booking_status == BookingStatus.active]
                if active_bookings:
                    response += f"Активные: {len(active_bookings)}\n"
                    for booking in active_bookings[:10]:  # Показываем первые 10
                        client = booking.client
                        response += f"• {client.full_name}: {booking.adults_count}+{booking.children_count}\n"

                    if len(active_bookings) > 10:
                        response += f"... и еще {len(active_bookings) - 10}\n"
                else:
                    response += "Активных бронирований нет\n"

                # Статистика по статусам
                status_counts = {}
                for booking in slot.bookings:
                    status = booking.booking_status.value
                    status_counts[status] = status_counts.get(status, 0) + 1

                if status_counts:
                    response += "\nСтатистика бронирований:\n"
                    for status, count in status_counts.items():
                        response += f"{status}: {count}\n"

            await callback.message.answer(response)

            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slot_actions_menu(slot_id)
            )

    except Exception as e:
        logger.error(f"Ошибка показа деталей слота {slot_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при получении информации о слотe")

@router.callback_query(F.data.startswith("manage_date_slots:"))
async def manage_date_slots_callback(callback: CallbackQuery):
    '''Управление слотами на конкретную дату'''
    try:
        await callback.answer()
        date_str = callback.data.split(":")[1]
        logger.info(f"Администратор {callback.from_user.id} выбрал управление слотом на дату {date_str}")
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Используем метод с предзагрузкой
            slots = await db_manager.get_slots_for_date_with_excursion(target_date)

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
        await callback.message.answer("Произошла ошибка")


# ===== ПЕРЕНОС СЛОТА НА НОВЫЕ ДАТУ/ВРЕМЯ =====


@router.callback_query(F.data.startswith("reschedule_slot:"))
async def reschedule_slot_callback(callback: CallbackQuery, state: FSMContext):
    """Начало переноса слота"""
    slot_id = int(callback.data.split(":")[1])

    try:
        await callback.answer()

        # Сохраняем ID слота в состоянии
        await state.update_data(slot_id=slot_id)
        await state.set_state(RescheduleSlot.waiting_for_new_datetime)

        await callback.message.answer(
            "Введите новую дату и время для слота в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 15.01.2024 14:30\n\n"
            "Или /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка начала переноса: {e}")
        await callback.message.answer("Произошла ошибка")

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

            from app.utils.validation import Validators

            try:
                date_obj = Validators.validate_slot_date(date_str)
                time_obj = Validators.validate_slot_time(time_str)
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
        await message.answer("Произошла ошибка при обработке даты")

@router.callback_query(F.data.startswith("confirm_reschedule_"))
async def confirm_reschedule(callback: CallbackQuery, state: FSMContext):
    """Подтверждение переноса слота"""
    try:
        await callback.answer()

        parts = callback.data.split(":")
        action = parts[0]  # "confirm_reschedule_yes" или "confirm_reschedule_no"
        slot_id = int(parts[1])

        # Если "нет" - отмена
        if action == "confirm_reschedule_no":
            await callback.message.answer("Перенос отменен.")
            await state.clear()
            return

        # Если "да" - продолжаем
        data = await state.get_data()
        new_datetime = data.get('new_datetime')

        if not new_datetime:
            await callback.message.answer("Ошибка: время не указано.")
            await state.clear()
            return

        async with async_session() as session:
            db_manager = DatabaseManager(session)

            success, error_message = await db_manager.reschedule_slot(slot_id, new_datetime)

            if success:
                await callback.message.answer(
                    f"Слот #{slot_id} успешно перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=schedule_exc_management_menu()
                )
                # TODO: Отправить уведомления клиентам
                await state.clear()
            else:
                if "Конфликт" in error_message:
                    # Сохраняем данные для выбора решения
                    await state.update_data(
                        error_type="slot_conflict",
                        error_message=error_message,
                        retry_slot_id=slot_id,
                        retry_datetime=new_datetime
                    )

                    # Извлекаем ID конфликтного слота из сообщения
                    import re
                    match = re.search(r'слотом #(\d+)', error_message)
                    if match:
                        conflict_slot_id = int(match.group(1))
                        await state.update_data(conflict_slot_id=conflict_slot_id)

                    await callback.message.answer(
                        f"{error_message}\n\n"
                        "Выберите действие:\n"
                        "1. Ввести другое время\n"
                        "2. Просмотреть информацию о конфликтном слоте\n"
                        "3. Отменить перенос",
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
                        "Выберите действие:\n"
                        "1. Ввести другое время\n"
                        "2. Назначить другого капитана\n"
                        "3. Просмотреть свободных капитанов\n"
                        "4. Отменить перенос",
                        reply_markup=captain_conflict_keyboard(slot_id)
                    )
                else:
                    await callback.message.answer(
                        f"Не удалось перенести слот.\n"
                        f"Причина: {error_message}\n\n"
                        "Попробуйте ввести другое время."
                    )
                    # Возвращаем в состояние ввода времени
                    await state.set_state(RescheduleSlot.waiting_for_new_datetime)
                    await callback.message.answer(
                        "Введите новую дату и время (ДД.ММ.ГГГГ ЧЧ:ММ):"
                    )

    except Exception as e:
        logger.error(f"Ошибка подтверждения переноса: {e}")
        await callback.message.answer("Произошла ошибка при переносе слота")
        await state.clear()

@router.callback_query(F.data.startswith("reschedule_new_time:"))
async def handle_new_time_request(callback: CallbackQuery, state: FSMContext):
    """Запрос нового времени при конфликте"""
    await callback.answer()

    slot_id = int(callback.data.split(":")[1])
    await state.update_data(slot_id=slot_id)

    await callback.message.answer(
        "Введите новую дату и время (ДД.ММ.ГГГГ ЧЧ:ММ):\n"
        "Например: 15.01.2024 14:30"
    )
    await state.set_state(RescheduleSlot.waiting_for_new_datetime)

@router.callback_query(F.data.startswith("show_conflict_slot:"))
async def show_conflict_slot(callback: CallbackQuery, state: FSMContext):
    """Показать информацию о конфликтном слоте"""
    await callback.answer()

    data = await state.get_data()
    conflict_slot_id = data.get('conflict_slot_id')
    slot_id = int(callback.data.split(":")[1])

    if not conflict_slot_id:
        await callback.message.answer("Информация о конфликте не найдена.")
        return

    async with async_session() as session:
        db_manager = DatabaseManager(session)
        conflict_slot = await db_manager.get_slot_by_id(conflict_slot_id)

        if conflict_slot:
            excursion = await db_manager.get_excursion_by_id(conflict_slot.excursion_id)
            captain = await db_manager.get_user_by_id(conflict_slot.captain_id) if conflict_slot.captain_id else None

            message = (
                f"Конфликтный слот #{conflict_slot.id}:\n"
                f"Экскурсия: {excursion.name if excursion else 'Неизвестно'}\n"
                f"Время: {conflict_slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"Статус: {conflict_slot.status.value}\n"
            )

            if captain:
                message += f"Капитан: {captain.full_name}\n"

            booked_places = await db_manager.get_booked_places_for_slot(conflict_slot_id)
            message += f"Забронировано мест: {booked_places}/{conflict_slot.max_people}\n"

            await callback.message.answer(message)
        else:
            await callback.message.answer("Конфликтный слот не найден.")

    # Показываем клавиатуру снова
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=slots_conflict_keyboard(slot_id)
    )

@router.callback_query(F.data.startswith("change_captain:"))
async def handle_change_captain(callback: CallbackQuery, state: FSMContext):
    """Начать процесс смены капитана при переносе"""
    await callback.answer()

    slot_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    new_datetime = data.get('retry_datetime')

    if not new_datetime:
        await callback.message.answer("Ошибка: время не указано.")
        return

    async with async_session() as session:
        db_manager = DatabaseManager(session)

        slot = await db_manager.get_slot_by_id(slot_id)
        if not slot:
            await callback.message.answer("Слот не найден.")
            return

        excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
        if not excursion:
            await callback.message.answer("Экскурсия не найдена.")
            return

        new_end_datetime = new_datetime + timedelta(
            minutes=excursion.base_duration_minutes
        )
        available_captains = await db_manager.get_available_captains(
            new_datetime, new_end_datetime
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
                    callback_prefix="select_captain_for_reschedule",  # Новый префикс
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
                            context="reschedule")
            )

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
            db_manager = DatabaseManager(session)

            # Проверяем, что капитан все еще доступен
            available_captains = data.get('available_captains', [])
            if captain_id not in available_captains:
                await callback.message.answer(
                    "Капитан больше не доступен на это время. Выберите другого капитана."
                )
                return

            # Переносим слот с новым капитаном
            success, error_message = await db_manager.reschedule_slot(slot_id, new_datetime)

            if success:
                # Назначаем капитана
                captain_assigned = await db_manager.assign_captain_to_slot(slot_id, captain_id)

                if captain_assigned:
                    captain = await db_manager.get_user_by_id(captain_id)
                    captain_name = captain.full_name if captain else f"ID {captain_id}"

                    await callback.message.answer(
                        f"Слот #{slot_id} успешно перенесен на "
                        f"{new_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Капитан: {captain_name}",
                        reply_markup=schedule_exc_management_menu()
                    )

                    # TODO: Отправить уведомления клиентам и капитану

                else:
                    await callback.message.answer(
                        f"Слот перенесен, но не удалось назначить капитана.",
                        reply_markup=schedule_exc_management_menu()
                    )

                await state.clear()

            else:
                # Если не удалось перенести, показываем ошибку
                await callback.message.answer(
                    f"Не удалось перенести слот.\n"
                    f"Причина: {error_message}"
                )

                # Предлагаем решения в зависимости от ошибки
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
                    await callback.message.answer(
                        "Попробуйте ввести другое время:"
                    )
                    await state.set_state(RescheduleSlot.waiting_for_new_datetime)

    except Exception as e:
        logger.error(f"Ошибка при выборе капитана для переноса: {e}")
        await callback.message.answer("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data.startswith("back_to_conflict_resolution:"))
async def back_to_conflict_resolution(callback: CallbackQuery, state: FSMContext):
    """Возврат к меню разрешения конфликта"""
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

@router.callback_query(F.data.startswith("show_available_captains:"))
async def show_available_captains(callback: CallbackQuery, state: FSMContext):
    """Показать свободных капитанов"""
    await callback.answer()

    slot_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    new_datetime = data.get('retry_datetime')

    if not new_datetime:
        await callback.message.answer("Ошибка: время не указано.")
        return

    async with async_session() as session:
        db_manager = DatabaseManager(session)

        slot = await db_manager.get_slot_by_id(slot_id)
        if not slot:
            await callback.message.answer("Слот не найден.")
            return

        excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
        if not excursion:
            await callback.message.answer("Экскурсия не найдена.")
            return

        new_end_datetime = new_datetime + timedelta(
            minutes=excursion.base_duration_minutes
        )

        available_captains = await db_manager.get_available_captains(
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
            await callback.message.answer("Нет свободных капитанов на это время.",
                                            reply_markup=no_captains_options_menu(
                                                slot_id=slot_id,
                                                context="reschedule"
                                            )
)

@router.callback_query(F.data.startswith("reschedule_without_captain:"))
async def reschedule_without_captain(callback: CallbackQuery, state: FSMContext):
    """Перенос слота без капитана"""
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
        db_manager = DatabaseManager(session)

        # Снимаем капитана перед переносом
        slot = await db_manager.get_slot_by_id(slot_id)
        captain_was_assigned = False
        captain_name = ""

        if slot and slot.captain_id:
            captain_was_assigned = True
            captain = await db_manager.get_user_by_id(slot.captain_id)
            captain_name = captain.full_name if captain else f"ID {slot.captain_id}"

            # Снимаем капитана
            await db_manager.assign_captain_to_slot(slot_id, None)

        # Теперь переносим слот (капитана нет - проверки не будет)
        success, error_message = await db_manager.reschedule_slot(slot_id, new_datetime)

        if success:
            if captain_was_assigned:
                await callback.message.answer(
                    f"Слот #{slot_id} перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Капитан {captain_name} был снят со слота.\n"
                    f"Назначьте нового капитана, если нужно.",
                    reply_markup=schedule_exc_management_menu()
                )
            else:
                await callback.message.answer(
                    f"Слот #{slot_id} перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')} без капитана.",
                    reply_markup=schedule_exc_management_menu()
                )

            await state.clear()
        else:
            # Если не удалось перенести, возвращаем капитана (если был)
            if captain_was_assigned and slot:
                await db_manager.assign_captain_to_slot(slot_id, slot.captain_id)

            await callback.message.answer(
                f"Не удалось перенести слот.\n"
                f"Причина: {error_message}",
                reply_markup=schedule_exc_management_menu()
            )

@router.callback_query(F.data.startswith("cancel_reschedule:"))
async def cancel_reschedule_process(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса переноса"""
    logger.info(f"Админ {callback.from_user.id} отменяет процесс переноса слота")
    await callback.answer()
    await state.clear()
    await callback.message.answer("Перенос отменен.")
from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import (
    UserRepository, SlotRepository, ExcursionRepository
)
from app.database.managers import SlotManager
from app.database.session import async_session

from app.admin_panel.states_adm import RescheduleSlot
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu,
    slot_actions_menu, slots_conflict_keyboard,
    captains_selection_menu, slot_action_confirmation_menu,
    no_captains_options_menu, captain_conflict_keyboard,
    schedule_date_management_menu
)
from app.middlewares import AdminMiddleware

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
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)
                success, slot = await slot_manager.cancel_slot(slot_id)

                if not success:
                    await callback.message.answer("Не удалось отменить слот.")
                    return

                # Уведомляем клиентов о отмене
                if slot and slot.bookings:
                    logger.info(f"Слот {slot_id} отменен. Бронирований для отмены: {len(slot.bookings)}")
                    # TODO: Добавить уведомления клиентам

                await callback.message.answer(
                    f"Слот #{slot_id} успешно отменен.\n"
                    f"Все связанные бронирования отменены."
                )

                logger.info(f"Слот {slot_id} отменен администратором {callback.from_user.id}")

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
            user_repo = UserRepository(session)
            captains = await user_repo.get_all_captains()

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
            async with UnitOfWork(session) as uow:
                slot_repo = SlotRepository(uow.session)
                user_repo = UserRepository(uow.session)

                # Назначаем капитана на слот
                success = await slot_repo.assign_captain(slot_id, captain_id)

                if not success:
                    await callback.message.answer("Не удалось назначить капитана.")
                    return

                # Получаем обновленную информацию о слотe
                slot = await slot_repo.get_by_id(slot_id)
                captain = await user_repo.get_by_id(captain_id)

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
    # TODO Разобраться, где оно вызывается (по ходу, пока что нигде). Почему именно на три дня?
    logger.info(f"Администратор {callback.from_user.id} открыл управление слотами")

    try:
        await callback.answer()

        # Получаем слоты на ближайшие 3 дня для управления
        date_from = datetime.now()
        date_to = date_from + timedelta(days=3)

        async with async_session() as session:
            slot_repo = SlotRepository(session)

            slots = await slot_repo.get_for_period(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайшие 3 дня нет слотов для управления.\n"
                    "Вы можете добавить новые слоты через меню 'Добавить в расписание'."
                )
                return

            builder = InlineKeyboardBuilder()
            for slot in slots:
                # У slot уже будет загружена excursion через selectinload
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная"

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
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info:
                await callback.message.answer(f"Слот {slot_id} не найден.")
                return

            slot = slot_info['slot']
            booked_places = slot_info['booked_places']
            current_weight = slot_info['current_weight']
            active_bookings = slot_info['active_bookings']

            # Формируем ответ
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
        await callback.message.answer("Произошла ошибка при управлении слотом")

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

            # Формируем основную информацию
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

            # Информация о капитане
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

            # Информация о бронированиях
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

                # Статистика по статусам
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
        await message.answer("Произошла ошибка при обработке даты")

@router.callback_query(F.data.startswith("confirm_reschedule_"))
async def confirm_reschedule(callback: CallbackQuery, state: FSMContext):
    """Подтверждение переноса слота"""
    try:
        await callback.answer()

        parts = callback.data.split(":")
        action = parts[0]  # "confirm_reschedule_yes" или "confirm_reschedule_no"
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
                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
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
                    return

                # Успешное обновление
                await callback.message.answer(
                    f"Слот #{slot_id} успешно перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=schedule_exc_management_menu()
                )
                # TODO: Отправить уведомления клиентам
                await state.clear()

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

        # Используем существующий метод
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
            async with UnitOfWork(session) as uow:
                slot_manager = SlotManager(uow.session)
                user_repo = UserRepository(uow.session)

                # Проверяем, что капитан все еще доступен
                available_captains = data.get('available_captains', [])
                if captain_id not in available_captains:
                    await callback.message.answer(
                        "Капитан больше не доступен на это время. Выберите другого капитана."
                    )
                    return

                # Переносим слот с новым капитаном
                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
                    await callback.message.answer(
                        f"Не удалось перенести слот.\nПричина: {error_message}"
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
                        await callback.message.answer("Попробуйте ввести другое время:")
                        await state.set_state(RescheduleSlot.waiting_for_new_datetime)
                    return

                # Назначаем капитана (после успешного переноса)
                slot_repo = SlotRepository(uow.session)
                captain_assigned = await slot_repo.assign_captain(slot_id, captain_id)

                if not captain_assigned:
                    await callback.message.answer(
                        f"Слот перенесен, но не удалось назначить капитана.",
                        reply_markup=schedule_exc_management_menu()
                    )
                    await state.clear()
                    return

                # Получаем информацию о капитане
                captain = await user_repo.get_by_id(captain_id)
                captain_name = captain.full_name if captain else f"ID {captain_id}"

                await callback.message.answer(
                    f"Слот #{slot_id} успешно перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Капитан: {captain_name}",
                    reply_markup=schedule_exc_management_menu()
                )
                # TODO: Отправить уведомления клиентам и капитану

        await state.clear()

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

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                slot_repo = SlotRepository(uow.session)
                user_repo = UserRepository(uow.session)
                slot_manager = SlotManager(uow.session)

                # Получаем текущий слот
                slot = await slot_repo.get_by_id(slot_id)
                if not slot:
                    await callback.message.answer("Слот не найден.")
                    await state.clear()
                    return

                # Запоминаем текущего капитана
                original_captain_id = slot.captain_id
                captain_was_assigned = original_captain_id is not None
                captain_name = ""

                if captain_was_assigned:
                    captain = await user_repo.get_by_id(original_captain_id)
                    captain_name = captain.full_name if captain else f"ID {original_captain_id}"

                    # Снимаем капитана
                    await slot_repo.assign_captain(slot_id, None)

                # Пытаемся перенести слот
                success, error_message = await slot_manager.reschedule_slot(slot_id, new_datetime)

                if not success:
                    # Если не удалось перенести, восстанавливаем капитана
                    if captain_was_assigned:
                        await slot_repo.assign_captain(slot_id, original_captain_id)

                    await callback.message.answer(
                        f"Не удалось перенести слот.\nПричина: {error_message}",
                        reply_markup=schedule_exc_management_menu()
                    )
                    return

                # Успешный перенос
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

            # Успешно завершили транзакцию
            await state.clear()

    except Exception as e:
        logger.error(f"Ошибка переноса слота без капитана {slot_id}: {e}")
        await callback.message.answer("Произошла ошибка при переносе")
        await state.clear()

@router.callback_query(F.data.startswith("cancel_reschedule:"))
async def cancel_reschedule_process(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса переноса"""
    logger.info(f"Админ {callback.from_user.id} отменяет процесс переноса слота")
    await callback.answer()
    await state.clear()
    await callback.message.answer("Перенос отменен.")
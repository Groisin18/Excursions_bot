from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, date

from app.admin_panel.states_adm import AdminStates
from app.database.requests import DatabaseManager
from app.database.models import SlotStatus
from app.database.session import async_session
from app.utils.validation import validate_slot_date
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu, schedule_view_options,
    schedule_date_management_menu, schedule_month_management_menu,
    schedule_week_management_menu
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_schedule")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== ОБЩИЕ КНОПКИ МЕНЮ =====

@router.callback_query(F.data == "back_to_schedule_menu")
async def back_to_schedule_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню расписания"""
    logger.debug(f"Администратор {callback.from_user.id} вернулся в меню расписания")

    try:
        await callback.answer()
        await state.clear()
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=schedule_exc_management_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка возврата в меню расписания: {e}", exc_info=True)

@router.callback_query(F.data.startswith("toggle_excursion:"))
async def toggle_excursion_callback(callback: CallbackQuery):
    """Изменение статуса экскурсии (inline)"""
    excursion_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет изменить статус экскурсии {excursion_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Изменение статуса экскурсии #{excursion_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


# ===== ПРОСМОТР РАСПИСАНИЯ =====

@router.message(F.text == "Расписание экскурсий")
async def show_excursion_schedule(message: Message):
    """Показать расписание экскурсий на ближайшие дни"""
    logger.info(f"Администратор {message.from_user.id} выбрал просмотр расписания")

    try:
        await message.answer(
            "Выберите период для просмотра:",
            reply_markup=schedule_view_options()
        )
    except Exception as e:
        logger.error(f"Ошибка в view_schedule: {e}", exc_info=True)
        await message.answer("Произошла ошибка")

@router.callback_query(F.data == "view_schedule_by_date")
async def view_schedule_by_date(callback: CallbackQuery, state: FSMContext):
    """Запрос конкретной даты для просмотра расписания"""
    logger.info(f"Администратор {callback.from_user.id} хочет посмотреть расписание на конкретную дату")

    try:
        await callback.answer()
        await callback.message.answer(
            "Введите дату для просмотра расписания в формате ДД.ММ.ГГГГ\n"
            "Например: 15.01.2024\n\n"
            "Или нажмите /cancel для отмены"
        )
        await state.set_state(AdminStates.waiting_for_schedule_date)

    except Exception as e:
        logger.error(f"Ошибка начала просмотра расписания по дате: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

async def format_schedule_for_date_with_preloaded(target_date: date, slots: list, db_manager: DatabaseManager) -> str:
    """
    Форматировать расписание с предзагруженными данными

    Args:
        target_date: Дата расписания
        slots: Список слотов с предзагруженной экскурсией
        db_manager: Менеджер базы данных
    """
    response = f"Расписание на {target_date.strftime('%d.%m.%Y (%A)')}:\n\n"

    for slot in slots:
        excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

        # Статус слота
        status_text = {
            SlotStatus.scheduled: "Запланирована",
            SlotStatus.in_progress: "В процессе",
            SlotStatus.completed: "Завершена",
            SlotStatus.cancelled: "Отменена"
        }.get(slot.status, "Неизвестно")

        # Форматируем время
        start_time = slot.start_datetime.strftime("%H:%M")
        end_time = slot.end_datetime.strftime("%H:%M")

        response += (
            f"• {start_time}-{end_time} "
            f"({excursion_name})\n"
            f"  ID слота: {slot.id}\n"
            f"Количество свободных мест: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}/{slot.max_people}\n"
            f"Занятость по максимально допустимому весу: {await db_manager.get_current_weight_for_slot(slot.id)}/{slot.max_weight}\n"
            f"({status_text})\n"
        )

        # Информация о капитане, если есть
        if slot.captain_id:
            captain = await db_manager.get_user_by_id(slot.captain_id)
            if captain:
                response += f"  Капитан: {captain.full_name}\n"

        response += "\n"

    return response

@router.message(AdminStates.waiting_for_schedule_date)
async def handle_schedule_date_view(message: Message, state: FSMContext):
    """Показать расписание на конкретную дату"""
    logger.info(f"Администратор {message.from_user.id} запросил расписание на дату: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Просмотр расписания отменен.",
                reply_markup=schedule_exc_management_menu()
            )
            return

        try:
            target_date = validate_slot_date(message.text)
        except ValueError as e:
            await message.answer(str(e))
            return

        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_slots_for_period_with_excursion(date_from, date_to)

            if not slots:
                await message.answer(
                    f"На {target_date.strftime('%d.%m.%Y')} нет запланированных экскурсий.\n\n"
                    f"Вы можете:\n"
                    f"1. Добавить экскурсию на эту дату\n"
                    f"2. Посмотреть другую дату\n"
                    f"3. Вернуться в меню"
                )
                await state.clear()
                await message.answer(
                    "Выберите действие:",
                    reply_markup=schedule_exc_management_menu()
                )
                return

            response = await format_schedule_for_date_with_preloaded(target_date, slots, db_manager)
            await message.answer(response)
            await message.answer(
                "Выберите действие:",
                reply_markup=schedule_date_management_menu(slots, target_date)
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка показа расписания по дате: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении расписания")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка показа расписания по дате: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении расписания")
        await state.clear()

@router.callback_query(F.data == "schedule_today")
async def schedule_today_callback(callback: CallbackQuery):
    """Показать расписание на сегодня"""
    logger.info(f"Администратор {callback.from_user.id} запросил расписание на сегодня")

    try:
        await callback.answer()

        today = datetime.now().date()
        date_from = datetime.combine(today, datetime.min.time())
        date_to = datetime.combine(today, datetime.max.time())

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_slots_for_period_with_excursion(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    f"На сегодня ({today.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            response = f"Расписание на сегодня ({today.strftime('%d.%m.%Y')}):\n\n"

            for slot in slots:
                # Теперь excursion уже загружен
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

                status_text = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }.get(slot.status, "Неизвестно")

                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M")

                response += (
                    f"• {start_time}-{end_time} "
                    f"({excursion_name})\n"
                    f"  ID: {slot.id}, Свободные места: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}/{slot.max_people}\n"
                    f"  Статус: {status_text}\n\n"
                )

            await callback.message.answer(response)

            # Показываем клавиатуру управления слотами
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_date_management_menu(slots, today)
            )

    except Exception as e:
        logger.error(f"Ошибка показа расписания на сегодня: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "schedule_tomorrow")
async def schedule_tomorrow_callback(callback: CallbackQuery):
    """Показать расписание на завтра"""
    logger.info(f"Администратор {callback.from_user.id} запросил расписание на завтра")

    try:
        await callback.answer()

        tomorrow = datetime.now().date() + timedelta(days=1)
        date_from = datetime.combine(tomorrow, datetime.min.time())
        date_to = datetime.combine(tomorrow, datetime.max.time())

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_slots_for_period_with_excursion(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    f"На завтра ({tomorrow.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            response = f"Расписание на завтра ({tomorrow.strftime('%d.%m.%Y')}):\n\n"

            for slot in slots:
                excursion = slot.excursion
                excursion_name = excursion.name if excursion else "Неизвестная экскурсия"

                status_text = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }.get(slot.status, "Неизвестно")

                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M")

                response += (
                    f"• {start_time}-{end_time} "
                    f"({excursion_name})\n"
                    f"  ID: {slot.id}, Свободные места: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}/{slot.max_people}\n"
                    f"  Статус: {status_text}\n\n"
                )

            await callback.message.answer(response)

            # Показываем клавиатуру управления слотами
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_date_management_menu(slots, tomorrow)
            )

    except Exception as e:
        logger.error(f"Ошибка показа расписания на завтра: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "schedule_week")
async def schedule_week_callback(callback: CallbackQuery):
    """Показать расписание на неделю вперед"""
    logger.info(f"Администратор {callback.from_user.id} запросил расписание на неделю")

    try:
        await callback.answer()
        date_from = datetime.now()
        date_to = date_from + timedelta(days=7)

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_slots_for_period_with_excursion(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайшие 7 дней нет запланированных экскурсий."
                )
                return

            # Группируем по датам
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)

            response = "Расписание на ближайшие 7 дней:\n\n"

            for slot_date, date_slots in sorted(slots_by_date.items()):
                response += f"{slot_date.strftime('%d.%m.%Y (%A)')}:\n"

                for slot in date_slots:
                    excursion = slot.excursion
                    excursion_name = excursion.name if excursion else "Неизвестная экскурсия"

                    status_text = {
                        SlotStatus.scheduled: "Запланирована",
                        SlotStatus.in_progress: "В процессе",
                        SlotStatus.completed: "Завершена",
                        SlotStatus.cancelled: "Отменена"
                    }.get(slot.status, "Неизвестно")

                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    response += f"  • {start_time}-{end_time} ({excursion_name}) - {status_text}\n"

                response += "\n"

            await callback.message.answer(response)

            # Показываем меню с вариантами управления
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_week_management_menu(slots_by_date)
            )

    except Exception as e:
        logger.error(f"Ошибка показа расписания на неделю: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_exc_management_menu())

@router.callback_query(F.data == "schedule_month")
async def schedule_month_callback(callback: CallbackQuery):
    """Показать расписание на месяц вперед"""
    logger.info(f"Администратор {callback.from_user.id} запросил расписание на месяц")

    try:
        await callback.answer()

        # Получаем расписание на ближайшие 30 дней
        date_from = datetime.now()
        date_to = date_from + timedelta(days=30)

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_slots_for_period_with_excursion(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайшие 30 дней нет запланированных экскурсий."
                )
                return

            # Группируем по датам
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)

            response = "Расписание на ближайшие 30 дней:\n\n"

            for slot_date, date_slots in sorted(slots_by_date.items())[:10]:  # Показываем первые 10 дней
                response += f"{slot_date.strftime('%d.%m.%Y (%A)')}:\n"

                for slot in date_slots:
                    excursion = slot.excursion
                    excursion_name = excursion.name if excursion else "Неизвестная экскурсия"

                    status_text = {
                        SlotStatus.scheduled: "Запланирована",
                        SlotStatus.in_progress: "В процессе",
                        SlotStatus.completed: "Завершена",
                        SlotStatus.cancelled: "Отменена"
                    }.get(slot.status, "Неизвестно")

                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    response += f"  • {start_time}-{end_time} ({excursion_name}) - {status_text}\n"

                response += "\n"

            if len(slots_by_date) > 10:
                response += f"\n... и еще {len(slots_by_date) - 10} дней"

            await callback.message.answer(response)

            # Показываем меню с вариантами управления
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_month_management_menu(slots_by_date)
            )
            # TODO Отработать show_more_month_dates из клавиатуры

    except Exception as e:
        logger.error(f"Ошибка показа расписания на месяц: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "view_schedule")
async def view_schedule_callback(callback: CallbackQuery):
    """Просмотр расписания (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} выбрал просмотр расписания")

    try:
        await callback.answer()
        # Перенаправляем на функцию просмотра расписания
        await callback.message.answer(
            "Выберите период для просмотра:",
            reply_markup=schedule_view_options()
        )
    except Exception as e:
        logger.error(f"Ошибка в view_schedule: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")
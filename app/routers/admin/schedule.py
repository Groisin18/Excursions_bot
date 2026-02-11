from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.admin_panel.states_adm import AdminStates
from app.database.repositories import SlotRepository
from app.database.managers import SlotManager
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

        async with async_session() as session:
            slot_manager = SlotManager(session)
            schedule_text = await slot_manager.get_detailed_schedule_for_date(target_date)

            if not schedule_text:
                await message.answer(
                    f"На {target_date.strftime('%d.%m.%Y')} нет запланированных экскурсий.\n\n"
                    f"Вы можете:\n"
                    f"1. Добавить экскурсию на эту дату\n"
                    f"2. Посмотреть другую дату\n"
                    f"3. Вернуться в меню"
                )
            else:
                await message.answer(schedule_text)

            # Получаем слоты для меню
            slot_repo = SlotRepository(session)
            date_from = datetime.combine(target_date, datetime.min.time())
            date_to = datetime.combine(target_date, datetime.max.time())
            slots = await slot_repo.get_schedule(date_from=date_from, date_to=date_to)

            await message.answer(
                "Выберите действие:",
                reply_markup=schedule_date_management_menu(slots, target_date)
            )

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

        async with async_session() as session:
            slot_manager = SlotManager(session)
            schedule_text = await slot_manager.get_detailed_schedule_for_date(today)

            if not schedule_text:
                await callback.message.answer(
                    f"На сегодня ({today.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            await callback.message.answer(schedule_text)

            # Получаем слоты для меню
            slot_repo = SlotRepository(session)
            date_from = datetime.combine(today, datetime.min.time())
            date_to = datetime.combine(today, datetime.max.time())
            slots = await slot_repo.get_schedule(date_from=date_from, date_to=date_to)

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

        async with async_session() as session:
            slot_manager = SlotManager(session)
            schedule_text = await slot_manager.get_detailed_schedule_for_date(tomorrow)

            if not schedule_text:
                await callback.message.answer(
                    f"На завтра ({tomorrow.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            await callback.message.answer(schedule_text)

            # Получаем слоты для меню
            slot_repo = SlotRepository(session)
            date_from = datetime.combine(tomorrow, datetime.min.time())
            date_to = datetime.combine(tomorrow, datetime.max.time())
            slots = await slot_repo.get_schedule(date_from=date_from, date_to=date_to)

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

        async with async_session() as session:
            slot_manager = SlotManager(session)
            schedule_text, slots_by_date = await slot_manager.get_weekly_schedule(days_ahead=7)

            if not schedule_text:
                await callback.message.answer(
                    "На ближайшие 7 дней нет запланированных экскурсий."
                )
                return

            await callback.message.answer(schedule_text)

            # Показываем меню с вариантами управления
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_week_management_menu(slots_by_date)
            )

    except Exception as e:
        logger.error(f"Ошибка показа расписания на неделю: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_exc_management_menu())

@router.callback_query(F.data == "schedule_month")
async def schedule_month_callback(callback: CallbackQuery, state: FSMContext):
    """Показать расписание на месяц вперед"""
    logger.info(f"Администратор {callback.from_user.id} запросил расписание на месяц")

    try:
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            schedule_text, slots_by_date = await slot_manager.get_weekly_schedule(days_ahead=30)

            if not schedule_text:
                await callback.message.answer(
                    "На ближайшие 30 дней нет запланированных экскурсий."
                )
                return

            # Сохраняем в состоянии для использования в show_more
            await state.update_data(
                monthly_slots_by_date=slots_by_date,
                monthly_total_days=len(slots_by_date)
            )

            # Ограничиваем вывод первыми 7 днями
            limited_response = "Расписание на ближайшие 30 дней:\n\n"
            sorted_dates = sorted(slots_by_date.keys())

            for slot_date in sorted_dates[:7]:
                date_slots = slots_by_date[slot_date]
                limited_response += f"{slot_date.strftime('%d.%m.%Y (%A)')}:\n"

                for slot in date_slots:
                    excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

                    status_text = {
                        SlotStatus.scheduled: "Запланирована",
                        SlotStatus.in_progress: "В процессе",
                        SlotStatus.completed: "Завершена",
                        SlotStatus.cancelled: "Отменена"
                    }.get(slot.status, "Неизвестно")

                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M") if slot.end_datetime else "?"

                    limited_response += f"  • {start_time}-{end_time} ({excursion_name}) - {status_text}\n"

                limited_response += "\n"

            if len(slots_by_date) > 7:
                limited_response += f"\n... и еще {len(slots_by_date) - 7} дней"

            await callback.message.answer(limited_response)

            # Показываем меню с вариантами управления
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_month_management_menu(slots_by_date)
            )

    except Exception as e:
        logger.error(f"Ошибка показа расписания на месяц: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "show_more_month_dates")
async def show_more_month_dates_callback(callback: CallbackQuery, state: FSMContext):
    """Показать остальные дни месяца из сохраненных данных"""
    logger.info(f"Администратор {callback.from_user.id} запросил продолжение расписания на месяц")

    try:
        await callback.answer()

        # Получаем данные из состояния
        data = await state.get_data()
        slots_by_date = data.get('monthly_slots_by_date', {})
        total_days = data.get('monthly_total_days', 0)

        if not slots_by_date or total_days <= 7:
            await callback.message.answer("Нет дополнительных дней для показа")
            return

        # Показываем дни с 8-го и дальше
        response = "Продолжение расписания на месяц:\n\n"
        sorted_dates = sorted(slots_by_date.keys())

        for slot_date in sorted_dates[7:min(total_days, 20)]:  # Показываем до 20 дней
            date_slots = slots_by_date[slot_date]
            response += f"{slot_date.strftime('%d.%m.%Y (%A)')}:\n"

            for slot in date_slots:
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

                status_text = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }.get(slot.status, "Неизвестно")

                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M") if slot.end_datetime else "?"

                response += f"  • {start_time}-{end_time} ({excursion_name}) - {status_text}\n"

            response += "\n"

        if total_days > 20:
            response += f"\n... и еще {total_days - 20} дней"

        await callback.message.answer(response)

        # Предлагаем вернуться к меню
        await callback.message.answer(
            "Для управления расписанием вернитесь в меню месяца.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Вернуться к меню месяца",
                        callback_data="back_to_month_menu"
                    )]
                ]
            )
        )

    except Exception as e:
        logger.error(f"Ошибка показа продолжения расписания: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "back_to_month_menu")
async def back_to_month_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Вернуться к меню месяца"""
    try:
        await callback.answer()

        data = await state.get_data()
        slots_by_date_str = data.get('monthly_slots_by_date', {})

        if not slots_by_date_str:
            await callback.message.answer("Данные устарели. Запросите расписание заново.")
            return

        # Конвертируем обратно
        slots_by_date = {}
        for date_str, date_slots in slots_by_date_str.items():
            slot_date = datetime.fromisoformat(date_str).date()
            # Восстанавливаем оригинальные объекты или оставляем как есть
            slots_by_date[slot_date] = date_slots

        # Показываем меню
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=schedule_month_management_menu(slots_by_date)
        )

    except Exception as e:
        logger.error(f"Ошибка возврата к меню месяца: {e}", exc_info=True)
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
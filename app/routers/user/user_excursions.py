from datetime import datetime, timedelta, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as kb

from app.database.requests import DatabaseManager
from app.database.models import async_session
from app.utils.logging_config import get_logger
from app.utils.datetime_utils import get_weekday_name
from app.utils.validation import Validators
from app.user_panel.states import UserScheduleStates


router = Router(name="user_excursions")

logger = get_logger(__name__)

# ===== НАЧАЛЬНОЕ МЕНЮ ВЫБОРА РАСПИСАНИЯ =====

@router.message(F.text == 'Наши экскурсии')
async def excursions(message: Message):
    """Показать список экскурсий из базы данных"""
    logger.info(f"Пользователь {message.from_user.id} запросил список экскурсий")
    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            excursions_list = await db.get_all_excursions(active_only=True)
            if not excursions_list:
                logger.warning(f"Нет доступных экскурсий для пользователя {message.from_user.id}")
                await message.answer(
                    "В настоящее время нет доступных экскурсий. Пожалуйста, проверьте позже.",
                    reply_markup=kb.main
                )
                return

            excursions_text = "Наши экскурсии:\n\n"
            for i, excursion in enumerate(excursions_list, 1):
                excursions_text += (
                    f"{i}. {excursion.name}\n"
                    f"   Стоимость: {excursion.base_price} руб.\n"
                    f"   Продолжительность: {excursion.base_duration_minutes} мин.\n"
                )
            if excursion.description and len(excursion.description) < 100:
                excursions_text += f"   {excursion.description}\n"
            excursions_text += ("\n"
                                f"   Скидки для детей:\n"
                                f"     - до 3 лет: бесплатно\n"
                                f"     - 4-7 лет: скидка 60%\n"
                                f"     - 8-12 лет: скидка 40%\n"
                                f"     - 13 лет и старше: полная стоимость\n"
                )

            excursions_text += "Выберите экскурсию для подробной информации или посмотрите общее расписание:"

            await message.answer(
                excursions_text,
                reply_markup=await kb.all_excursions_inline()
            )
            logger.debug(f"Список экскурсий отправлен пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка показа экскурсий для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при загрузке списка экскурсий. Попробуйте позже.",
            reply_markup=kb.main
        )

@router.callback_query(F.data == "public_schedule_all")
async def show_public_schedule_all(callback: CallbackQuery):
    """Показать опции просмотра расписания"""
    try:
        await callback.answer()
        await callback.message.answer(
            "Выберите период для просмотра расписания:",
            reply_markup=kb.public_schedule_options()
        )
    except Exception as e:
        logger.error(f"Ошибка показа опций расписания: {e}")
        await callback.answer("Ошибка загрузки", show_alert=True)

@router.callback_query(F.data == "public_back_to_excursions")
async def back_to_excursions_list_public(callback: CallbackQuery):
    """Вернуться к списку экскурсий (публичная версия)"""
    try:
        await callback.answer()

        # Просто отправляем новое сообщение со списком экскурсий
        async with async_session() as session:
            db = DatabaseManager(session)
            excursions_list = await db.get_all_excursions(active_only=True)

            if not excursions_list:
                await callback.message.answer(
                    "В настоящее время нет доступных экскурсий.",
                    reply_markup=kb.main
                )
                return

            excursions_text = "Наши экскурсии:\n\n"
            for i, excursion in enumerate(excursions_list, 1):
                excursions_text += (
                    f"{i}. {excursion.name}\n"
                    f"   Стоимость: {excursion.base_price} руб.\n"
                    f"   Продолжительность: {excursion.base_duration_minutes} мин.\n"
                )
            if excursion.description and len(excursion.description) < 100:
                excursions_text += f"   {excursion.description}\n"
            excursions_text += ("\n"
                                f"   Скидки для детей:\n"
                                f"     - до 3 лет: бесплатно\n"
                                f"     - 4-7 лет: скидка 60%\n"
                                f"     - 8-12 лет: скидка 40%\n"
                                f"     - 13 лет и старше: полная стоимость\n"
                )

            excursions_text += "Выберите экскурсию для подробной информации или посмотрите общее расписание:"

            keyboard = await kb.all_excursions_inline()
            await callback.message.answer(
                excursions_text,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Ошибка возврата к списку экскурсий: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки списка", show_alert=True)


# ===== ПРОСМОТР РАСПИСАНИЯ ПО ДАТЕ =====

async def format_public_schedule_for_date(
    target_date: date,
    slots: list,
    db_manager: DatabaseManager
) -> str:
    """Форматировать расписание для пользователей"""


    response = f"Расписание на {target_date.strftime('%d.%m.%Y')} ({get_weekday_name(target_date)}):\n\n"

    for slot in slots:
        excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

        # Время
        start_time = slot.start_datetime.strftime("%H:%M")
        end_time = slot.end_datetime.strftime("%H:%M")

        # Свободные места
        booked = await db_manager.get_booked_places_for_slot(slot.id)
        free_places = slot.max_people - booked

        if free_places > 0:
            places_text = f"({free_places} мест)"
        else:
            places_text = "(Мест нет)"

        response += f"• {start_time}-{end_time} {excursion_name} {places_text}\n"

    return response

async def show_date_schedule(reply_func, target_date: date, answer_func=None):
    """
    Общая функция показа расписания на дату

    Args:
        reply_func: функция для отправки сообщения (callback.message.answer или message.answer)
        target_date: дата для показа
        answer_func: функция для callback.answer (только для callback)
    """
    try:
        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        async with async_session() as session:
            db = DatabaseManager(session)
            slots = await db.get_public_schedule_for_period(date_from, date_to)

            if not slots:
                await reply_func(
                    f"На {target_date.strftime('%d.%m.%Y')} нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                if answer_func:
                    await answer_func()
                return

            text = await format_public_schedule_for_date(target_date, slots, db)
            keyboard = kb.public_schedule_date_menu(slots, target_date)
            await reply_func(text, reply_markup=keyboard)
            if answer_func:
                await answer_func()

    except Exception as e:
        logger.error(f"Ошибка показа расписания: {e}", exc_info=True)
        if answer_func:
            await answer_func("Ошибка загрузки расписания", show_alert=True)
        else:
            await reply_func("Произошла ошибка при получении расписания")

@router.callback_query(F.data == "public_schedule_today")
async def public_schedule_today(callback: CallbackQuery):
    """Показать расписание на сегодня"""
    await show_date_schedule(callback.message.answer, datetime.now().date(), callback.answer)

@router.callback_query(F.data == "public_schedule_tomorrow")
async def public_schedule_tomorrow(callback: CallbackQuery):
    """Показать расписание на завтра"""
    await show_date_schedule(callback.message.answer, datetime.now().date() + timedelta(days=1), callback.answer)

@router.callback_query(F.data == "public_schedule_week")
async def public_schedule_week(callback: CallbackQuery):
    """Показать расписание на неделю для пользователей"""
    try:
        await callback.answer()

        date_from = datetime.now()
        date_to = date_from + timedelta(days=7)

        async with async_session() as session:
            db = DatabaseManager(session)
            slots = await db.get_public_schedule_for_period(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайшую неделю нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            # Группируем по датам
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)

            # Формируем текст
            text = "Расписание на неделю:\n\n"

            for date_key in sorted(slots_by_date.keys()):
                date_slots = slots_by_date[date_key]
                text += f"{date_key.strftime('%d.%m.%Y')} ({get_weekday_name(date_key)}):\n"

                for slot in date_slots:
                    excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

                    # Время
                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    # Свободные места
                    booked = await db.get_booked_places_for_slot(slot.id)
                    free_places = slot.max_people - booked

                    if free_places > 0:
                        places_text = f"({free_places} мест)"
                    else:
                        places_text = "(Мест нет)"

                    text += f"• {start_time}-{end_time} {excursion_name} {places_text}\n"

                text += "\n"

            keyboard = kb.public_schedule_week_menu(slots_by_date)
            await callback.message.answer(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания на неделю: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data == "public_schedule_month")
async def public_schedule_month(callback: CallbackQuery):
    """Показать расписание на месяц для пользователей"""
    try:
        await callback.answer()

        date_from = datetime.now()
        date_to = date_from + timedelta(days=30)

        async with async_session() as session:
            db = DatabaseManager(session)
            slots = await db.get_public_schedule_for_period(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    "На ближайший месяц нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            # Группируем по датам
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)


            text = "Расписание на месяц:\n\n"

            dates_to_show = sorted(slots_by_date.keys())

            for date_key in dates_to_show:
                date_slots = slots_by_date[date_key]
                text += f"{date_key.strftime('%d.%m.%Y')} ({get_weekday_name(date_key)}):\n"

                # Показываем только первые 3 слота на день
                for slot in date_slots[:3]:
                    excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

                    # Время
                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    # Свободные места
                    booked = await db.get_booked_places_for_slot(slot.id)
                    free_places = slot.max_people - booked

                    if free_places > 0:
                        places_text = f"({free_places} мест)"
                    else:
                        places_text = "(Мест нет)"

                    text += f"• {start_time}-{end_time} {excursion_name} {places_text}\n"

                if len(date_slots) > 3:
                    text += f"  ... и еще {len(date_slots) - 3} экскурсий\n"

                text += "\n"

            keyboard = kb.public_schedule_month_menu(slots_by_date)
            await callback.message.answer(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания на месяц: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data == "public_schedule_by_date")
async def public_schedule_by_date(callback: CallbackQuery, state: FSMContext):
    """Запрос даты для просмотра расписания"""
    try:
        await callback.answer()
        await callback.message.answer(
            "Введите дату для просмотра расписания в формате ДД.ММ.ГГГГ\n"
            "Например: 15.01.2024\n\n"
            "Или нажмите /cancel для отмены"
        )
        await state.set_state(UserScheduleStates.waiting_for_schedule_date)

    except Exception as e:
        logger.error(f"Ошибка запроса даты: {e}", exc_info=True)
        await callback.answer("Ошибка", show_alert=True)

@router.message(UserScheduleStates.waiting_for_schedule_date)
async def handle_public_schedule_date(message: Message, state: FSMContext):
    """Обработка введенной даты для расписания"""
    try:
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Просмотр расписания отменен.",
                reply_markup=kb.public_schedule_options()
            )
            return

        try:
            target_date = Validators.validate_slot_date(message.text)
        except ValueError as e:
            await message.answer(str(e))
            return

        if target_date < datetime.now().date():
            await message.answer("Нельзя посмотреть расписание на прошедшую дату.")
            return

        # Используем общую функцию
        await show_date_schedule(message.answer, target_date)
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка обработки даты расписания: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении расписания")
        await state.clear()

@router.callback_query(F.data.startswith("public_view_date:"))
async def public_view_date_callback(callback: CallbackQuery):
    """Показать расписание на выбранную дату"""
    date_str = callback.data.split(":")[-1]
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    await show_date_schedule(callback.message.answer, target_date, callback.answer)

@router.callback_query(F.data == "public_back_to_schedule_options")
async def public_back_to_schedule_options(callback: CallbackQuery):
    """Вернуться к выбору периода"""
    try:
        await callback.answer()
        await callback.message.answer(
            "Выберите период для просмотра расписания:",
            reply_markup=kb.public_schedule_options()
        )
    except Exception as e:
        logger.error(f"Ошибка возврата к выбору периода: {e}")
        await callback.answer("Ошибка", show_alert=True)


# ===== ПРОСМОТР РАСПИСАНИЯ ПО ВИДУ ЭКСКУРСИИ =====

@router.callback_query(F.data.startswith("public_exc_detail:"))
async def show_excursion_public_detail(callback: CallbackQuery):
    """Показать детали экскурсии для пользователя"""
    try:
        exc_id = int(callback.data.split(":")[-1])

        async with async_session() as session:
            db = DatabaseManager(session)
            excursion = await db.get_excursion_by_id(exc_id)

            if not excursion:
                await callback.answer("Экскурсия не найдена", show_alert=True)
                return

            details = (
                f"{excursion.name}\n\n"
                f"Стоимость:\n"
                f"   • Взрослый: {excursion.base_price} руб.\n"
                f"   • Детский: до 3 лет - бесплатно, 4-7 лет скидка 60%, 8-12 лет скидка 40%, 13+ лет - полная цена\n\n"
                f"\nПродолжительность: {excursion.base_duration_minutes} минут\n\n"
            )
            if excursion.description:
                details += f"Описание:\n{excursion.description}\n\n"

            await callback.answer()
            await callback.message.answer(
                details,
                reply_markup=await kb.get_excursion_details_inline(exc_id)
            )

    except Exception as e:
        logger.error(f"Ошибка показа деталей экскурсии: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки информации", show_alert=True)

@router.callback_query(F.data.startswith("public_schedule_exc:"))
async def show_excursion_schedule(callback: CallbackQuery):
    """Показать расписание конкретной экскурсии"""
    try:
        exc_id = int(callback.data.split(":")[-1])
        await callback.answer()

        async with async_session() as session:
            db = DatabaseManager(session)

            # Получаем экскурсию
            excursion = await db.get_excursion_by_id(exc_id)
            if not excursion:
                await callback.answer("Экскурсия не найдена", show_alert=True)
                return

            # Получаем слоты на ближайшие 30 дней
            date_from = datetime.now()
            date_to = date_from + timedelta(days=30)

            slots = await db.get_public_schedule_for_period(date_from, date_to)
            # Фильтруем по конкретной экскурсии
            slots = [s for s in slots if s.excursion_id == exc_id]

            if not slots:
                text = f"{excursion.name}\n"
                text += f"\nНа ближайшие 30 дней нет доступных записей на экскурсию '{excursion.name}'.\n"
                text += "Пожалуйста, проверьте позже или выберите другую экскурсию."
                await callback.message.answer(
                    text=text,
                    reply_markup=await kb.all_excursions_inline()
                )
                return

            # Группируем по датам
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)

            text = f"{excursion.name}\n"

            for date_key in sorted(slots_by_date.keys()):
                date_slots = slots_by_date[date_key]
                text += f"\n{date_key.strftime('%d.%m.%Y')} ({get_weekday_name(date_key)}):\n"

                for slot in date_slots:
                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    # Свободные места
                    booked = await db.get_booked_places_for_slot(slot.id)
                    free_places = slot.max_people - booked

                    if free_places > 0:
                        places_text = f"({free_places} мест)"
                    else:
                        places_text = "(Мест нет)"

                    text += f"• {start_time}-{end_time} {places_text}\n"

            keyboard = await kb.get_excursion_schedule_keyboard(slots)
            await callback.message.answer(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания экскурсии: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data.startswith("public_view_exc_date:"))
async def public_view_exc_date(callback: CallbackQuery):
    """Показать слоты конкретной экскурсии на выбранную дату"""
    try:
        # Формат: public_view_exc_date:{date_str}:{exc_id}
        parts = callback.data.split(":")
        date_str = parts[1]
        exc_id = int(parts[2])

        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        async with async_session() as session:
            db = DatabaseManager(session)

            # Получаем все слоты на дату
            slots = await db.get_public_schedule_for_period(date_from, date_to)
            # Фильтруем по экскурсии
            slots = [s for s in slots if s.excursion_id == exc_id]

            if not slots:
                await callback.answer("На эту дату нет слотов для этой экскурсии", show_alert=True)
                return

            excursion = await db.get_excursion_by_id(exc_id)

            # Формируем текст
            from app.utils.datetime_utils import get_weekday_name

            text = (
                f"Экскурсия: {excursion.name if excursion else 'Экскурсия'}\n"
                f"Дата: {target_date.strftime('%d.%m.%Y')} ({get_weekday_name(target_date)})\n\n"
            )

            for slot in slots:
                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M")

                booked = await db.get_booked_places_for_slot(slot.id)
                free_places = slot.max_people - booked

                current_weight = await db.get_current_weight_for_slot(slot.id)
                free_weight = slot.max_weight - current_weight

                if free_places > 0 and free_weight > 0:
                    places_text = f"({free_places} мест, ограничение по весу - не более {free_weight} кг)"
                else:
                    places_text = "(Мест нет)"

                text += f"• {start_time}-{end_time} {places_text}\n"
                text += "\nНажмите на экскурсию, чтобы записаться"

            keyboard = kb.public_schedule_date_menu(slots, target_date)
            await callback.message.answer(text, reply_markup=keyboard)
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа слотов экскурсии на дату: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки", show_alert=True)

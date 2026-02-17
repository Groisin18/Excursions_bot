from datetime import datetime, timedelta, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import app.user_panel.keyboards as kb
from app.user_panel.states import UserScheduleStates

from app.database.repositories import ExcursionRepository
from app.database.managers import SlotManager
from app.database.session import async_session

from app.utils.logging_config import get_logger
from app.utils.datetime_utils import get_weekday_name
from app.utils.validation import validate_slot_date


router = Router(name="user_excursions")

logger = get_logger(__name__)

# TODO Исправить коллбэк-ансверы в блоках ошибок

# ===== НАЧАЛЬНОЕ МЕНЮ ВЫБОРА РАСПИСАНИЯ =====


@router.message(F.text == 'Наши экскурсии')
async def excursions(message: Message):
    """Показать список экскурсий из базы данных"""
    logger.info(f"Пользователь {message.from_user.id} запросил список экскурсий")
    try:
        # Отправляем временное сообщение, которое убирает реплай-клавиатуру
        await message.answer(
            "Загружаем список экскурсий...",
            reply_markup=ReplyKeyboardRemove()
        )

        async with async_session() as session:
            exc_repo = ExcursionRepository(session)
            excursions_list = await exc_repo.get_all(active_only=True)

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

            excursions_text += (
                "\nСкидки для детей:\n"
                "   - до 3 лет: бесплатно\n"
                "   - 4-7 лет: скидка 60%\n"
                "   - 8-12 лет: скидка 40%\n"
                "   - 13 лет и старше: полная стоимость\n\n"
                "Выберите экскурсию для подробной информации или посмотрите общее расписание:"
            )

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
        await callback.message.edit_text(
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
            exc_repo = ExcursionRepository(session)
            excursions_list = await exc_repo.get_all(active_only=True)

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
            await callback.message.edit_text(
                excursions_text,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Ошибка возврата к списку экскурсий: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки списка", show_alert=True)


# ===== ПРОСМОТР РАСПИСАНИЯ ПО ДАТЕ =====


async def show_date_schedule(message_or_callback, target_date: date, is_callback: bool = False):
    try:
        async with async_session() as session:
            slot_manager = SlotManager(session)
            formatted_text, slots = await slot_manager.get_date_schedule(target_date)

            if not slots:
                if is_callback:
                    await message_or_callback.message.edit_text(
                        f"На {target_date.strftime('%d.%m.%Y')} нет доступных экскурсий.",
                        reply_markup=kb.public_schedule_options()
                    )
                    await message_or_callback.answer()
                else:
                    await message_or_callback.edit_text(
                        f"На {target_date.strftime('%d.%m.%Y')} нет доступных экскурсий.",
                        reply_markup=kb.public_schedule_options()
                    )
                return

            keyboard = kb.public_schedule_date_menu(slots, target_date)

            if is_callback:
                await message_or_callback.message.edit_text(formatted_text, reply_markup=keyboard)
                await message_or_callback.answer()
            else:
                await message_or_callback.edit_text(formatted_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания: {e}", exc_info=True)
        if is_callback:
            await message_or_callback.edit_text("Ошибка загрузки расписания", show_alert=True)
        else:
            await message_or_callback.edit_text("Произошла ошибка при получении расписания")


@router.callback_query(F.data.startswith("public_schedule:"))
async def handle_public_schedule(callback: CallbackQuery):
    """Обработчик для публичного расписания (сегодня/завтра)"""
    try:
        await callback.answer()

        if callback.data == "public_schedule:today":
            target_date = datetime.now().date()
            date_name = "сегодня"
        elif callback.data == "public_schedule:tomorrow":
            target_date = datetime.now().date() + timedelta(days=1)
            date_name = "завтра"
        else:
            return

        async with async_session() as session:
            slot_manager = SlotManager(session)
            formatted_text, slots = await slot_manager.get_date_schedule(target_date)

            if not slots:
                await callback.message.edit_text(
                    f"На {date_name} ({target_date.strftime('%d.%m.%Y')}) нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            keyboard = kb.public_schedule_date_menu(slots, target_date)
            await callback.message.edit_text(formatted_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания ({callback.data}): {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data == "public_schedule_week")
async def public_schedule_week(callback: CallbackQuery):
    """Показать расписание на неделю для пользователей"""
    try:
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            text, slots_by_date = await slot_manager.get_week_schedule()

            if not slots_by_date:
                await callback.message.edit_text(
                    "На ближайшую неделю нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            keyboard = kb.public_schedule_week_menu(slots_by_date)
            await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания на неделю: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data == "public_schedule_month")
async def public_schedule_month(callback: CallbackQuery):
    """Показать расписание на месяц для пользователей"""
    try:
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            text, slots_by_date = await slot_manager.get_month_schedule()

            if not slots_by_date:
                await callback.message.edit_text(
                    "На ближайший месяц нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            keyboard = kb.public_schedule_month_menu(slots_by_date)
            await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания на месяц: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки расписания", show_alert=True)

@router.callback_query(F.data == "public_schedule_by_date")
async def public_schedule_by_date(callback: CallbackQuery, state: FSMContext):
    """Запрос даты для просмотра расписания"""
    try:
        await callback.answer()
        await callback.message.edit_text(
            "Введите дату для просмотра расписания в формате ДД.ММ.ГГГГ\n"
            "Например: 15.01.2024\n\n"
            "Или нажмите /cancel для отмены"
        )
        await state.set_state(UserScheduleStates.waiting_for_schedule_date)

    except Exception as e:
        logger.error(f"Ошибка запроса даты: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=kb.main)

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
            target_date = validate_slot_date(message.text)
        except ValueError as e:
            await message.answer(str(e))
            return

        if target_date < datetime.now().date():
            await message.answer("Нельзя посмотреть расписание на прошедшую дату.")
            return

        async with async_session() as session:
            slot_manager = SlotManager(session)
            formatted_text, slots = await slot_manager.get_date_schedule(target_date)

            if not slots:
                await message.answer(
                    f"На {target_date.strftime('%d.%m.%Y')} нет доступных экскурсий.",
                    reply_markup=kb.public_schedule_options()
                )
                await state.clear()
                return

            keyboard = kb.public_schedule_date_menu(slots, target_date)
            await message.answer(formatted_text, reply_markup=keyboard)

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
    await show_date_schedule(callback, target_date, is_callback=True)

@router.callback_query(F.data == "public_back_to_schedule_options")
async def public_back_to_schedule_options(callback: CallbackQuery):
    """Вернуться к выбору периода"""
    try:
        await callback.answer()
        await callback.message.edit_text(
            "Выберите период для просмотра расписания:",
            reply_markup=kb.public_schedule_options()
        )
    except Exception as e:
        logger.error(f"Ошибка возврата к выбору периода: {e}")
        await callback.message.answer("Ошибка возврата к выбору периода", reply_markup=kb.main)


# ===== ПРОСМОТР РАСПИСАНИЯ ПО ВИДУ ЭКСКУРСИИ =====


@router.callback_query(F.data.startswith("public_exc_detail:"))
async def show_excursion_public_detail(callback: CallbackQuery):
    """Показать детали экскурсии для пользователя"""
    try:
        exc_id = int(callback.data.split(":")[-1])

        async with async_session() as session:
            exc_repo = ExcursionRepository(session)
            excursion = await exc_repo.get_by_id(exc_id)

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
            await callback.message.edit_text(
                details,
                reply_markup=await kb.get_excursion_details_inline(exc_id)
            )

    except Exception as e:
        logger.error(f"Ошибка показа деталей экскурсии: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке расписания", reply_markup=kb.main)

@router.callback_query(F.data.startswith("public_schedule_exc:"))
async def show_excursion_schedule(callback: CallbackQuery):
    """Показать расписание конкретной экскурсии"""
    try:
        exc_id = int(callback.data.split(":")[-1])
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            excursion, text, slots_by_date = await slot_manager.get_excursion_schedule_period(exc_id, days_ahead=30)

            if not excursion:
                await callback.answer("Экскурсия не найдена", show_alert=True)
                return

            if not slots_by_date:
                text = f"{excursion.name}\n"
                text += f"\nНа ближайшие 30 дней нет доступных записей на экскурсию '{excursion.name}'.\n"
                text += "Пожалуйста, проверьте позже или выберите другую экскурсию."
                await callback.message.edit_text(
                    text=text,
                    reply_markup=await kb.all_excursions_inline()
                )
                return

            # Получаем все слоты для клавиатуры
            all_slots = []
            for date_slots in slots_by_date.values():
                all_slots.extend(date_slots)

            keyboard = await kb.get_excursion_schedule_keyboard(all_slots)
            await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка показа расписания экскурсии: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке расписания", reply_markup=kb.main)

@router.callback_query(F.data.startswith("public_view_exc_date:"))
async def public_view_exc_date(callback: CallbackQuery):
    """Показать слоты конкретной экскурсии на выбранную дату"""
    try:
        parts = callback.data.split(":")
        date_str = parts[1]
        exc_id = int(parts[2])
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            excursion, text, slots = await slot_manager.get_excursion_slots_for_date(exc_id, target_date)

            if not excursion:
                await callback.answer("Экскурсия не найдена", show_alert=True)
                return

            if not slots:
                await callback.answer("На эту дату нет слотов для этой экскурсии", show_alert=True)
                return

            keyboard = kb.public_schedule_date_menu(slots, target_date)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа слотов экскурсии на дату: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке расписания", reply_markup=kb.main)

@router.callback_query(F.data.startswith("public_view_slot:"))
async def public_view_slot_details(callback: CallbackQuery, state: FSMContext):
    """Просмотр деталей слота перед бронированием"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} просматривает детали слота")

    try:
        slot_id = int(callback.data.split(":")[-1])
        await callback.answer()

        async with async_session() as session:
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info or not slot_info.get('slot'):
                logger.warning(f"Слот {slot_id} не найден для пользователя {user_telegram_id}")
                await callback.message.edit_text(
                    "Слот не найден. Возможно, он был удален или изменен.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            slot = slot_info['slot']
            if not slot.excursion:
                logger.error(f"Экскурсия не найдена для слота {slot.id}")
                await callback.message.edit_text(
                    "Ошибка: данные экскурсии не найдены.",
                    reply_markup=kb.main
                )
                return

            if not slot_info.get('is_available', False):
                logger.warning(f"Слот {slot_id} не доступен для бронирования. Статус: {slot.status}")
                await callback.message.edit_text(
                    "Этот слот недоступен для записи.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            weekday = get_weekday_name(slot.start_datetime)

            # Получаем цены через PriceCalculator
            from app.utils.calculators import PriceCalculator
            base_price = slot.excursion.base_price
            price_categories = PriceCalculator.get_price_categories(base_price)

            # Формируем подробное описание без HTML
            slot_info_text = (
                "ДЕТАЛИ ЭКСКУРСИИ\n\n"
                f"Дата: {slot.start_datetime.strftime('%d.%m.%Y')} ({weekday})\n"
                f"Время: {slot.start_datetime.strftime('%H:%M')}\n"
                f"Продолжительность: {slot.excursion.base_duration_minutes} минут\n"
                f"Экскурсия: {slot.excursion.name}\n"
                f"Описание: {slot.excursion.description or 'Нет описания'}\n\n"

                "СТОИМОСТЬ:\n"
                f"Взрослый: {base_price} руб.\n"
                f"Детский билет:\n"
            )

            # Добавляем информацию о детских ценах
            for category in price_categories:
                slot_info_text += f"{category['age_range']}: {category['price']} руб.\n"

            slot_info_text += (
                f"\nОГРАНИЧЕНИЯ:\n"
                f"Максимальное количество человек: {slot.max_people}\n"
                f"Свободных мест: {slot_info.get('available_places', 0)}\n"
                f"Максимальный суммарный вес: {slot.max_weight} кг\n"
                f"Доступный вес: {slot_info.get('available_weight', 0)} кг\n"
            )

            # Добавляем информацию о капитане если есть
            if slot.captain:
                captain_name = f"{slot.captain.full_name}"
                slot_info_text += f"\nКапитан: {captain_name}"

            # Добавляем предупреждение если мест мало
            if slot_info.get('available_places', 0) <= 2:
                slot_info_text += f"\n\nОсталось всего {slot_info['available_places']} места!"

            # Создаем клавиатуру [Записаться][Вернуться]
            builder = InlineKeyboardBuilder()
            builder.button(
                text="Записаться",
                callback_data=f"public_book_slot:{slot_id}"
            )
            builder.button(
                text="Вернуться",
                callback_data="public_schedule_back"
            )
            builder.adjust(1)

            # Отправляем сообщение с клавиатурой
            await callback.message.edit_text(
                slot_info_text,
                reply_markup=builder.as_markup()
            )

            logger.debug(f"Показаны детали слота {slot_id} пользователю {user_telegram_id}")

    except ValueError as e:
        logger.error(f"Ошибка парсинга slot_id для пользователя {user_telegram_id}: {e}")
        await callback.message.answer("Ошибка: некорректный идентификатор слота", reply_markup=kb.main)

    except Exception as e:
        logger.error(
            f"Ошибка показа деталей слота для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await callback.message.answer(
            "Произошла ошибка при загрузке деталей. Попробуйте позже.",
            reply_markup=kb.main
        )

@router.callback_query(F.data == "public_schedule_back")
async def public_schedule_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к расписанию из деталей слота"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} вернулся к расписанию")

    # Очищаем состояние если есть
    await state.clear()

    # Получаем последнюю выбранную дату из state или используем сегодняшнюю
    data = await state.get_data()
    target_date = data.get("schedule_target_date", date.today())

    # Показываем расписание на выбранную дату
    await show_date_schedule(callback, target_date, is_callback=True)

    await callback.answer()


@router.callback_query(F.data == "public_back_to_date_schedule")
async def back_to_schedule_options(callback: CallbackQuery, state: FSMContext):
    """Возврат к опциям расписания из просмотра даты"""
    logger.info(f"Пользователь {callback.from_user.id} вернулся к опциям расписания")

    try:
        await callback.answer()
        await state.clear()

        await callback.message.edit_text(
            "Выберите период для просмотра расписания:",
            reply_markup=kb.public_schedule_options()
        )

    except Exception as e:
        logger.error(f"Ошибка возврата к опциям расписания: {e}", exc_info=True)
        await callback.message.answer(
            "Выберите период для просмотра расписания:",
            reply_markup=kb.public_schedule_options()
        )

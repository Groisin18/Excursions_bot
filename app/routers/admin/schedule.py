from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, date
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional

from app.admin_panel.states_adm import AddToSchedule, AdminStates, RescheduleSlot
from app.database.requests import DatabaseManager
from app.database.models import async_session, SlotStatus, BookingStatus
from app.utils.validation import Validators
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu, schedule_view_options,
    slot_actions_menu, schedule_back_menu, conflict_resolution_keyboard,
    captains_selection_menu, time_slot_menu, schedule_management_menu,
    slot_action_confirmation_menu, excursions_selection_menu_for_schedule,
    schedule_slots_management_menu, no_captains_options_menu,
    captain_conflict_keyboard
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_admin_logger


router = Router(name="admin_schedule")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = get_admin_logger()


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


# ===== СОЗДАНИЕ СЛОТА =====

@router.message(F.text == "Добавить экскурсию в расписание")
async def add_to_schedule(message: Message):
    """Добавить экскурсию в расписание"""
    logger.info(f"Администратор {message.from_user.id} хочет добавить экскурсию в расписание")

    try:
        # Показываем меню для выбора экскурсии
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursions = await db_manager.get_all_excursions(active_only=True)

            if not excursions:
                await message.answer(
                    "Нет активных экскурсий. Сначала создайте экскурсию.", reply_markup=schedule_back_menu()
                )
                return

            await message.answer(
                "Выберите экскурсию для добавления в расписание:",
                reply_markup=excursions_selection_menu_for_schedule(excursions)
            )

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await message.answer("Произошла ошибка при выборе экскурсии для расписания", reply_markup=schedule_back_menu())

@router.callback_query(F.data.startswith("schedule_select_exc:"))
async def schedule_select_excursion(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора экскурсии для расписания"""
    excursion_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал экскурсию {excursion_id} для расписания")

    try:
        await callback.answer()
        await state.update_data(excursion_id=excursion_id)
        await callback.message.answer(
            "Введите дату проведения экскурсии в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ\n"
            "Например: 15.01.2024 или 5.1.26\n"
            "Или нажмите /cancel для отмены"
        )
        await state.set_state(AddToSchedule.waiting_for_date)

    except Exception as e:
        logger.error(f"Ошибка обработки выбора экскурсии: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при выборе экскурсии", reply_markup=schedule_back_menu())

@router.message(AddToSchedule.waiting_for_date)
async def handle_schedule_date(message: Message, state: FSMContext):
    """Обработка ввода даты для расписания"""
    logger.info(f"Администратор {message.from_user.id} ввел дату: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer("Ввод даты отменен.", reply_markup=schedule_exc_management_menu())
            return

        slot_date = Validators.validate_slot_date(message.text)

        await state.update_data(slot_date=slot_date)
        data = await state.get_data()
        excursion_id = data.get('excursion_id')

        if not excursion_id:
            logger.error("Excursion ID не найден в состоянии!")
            await message.answer("Ошибка: не выбрана экскурсия. Начните заново.", reply_markup=schedule_back_menu())
            await state.clear()
            return

        date_str = slot_date.strftime('%d.%m.%Y')

        await message.answer(
            f"Выбрана дата: {date_str}\n"
            f"Выберите время начала:",
            reply_markup=time_slot_menu(date_str, excursion_id)
        )

    except Exception as e:
        logger.error(f"Ошибка обработки даты расписания: {e}", exc_info=True)
        await message.answer(str(e))

@router.callback_query(F.data.startswith("select_time;"))
async def handle_time_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора времени из клавиатуры"""
    try:
        await callback.answer()

        # Парсим данные: select_time;2024-01-15;excursion_id;14:30
        parts = callback.data.split(";")
        date_str = parts[1]
        excursion_id = int(parts[2])
        time_str = parts[3]

        data = await state.get_data()
        slot_date = data.get('slot_date')
        validated_time = Validators.validate_slot_time(time_str)
        start_datetime = datetime.combine(slot_date, validated_time)

        # Проверяем, что время не в прошлом
        now = datetime.now()
        if start_datetime < now:
            await callback.message.answer(
                "Нельзя добавлять экскурсии на прошедшее время. "
                "Пожалуйста, выберите другое время."
            )
            await callback.message.answer(
                "Выберите время:",
                reply_markup=time_slot_menu(date_str, excursion_id)
            )
            return

        await state.update_data(
            start_datetime=start_datetime,
            excursion_id=excursion_id,
        )

        # Переходим к выбору вместимости
        await state.set_state(AddToSchedule.waiting_for_capacity)

        await callback.message.answer(
            f"Выбрано время: {time_str}\n\n"
            "Введите максимальную вместимость экскурсии (количество человек)\n"
            "Введите число:"
        )

    except Exception as e:
        logger.error(f"Ошибка выбора времени: {e}", exc_info=True)
        await callback.message.answer(str(e))

@router.callback_query(F.data.startswith("custom_time:"))
async def handle_custom_time_request(callback: CallbackQuery, state: FSMContext):
    """Запрос ручного ввода времени"""
    try:
        await callback.answer()
        await state.set_state(AddToSchedule.waiting_for_time)

        await callback.message.answer(
            "Введите время начала экскурсии в формате ЧЧ:ММ\n"
            "Например: 14:30\n\n"
            "Или нажмите /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка запроса ручного ввода времени: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.message(AddToSchedule.waiting_for_time)
async def handle_schedule_time(message: Message, state: FSMContext):
    """Обработка ручного ввода времени для расписания"""
    logger.info(f"Администратор {message.from_user.id} ввел время вручную: '{message.text}'")

    # Проверяем команду отмены
    if message.text.lower() == "/cancel":
        await state.clear()
        await message.answer("Ввод времени отменен.", reply_markup=schedule_exc_management_menu())
        return

    try:
        validated_time = Validators.validate_slot_time(message.text)

        data = await state.get_data()
        slot_date = data.get('slot_date')
        start_datetime = datetime.combine(slot_date, validated_time)

        # Проверяем, что время не в прошлом (если сегодняшняя дата)
        now = datetime.now()
        if start_datetime < now:
            await message.answer(
                "Нельзя добавлять экскурсии на прошедшее время. "
                "Пожалуйста, введите будущее время."
            )
            return

        await state.update_data(start_datetime=start_datetime)
        await state.set_state(AddToSchedule.waiting_for_capacity)

        await message.answer(
            "Введите максимальную вместимость экскурсии (количество человек)\n"
            "Введите число:"
        )
    except Exception as e:
        logger.error(f"Ошибка обработки ручного ввода времени: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.message(AddToSchedule.waiting_for_capacity)
async def handle_schedule_capacity(message: Message, state: FSMContext):
    """Обработка ввода вместимости и переход к весу"""
    logger.info(f"Администратор {message.from_user.id} ввел вместимость: '{message.text}'")

    try:
        # Валидируем вместимость
        try:
            max_people = int(message.text)
            if max_people < 1 or max_people > 50:
                await message.answer(
                    "Вместимость должна быть от 1 до 50 человек. "
                    "Пожалуйста, введите корректное число."
                )
                return
        except ValueError:
            await message.answer(
                "Пожалуйста, введите число от 1 до 50."
            )
            return

        # Сохраняем вместимость и переходим к весу
        await state.update_data(max_people=max_people)
        await state.set_state(AddToSchedule.waiting_for_max_weight)

        await message.answer(
            "Введите максимальный совместный вес группы (в кг, включая капитана)\n"
            "Примерные расчеты:\n"
            "• 10 человек × 70кг = 700кг\n"
            "• 15 человек × 70кг = 1050кг\n"
            "• 20 человек × 70кг = 1400кг\n\n"
            "Введите число:"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки вместимости: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке вместимости", reply_markup=schedule_back_menu())

@router.message(AddToSchedule.waiting_for_max_weight)
async def handle_max_weight(message: Message, state: FSMContext):
    """Обработка ввода максимального веса и переход к выбору капитана"""
    logger.info(f"Администратор {message.from_user.id} ввел вес: '{message.text}'")

    try:
        # Валидируем вес
        try:
            max_weight = int(message.text)
            if max_weight < 50 or max_weight > 3000:
                await message.answer(
                    "Вес должен быть от 50 до 3000 кг. "
                    "Пожалуйста, введите корректное число."
                )
                return
        except ValueError:
            await message.answer("Пожалуйста, введите число от 50 до 3000.")
            return

        await state.update_data(max_weight=max_weight)

        data = await state.get_data()
        start_datetime = data.get('start_datetime')
        excursion_id = data.get('excursion_id')
        max_people = data.get('max_people')

        async with async_session() as session:
            db_manager = DatabaseManager(session)

            excursion = await db_manager.get_excursion_by_id(excursion_id)
            if not excursion:
                await message.answer("Ошибка: данный вид экскурсии не найден.", reply_markup=schedule_back_menu())
                await state.clear()
                return

            end_datetime = start_datetime + timedelta(minutes=excursion.base_duration_minutes)

            available_captains = await db_manager.get_available_captains(
                start_datetime=start_datetime,
                end_datetime=end_datetime
            )

            await state.update_data(
                end_datetime=end_datetime,
                excursion_duration=excursion.base_duration_minutes
            )

            await state.set_state(AddToSchedule.waiting_for_captain_selection)

            slot_date = start_datetime.date()
            slot_time = start_datetime.strftime("%H:%M")

            # Создаем временный ID слота (будет заменен на реальный после создания)
            # Используем negative ID для обозначения, что это временный слот
            temp_slot_id = -1

            if available_captains:
                response = (
                    f"Данные слота:\n"
                    f"Дата: {slot_date.strftime('%d.%m.%Y')}\n"
                    f"Время: {slot_time}\n"
                    f"Людей: {max_people}\n"
                    f"Макс. вес: {max_weight} кг\n\n"
                    f"Доступно капитанов: {len(available_captains)}"
                )

                await message.answer(response)

                await message.answer(
                    "Выберите капитана:",
                    reply_markup=captains_selection_menu(
                        item_id=temp_slot_id,
                        captains=available_captains,
                        callback_prefix="select_captain_for_new_slot",
                        include_back=True,
                        back_callback="back_to_weight_input",
                        include_remove=False
                    )
                )
            else:
                # Нет доступных капитанов
                response = (
                    f"На {slot_date.strftime('%d.%m.%Y')} в {slot_time} "
                    "нет свободных капитанов.\n\n"
                    "Выберите действие:\n"
                )

                await message.answer(response, reply_markup=no_captains_options_menu())


    except Exception as e:
        logger.error(f"Ошибка обработки максимального веса: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке веса", reply_markup=schedule_back_menu())
        await state.clear()

class ExcursionSlotCreate(BaseModel):
    """Модель для создания слота экскурсии"""

    excursion_id: int = Field(..., gt=0, description="ID экскурсии")
    start_datetime: datetime = Field(..., description="Дата и время начала")
    max_people: int = Field(..., gt=0, le=50, description="Максимальное количество людей")
    max_weight: int = Field(..., gt=0, le=3000, description="Максимальный суммарный вес (кг)")
    captain_id: Optional[int] = Field(None, gt=0, description="ID капитана (опционально)")

    @field_validator('start_datetime')
    @classmethod
    def validate_start_datetime(cls, v: datetime) -> datetime:
        """Проверяем, что дата не в прошлом"""
        if v < datetime.now():
            raise ValueError("Нельзя создавать слоты на прошедшее время")
        return v

    @field_validator('max_weight')
    @classmethod
    def validate_max_weight(cls, v: int, info) -> int:
        """Проверяем соотношение веса и количества людей"""
        values = info.data

        if 'max_people' in values:
            max_people = values['max_people']

            # Минимальный средний вес - 30кг (дети), максимальный - 120кг
            min_avg_weight = 30
            max_avg_weight = 120

            min_recommended = max_people * min_avg_weight
            max_recommended = max_people * max_avg_weight

            if v < min_recommended:
                raise ValueError(
                    f"Слишком маленький максимальный вес. "
                    f"Для {max_people} человек рекомендуется минимум {min_recommended}кг"
                )

            if v > max_recommended:
                raise ValueError(
                    f"Слишком большой максимальный вес. "
                    f"Для {max_people} человек рекомендуется максимум {max_recommended}кг"
                )

        return v

@router.callback_query(F.data.startswith("select_captain_for_new_slot:"))
async def select_captain_for_new_slot(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора капитана для нового слота"""
    try:
        await callback.answer()

        captain_id = int(callback.data.split(":")[2])
        data = await state.get_data()

        try:
            slot_data = ExcursionSlotCreate(
                excursion_id=data['excursion_id'],
                start_datetime=data['start_datetime'],
                max_people=data['max_people'],
                max_weight=data['max_weight'],
                captain_id=captain_id
            )
        except ValidationError as e:
            logger.error(f"Ошибка валидации: {e}")
            await callback.message.answer("Ошибка валидации данных")
            await state.clear()
            return

        # Создаем слот
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            slot = await db_manager.create_excursion_slot(
                excursion_id=slot_data.excursion_id,
                start_datetime=slot_data.start_datetime,
                max_people=slot_data.max_people,
                max_weight=slot_data.max_weight,
                captain_id=slot_data.captain_id
            )

            if slot:
                excursion = await db_manager.get_excursion_by_id(slot_data.excursion_id)
                await callback.message.answer(
                    "Экскурсия успешно добавлена в расписание!\n\n"
                    f"Экскурсия: {excursion.name}\n"
                    f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Продолжительность: {excursion.base_duration_minutes} мин.\n"
                    f"Вместимость: {slot.max_people} человек\n"
                    f"Вместимость по весу: {slot.max_weight} кг\n"
                    f"Слот ID: {slot.id}\n\n"
                )
                await state.clear()
                await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_exc_management_menu()
                )

            else:
                logger.error(f"Ошибка создания слота")
                await state.clear()
                await callback.message.answer("Ошибка добавления экскурсии в расписание!\n"
                                              "Возможно, на данное время "
                                              "уже назначена данная экскурсия, или произошла другая ошибка.\n"
                                              "Пожалуйста, попробуйте назначить экскурсию заново.", reply_markup=schedule_back_menu())

    except Exception as e:
        logger.error(f"Ошибка выбора капитана: {e}", exc_info=True)
        await callback.message.answer("Ошибка при выборе капитана", reply_markup=schedule_back_menu())
        await state.clear()

@router.callback_query(F.data == "create_without_captain")
async def create_without_captain(callback: CallbackQuery, state: FSMContext):
    """Создание слота без капитана"""
    try:
        await callback.answer()

        data = await state.get_data()

        try:
            slot_data = ExcursionSlotCreate(
                excursion_id=data['excursion_id'],
                start_datetime=data['start_datetime'],
                max_people=data['max_people'],
                max_weight=data['max_weight'],
                captain_id=None
            )
        except ValidationError as e:
            logger.error(f"Ошибка валидации: {e}")
            await callback.message.answer("Ошибка валидации данных")
            await state.clear()
            return

        async with async_session() as session:
            db_manager = DatabaseManager(session)

            slot = await db_manager.create_excursion_slot(
                excursion_id=slot_data.excursion_id,
                start_datetime=slot_data.start_datetime,
                max_people=slot_data.max_people,
                max_weight=slot_data.max_weight,
                captain_id=None
            )

            if slot:
                excursion = await db_manager.get_excursion_by_id(slot_data.excursion_id)
                await callback.message.answer(
                    "Экскурсия успешно добавлена в расписание!\n\n"
                    f"Экскурсия: {excursion.name}\n"
                    f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Продолжительность: {excursion.base_duration_minutes} мин.\n"
                    f"Вместимость: {slot.max_people} человек\n"
                    f"Вместимость по весу: {slot.max_weight} кг\n"
                    f"Слот ID: {slot.id}\n\n"
                    "Не забудьте назначить капитана в ближайшее время"
                )
                await callback.message.answer(f"Слот создан без капитана! ID: {slot.id}")
                await state.clear()
                await callback.message.answer(
                "Выберите действие:",
                reply_markup=schedule_exc_management_menu()
                )
            else:
                logger.error(f"Ошибка создания слота")
                await state.clear()
                await callback.message.answer("Ошибка добавления экскурсии в расписание!\n"
                                              "Возможно, на данное время "
                                              "уже назначена данная экскурсия, или произошла другая ошибка.\n"
                                              "Пожалуйста, попробуйте назначить экскурсию заново.", reply_markup=schedule_back_menu())

    except Exception as e:
        logger.error(f"Ошибка создания без капитана: {e}", exc_info=True)
        await callback.message.answer("Ошибка создания слота", reply_markup=schedule_back_menu())
        await state.clear()

@router.callback_query(F.data == "back_to_weight_input")
async def handle_back_to_weight_input(callback: CallbackQuery, state: FSMContext):
    """Возврат к вводу максимального веса"""
    try:
        await callback.answer()

        await state.set_state(AddToSchedule.waiting_for_max_weight)

        data = await state.get_data()
        max_people = data.get('max_people', 10)

        await callback.message.answer(
            f"Введите максимальный совместный вес группы (в кг)\n"
            f"Для {max_people} человек рекомендуется {max_people * 70}кг\n"
            "Или введите /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка возврата к весу: {e}")
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.callback_query(F.data == "change_time")
async def handle_change_time(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору времени"""
    try:
        await callback.answer()

        data = await state.get_data()
        slot_date = data.get('slot_date')
        excursion_id = data.get('excursion_id')

        if slot_date and excursion_id:
            date_str = slot_date.strftime("%d.%m.%Y")
            await callback.message.answer(
                f"Выберите время для даты {date_str}:",
                reply_markup=time_slot_menu(date_str, excursion_id)
            )
            await state.set_state(AddToSchedule.waiting_for_time)
        else:
            await callback.message.answer("Не удалось вернуться к выбору времени", reply_markup=schedule_back_menu())
            await state.clear()

    except Exception as e:
        logger.error(f"Ошибка смены времени: {e}")
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.callback_query(F.data == "cancel_slot_creation")
async def handle_cancel_slot_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания слота"""
    try:
        await callback.answer()
        await state.clear()
        await callback.message.answer(
            "Создание слота отменено.",
            reply_markup=schedule_management_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка отмены: {e}")
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.callback_query(F.data == "add_to_schedule")
async def add_to_schedule_callback(callback: CallbackQuery):
    """Добавление в расписание (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} выбрал добавление в расписание")

    try:
        await callback.answer()
        await add_to_schedule(callback.message)
    except Exception as e:
        logger.error(f"Ошибка в add_to_schedule: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())

@router.callback_query(F.data.startswith("add_to_date:"))
async def add_to_specific_date_callback(callback: CallbackQuery, state: FSMContext):
    """Добавление экскурсии на конкретную дату"""
    date_str = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} хочет добавить экскурсию на дату {date_str}")

    try:
        await callback.answer()

        # Парсим дату
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Сохраняем дату в состоянии
        await state.update_data(slot_date=target_date)

        # Получаем список экскурсий
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursions = await db_manager.get_all_excursions(active_only=True)

            if not excursions:
                await callback.message.answer(
                    "Нет активных экскурсий. Сначала создайте экскурсию.", reply_markup=schedule_back_menu()
                )
                await state.clear()
                return
            await callback.message.answer(
                f"Выберите экскурсию для добавления на {target_date.strftime('%d.%m.%Y')}:",
                reply_markup=excursions_selection_menu_for_schedule(excursions)
            )
    except Exception as e:
        logger.error(f"Ошибка начала добавления на дату: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=schedule_back_menu())
        await state.clear()


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

async def format_schedule_for_date(target_date: date, slots: list, db_manager: DatabaseManager) -> str:
    """
    Форматировать расписание на конкретную дату в текстовый вид

    Args:
        target_date: Дата расписания
        slots: Список слотов
        db_manager: Менеджер базы данных для получения дополнительной информации

    Returns:
        Отформатированная строка с расписанием
    """
    response = f"Расписание на {target_date.strftime('%d.%m.%Y (%A)')}:\n\n"

    for slot in slots:
        excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
        excursion_name = excursion.name if excursion else "Неизвестная экскурсия"

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
            target_date = Validators.validate_slot_date(message.text)
        except Exception as e:
            logger.error(f"Ошибка валидации даты: {str(e)}", exc_info=True)
            await message.answer(str(e))

        # Получаем слоты на эту дату
        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

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

            response = await format_schedule_for_date(target_date, slots, db_manager)
            await message.answer(response)
            await message.answer(
                "Выберите действие:",
                reply_markup=schedule_slots_management_menu(slots, target_date)
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
        date_from = datetime.combine(today, datetime.min.time())
        date_to = datetime.combine(today, datetime.max.time())

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    f"На сегодня ({today.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            response = f"Расписание на сегодня ({today.strftime('%d.%m.%Y')}):\n\n"

            for slot in slots:
                excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
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
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

            if not slots:
                await callback.message.answer(
                    f"На завтра ({tomorrow.strftime('%d.%m.%Y')}) нет запланированных экскурсий."
                )
                return

            response = f"Расписание на завтра ({tomorrow.strftime('%d.%m.%Y')}):\n\n"

            for slot in slots:
                excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
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
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

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
                    excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
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
            slots = await db_manager.get_excursion_schedule(date_from, date_to)

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
                    excursion = await db_manager.get_excursion_by_id(slot.excursion_id)
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


# ===== УПРАВЛЕНИЕ СЛОТОМ =====

@router.callback_query(F.data.startswith("manage_slot:"))
async def manage_slot_callback(callback: CallbackQuery):
    """Управление конкретным слотом"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} управляет слотом {slot_id}")

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
                f"Управление слотом #{slot.id}\n\n"
                f"Экскурсия: {excursion.name}\n"
                f"Дата и время: {slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"Продолжительность: {excursion.base_duration_minutes} мин.\n"
                f"Количество свободных мест: {slot.max_people - await db_manager.get_booked_places_for_slot(slot.id)}/{slot.max_people}\n"
                f"Занятость по максимально допустимому весу: {await db_manager.get_current_weight_for_slot(slot.id)}/{slot.max_weight}\n"
                f"Статус: {slot.status.value}\n"
            )

            # Информация о капитане
            if slot.captain:
                response += f"Капитан: {slot.captain.full_name}\n"
            else:
                response += "Капитан: не назначен\n"

            # Информация о бронированиях
            if slot.bookings:
                response += f"\nБронирования ({len(slot.bookings)}):\n"
                for booking in slot.bookings:
                    client = booking.client
                    response += (
                        f"• {client.full_name} "
                        f"({booking.adults_count}+{booking.children_count})\n"
                    )

            await callback.message.answer(response)

            # Используем клавиатуру из keyboards_adm.py
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=slot_actions_menu(slot_id)
            )

    except Exception as e:
        logger.error(f"Ошибка управления слотом {slot_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при управлении слотом")

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
                action_text="Да, отменить слот",
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
                        reply_markup=conflict_resolution_keyboard(slot_id)
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
        reply_markup=conflict_resolution_keyboard(slot_id)
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
                reply_markup=no_captains_options_menu()
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
                        reply_markup=conflict_resolution_keyboard(slot_id)
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
            reply_markup=conflict_resolution_keyboard(slot_id)
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
    """Показать свободных капитанов (упрощенная версия)"""
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
            await callback.message.answer("Нет свободных капитанов на это время.")

            # Предлагаем альтернативы
            await callback.message.answer(
                "Вы можете:\n"
                "1. Выбрать другое время\n"
                "2. Отменить перенос",
                reply_markup=no_captains_options_menu()
            )

@router.callback_query(F.data == "create_without_captain")
async def create_without_captain(callback: CallbackQuery, state: FSMContext):
    """Создание перенесенного слота без капитана"""
    await callback.answer()

    data = await state.get_data()
    slot_id = data.get('slot_id')
    new_datetime = data.get('new_datetime')

    if not new_datetime:
        await callback.message.answer("Ошибка: время не указано.")
        await state.clear()
        return

    async with async_session() as session:
        db_manager = DatabaseManager(session)

        # Переносим слот без капитана (капитана оставляем как есть или снимаем)
        success, error_message = await db_manager.reschedule_slot(slot_id, new_datetime)

        if success:
            # Можно снять капитана, если он был
            slot = await db_manager.get_slot_by_id(slot_id)
            if slot and slot.captain_id:
                # Оставляем капитана, просто переносим слот
                captain = await db_manager.get_user_by_id(slot.captain_id)
                captain_name = captain.full_name if captain else f"ID {slot.captain_id}"

                await callback.message.answer(
                    f"Слот #{slot_id} перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Капитан остался прежним: {captain_name}\n\n"
                    f"Внимание: капитан может быть занят в новое время!"
                )
            else:
                await callback.message.answer(
                    f"Слот #{slot_id} перенесен на "
                    f"{new_datetime.strftime('%d.%m.%Y %H:%M')} без капитана."
                )

            await state.clear()
        else:
            await callback.message.answer(
                f"Не удалось перенести слот.\n"
                f"Причина: {error_message}"
            )

@router.callback_query(F.data.startswith("cancel_reschedule:"))
async def cancel_reschedule_process(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса переноса"""
    await callback.answer()
    await state.clear()
    await callback.message.answer("Перенос отменен.")
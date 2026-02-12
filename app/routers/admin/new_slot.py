from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional

from app.database.repositories import ExcursionRepository, UserRepository
from app.database.managers import SlotManager
from app.database.unit_of_work import UnitOfWork
from app.database.session import async_session

from app.admin_panel.states_adm import AddToSchedule
from app.admin_panel.keyboards_adm import (
    schedule_exc_management_menu, schedule_back_menu,
    captains_selection_menu, time_slot_menu, schedule_captains_management_menu,
    excursions_selection_menu_for_schedule, no_captains_options_menu
)
from app.middlewares import AdminMiddleware

from app.utils.validation import validate_slot_date, validate_slot_time
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_new_slot")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


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

            # Минимальный средний вес - 10кг (дети), максимальный - 160кг
            min_avg_weight = 10
            max_avg_weight = 160

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


# ===== СОЗДАНИЕ СЛОТА =====


@router.message(F.text == "Добавить экскурсию в расписание")
async def add_to_schedule(message: Message):
    """Добавить экскурсию в расписание"""
    logger.info(f"Администратор {message.from_user.id} хочет добавить экскурсию в расписание")

    try:
        # Показываем меню для выбора экскурсии
        async with async_session() as session:
            exc_repo = ExcursionRepository(session)
            excursions = await exc_repo.get_all(active_only=True)

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
    await callback.answer()

    try:

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
        await state.clear()

@router.message(AddToSchedule.waiting_for_date)
async def handle_schedule_date(message: Message, state: FSMContext):
    """Обработка ввода даты для расписания"""
    logger.info(f"Администратор {message.from_user.id} ввел дату: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer("Ввод даты отменен.", reply_markup=schedule_exc_management_menu())
            return

        slot_date = validate_slot_date(message.text)

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
        await message.answer(str(e), reply_markup=schedule_back_menu())
        await state.clear()

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
        validated_time = validate_slot_time(time_str)
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
        await callback.message.answer(str(e), reply_markup=schedule_back_menu())

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
        validated_time = validate_slot_time(message.text)

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
            exc_repo = ExcursionRepository(session)
            user_repo = UserRepository(session)

            excursion = await exc_repo.get_by_id(excursion_id)
            if not excursion:
                await message.answer("Ошибка: данный вид экскурсии не найден.", reply_markup=schedule_back_menu())
                await state.clear()
                return

            end_datetime = start_datetime + timedelta(minutes=excursion.base_duration_minutes)

            available_captains = await user_repo.get_available_captains(
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

                await message.answer(response, reply_markup=no_captains_options_menu(context="create"))


    except Exception as e:
        logger.error(f"Ошибка обработки максимального веса: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке веса", reply_markup=schedule_back_menu())
        await state.clear()

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
            await callback.message.answer(f"Ошибка валидации данных: {e}")
            await state.clear()
            return

        # Создаем слот
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                exc_repo = ExcursionRepository(uow.session)
                slot_manager = SlotManager(uow.session)

                slot = await slot_manager.create_slot(
                    excursion_id=slot_data.excursion_id,
                    start_datetime=slot_data.start_datetime,
                    max_people=slot_data.max_people,
                    max_weight=slot_data.max_weight,
                    captain_id=slot_data.captain_id
                )

                if not slot:
                    logger.error("Ошибка создания слота")
                    await state.clear()
                    await callback.message.answer(
                        "Ошибка добавления экскурсии в расписание!\n"
                        "Возможно, на данное время уже назначена данная экскурсия, "
                        "или произошла другая ошибка.\n"
                        "Пожалуйста, попробуйте назначить экскурсию заново.",
                        reply_markup=schedule_back_menu()
                    )
                    return

                excursion = await exc_repo.get_by_id(slot_data.excursion_id)

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

    except Exception as e:
        logger.error(f"Ошибка выбора капитана: {e}", exc_info=True)
        await callback.message.answer(
            "Ошибка при выборе капитана",
            reply_markup=schedule_back_menu()
        )
        await state.clear()

@router.callback_query(F.data == "create_without_captain")
async def create_without_captain(callback: CallbackQuery, state: FSMContext):
    """Создание слота без капитана"""
    logger.info(f"Админ {callback.from_user.id} создает слот без капитана")
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
            await callback.message.answer("Ошибка валидации данных", reply_markup=schedule_back_menu())
            await state.clear()
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                exc_repo = ExcursionRepository(uow.session)
                slot_manager = SlotManager(uow.session)

                slot = await slot_manager.create_slot(
                    excursion_id=slot_data.excursion_id,
                    start_datetime=slot_data.start_datetime,
                    max_people=slot_data.max_people,
                    max_weight=slot_data.max_weight,
                    captain_id=None
                )

                if not slot:
                    logger.error("Ошибка создания слота")
                    await state.clear()
                    await callback.message.answer(
                        "Ошибка добавления экскурсии в расписание!\n"
                        "Возможно, на данное время уже назначена данная экскурсия, "
                        "или произошла другая ошибка.\n"
                        "Пожалуйста, попробуйте назначить экскурсию заново.",
                        reply_markup=schedule_back_menu()
                    )
                    return

                excursion = await exc_repo.get_by_id(slot_data.excursion_id)

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
        await state.clear()

@router.callback_query(F.data == "cancel_slot_creation")
async def handle_cancel_slot_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания слота"""
    try:
        await callback.answer()
        await state.clear()
        await callback.message.answer(
            "Создание слота отменено.",
            reply_markup=schedule_captains_management_menu()
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

        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        await state.update_data(slot_date=target_date)

        async with async_session() as session:
            exc_repo = ExcursionRepository(session)
            excursions = await exc_repo.get_all(active_only=True)

            if not excursions:
                await callback.message.answer(
                    "Нет активных экскурсий. Сначала создайте экскурсию.",
                    reply_markup=schedule_back_menu()
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
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database.requests import DatabaseManager
from app.database.models import async_session, SlotStatus, BookingStatus
from app.utils.logging_config import get_logger
from app.user_panel.states import UserBookingStates
from app.utils.datetime_utils import get_weekday_name

import app.user_panel.keyboards as kb


router = Router(name="user_booking")
logger = get_logger(__name__)


@router.callback_query(F.data.startswith("public_book_slot:"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал бронирование")

    try:
        slot_id = int(callback.data.split(":")[-1])

        await callback.answer()

        async with async_session() as session:
            db = DatabaseManager(session)

            slot = await db.get_slot_by_id(slot_id)
            if not slot:
                logger.warning(f"Слот {slot_id} не найден для пользователя {user_telegram_id}")
                await callback.message.answer(
                    "Слот не найден. Возможно, он был удален или изменен.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            if slot.status != SlotStatus.scheduled:
                logger.warning(f"Слот {slot_id} не доступен для бронирования. Статус: {slot.status}")
                await callback.message.answer(
                    "Этот слот недоступен для записи.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            booked_places = await db.get_booked_places_for_slot(slot.id)
            if booked_places >= slot.max_people:
                logger.info(f"Нет свободных мест в слоте {slot_id} для пользователя {user_telegram_id}")
                await callback.message.answer(
                    "На этот слот нет свободных мест.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            user = await db.get_user_by_telegram_id(user_telegram_id)
            if not user:
                logger.error(f"Пользователь {user_telegram_id} не найден в БД")
                await callback.message.answer(
                    "Вы не зарегистрированы в системе. Пожалуйста, завершите регистрацию.",
                    reply_markup=kb.main
                )
                return

            existing_booking = await db.get_user_active_booking_for_slot(user.id, slot.id)
            if existing_booking:
                logger.info(f"У пользователя {user.id} уже есть активная бронь на слот {slot.id}")
                await callback.message.answer(
                    "У вас уже есть активное бронирование на этот слот.",
                    reply_markup=kb.public_schedule_options()
                )
                return

            # Теперь slot.excursion точно загружен благодаря исправленному методу
            excursion = slot.excursion
            if not excursion:
                logger.error(f"Экскурсия не найдена для слота {slot.id}")
                await callback.message.answer(
                    "Ошибка: данные экскурсии не найдены.",
                    reply_markup=kb.main
                )
                return

            current_weight = await db.get_current_weight_for_slot(slot.id)
            available_weight = slot.max_weight - current_weight

            user_has_children = await db.user_has_children(user.id)

            weekday = get_weekday_name(slot.start_datetime)

            excursion_info = (
                "Начинаем бронирование:\n\n"
                f"Дата: {slot.start_datetime.strftime('%d.%m.%Y')} ({weekday})\n"
                f"Время: {slot.start_datetime.strftime('%H:%M')}\n"
                f"Экскурсия: {excursion.name}\n"
                f"Продолжительность: {excursion.base_duration_minutes} мин.\n\n"

            )

            excursion_info += (
                f"\nОграничения:\n"
                f"• Свободных мест: {slot.max_people - booked_places}/{slot.max_people}\n"
                f"• Доступный вес: {available_weight} кг\n"
            )

            if user.weight is None:
                excursion_info += "\nВнимание: ваш вес не указан в профиле. Он будет запрошен на следующем шаге.\n"

            await state.update_data({
                "slot_id": slot.id,
                "user_id": user.id,
                "adult_weight": user.weight,
                "user_has_children": user_has_children,
                "available_weight": available_weight,
                "max_weight": slot.max_weight,
                "adult_price": excursion.base_price
            })

            await callback.message.answer(excursion_info, reply_markup=await kb.booking_start_confirm_keyboard())
            await state.set_state(UserBookingStates.checking_weight)

            logger.info(
                f"Начало бронирования: пользователь {user.id} (TG: {user_telegram_id}), "
                f"слот {slot.id}, экскурсия {excursion.name}"
            )

    except ValueError as e:
        logger.error(f"Ошибка парсинга slot_id для пользователя {user_telegram_id}: {e}")
        await callback.answer("Ошибка: некорректный идентификатор слота", show_alert=True)

    except Exception as e:
        logger.error(
            f"Ошибка начала бронирования для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await callback.message.answer(
            "Произошла ошибка при начале бронирования. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

@router.callback_query(F.data == ("confirm_start_booking"))
async def check_adult_weight(callback: CallbackQuery, state: FSMContext):
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} на этапе проверки веса")

    try:
        callback.answer('')
        data = await state.get_data()

        # Получаем данные из state
        slot_id = data.get("slot_id")
        user_id = data.get("user_id")
        adult_weight = data.get("adult_weight")  # может быть None
        available_weight = data.get("available_weight")
        max_weight = data.get("max_weight")

        if not all([slot_id, user_id, available_weight is not None]):
            logger.error(f"Недостаточно данных в state для пользователя {user_telegram_id}")
            await callback.message.answer(
                "Ошибка: недостаточно данных. Начните бронирование заново.",
                reply_markup=kb.main
            )
            await state.clear()
            return

        async with async_session() as session:
            db = DatabaseManager(session)

            # Если вес не указан в профиле, запрашиваем его
            if adult_weight is None:
                logger.info(f"Вес пользователя {user_telegram_id} не указан, запрашиваем")
                await state.update_data({"awaiting_weight_input": True})
                await state.set_state(UserBookingStates.requesting_adult_weight)
                await callback.message.answer(
                    "Ваш вес не указан в профиле.\n"
                    "Пожалуйста, введите ваш вес в кг (только цифры, например: 75):\n\n"
                    "Или нажмите /cancel для отмены бронирования"
                )
                return

            # Проверяем вес взрослого
            if adult_weight > available_weight:
                logger.warning(
                    f"Превышение веса: пользователь {user_telegram_id} вес {adult_weight}кг, "
                    f"доступно {available_weight}кг"
                )

                # Получаем текущий занятый вес для полного сообщения
                current_weight = await db.get_current_weight_for_slot(slot_id)

                await callback.message.answer(
                    f"Превышение общего допустимого веса на экскурсию:\n\n"
                    f"Ваш вес: {adult_weight} кг\n"
                    f"Доступный вес: {available_weight} кг\n"
                    f"Максимальный суммарный вес: {max_weight} кг\n"
                    f"Уже занято: {current_weight} кг\n\n"
                    f"К сожалению, вы не можете присоединиться к этой экскурсии.\n"
                    f"Пожалуйста, выберите другой слот или обратитесь к администратору.",
                    reply_markup=kb.public_schedule_options()
                )
                await state.clear()
                return

            # Вес проходит проверку
            logger.info(f"Вес пользователя {user_telegram_id} проверен: {adult_weight}кг из {available_weight}кг доступно")

            # Обновляем доступный вес в state (вычитаем вес взрослого)
            new_available_weight = available_weight - adult_weight
            await state.update_data({
                "available_weight": new_available_weight,
                "total_weight": adult_weight,  # Пока только вес взрослого
                "adults_count": 1  # По умолчанию 1 взрослый
            })

            # Переходим к выбору участников
            await state.set_state(UserBookingStates.selecting_participants)

            user_has_children = data.get("user_has_children", False)

            if user_has_children:
                # Получаем детей пользователя для информации
                children = await db.get_children_users(user_id)
                children_count = len(children)

                await callback.message.answer(
                    f"У вас зарегистрировано детей: {children_count}\n"
                    f"Вы хотите записаться на экскурсию:",
                    reply_markup=await kb.create_participants_keyboard(user_has_children)
                )
            else:
                await callback.message.answer(
                    f"Вы хотите записаться на экскурсию:",
                    reply_markup=await kb.create_participants_keyboard(user_has_children)
                )

    except Exception as e:
        logger.error(
            f"Ошибка проверки веса для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await callback.answer(
            "Произошла ошибка при проверке веса. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

@router.message(UserBookingStates.requesting_adult_weight)
async def request_adult_weight(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} вводит вес")

    try:
        if message.text.lower() == "/cancel":
            await message.answer(
                "Бронирование отменено.",
                reply_markup=kb.main
            )
            await state.clear()
            return

        # Валидация веса
        from app.utils.validation import validate_weight
        try:
            weight = validate_weight(message.text)
        except ValueError as e:
            logger.warning(f"Невалидный вес от пользователя {user_telegram_id}: {message.text}")
            await message.answer(str(e))
            return

        # Сохраняем вес в БД
        async with async_session() as session:
            db = DatabaseManager(session)

            user = await db.get_user_by_telegram_id(user_telegram_id)
            if user:
                await db.update_user_data(user.id, weight=weight)
                logger.info(f"Вес пользователя {user_telegram_id} сохранен в БД: {weight}кг")

        # Обновляем вес в state
        await state.update_data({
            "adult_weight": weight,
            "awaiting_weight_input": False
        })

        # Возвращаемся к проверке веса
        await state.set_state(UserBookingStates.checking_weight)

        # Вызываем проверку веса снова
        await check_adult_weight(message, state)

    except Exception as e:
        logger.error(
            f"Ошибка обработки веса для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await message.answer(
            "Произошла ошибка при сохранении веса. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

@router.callback_query(UserBookingStates.selecting_participants, F.data == "booking_just_me")
async def handle_booking_alone(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Записываюсь только я'"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} выбрал 'Записываюсь только я'")

    try:
        # Обновляем данные в state
        await state.update_data({
            "children_ids": [],
            "children_weights": {},
            "total_children": 0,
            "selected_participants": "alone"
        })

        # Переходим к вводу промокода
        await state.set_state(UserBookingStates.applying_promo_code)

        await callback.message.answer(
            "Вы записываетесь один на экскурсию.\n\n"
            "Если у вас есть промокод, введите его сейчас (например: SUMMER2024).\n"
            "Или нажмите кнопку ниже, чтобы пропустить этот шаг.",
            reply_markup=await kb.create_promo_code_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка обработки выбора 'Записываюсь только я' для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

    await callback.answer()

@router.callback_query(UserBookingStates.selecting_participants, F.data == "booking_with_children")
async def handle_booking_with_children(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Я с детьми'"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} выбрал 'Я с детьми'")

    try:
        data = await state.get_data()
        user_id = data.get("user_id")

        async with async_session() as session:
            db = DatabaseManager(session)

            # Получаем список детей пользователя
            children = await db.get_children_users(user_id)

            if not children:
                logger.warning(f"У пользователя {user_telegram_id} нет зарегистрированных детей")
                await callback.message.answer(
                    "У вас нет зарегистрированных детей в системе.\n"
                    "Пожалуйста, зарегистрируйте детей (Главное меню -> Личный кабинет) или выберите 'Записываюсь только я'.",
                    reply_markup=await kb.create_participants_keyboard(True)
                )
                await callback.answer()
                return

            # Сохраняем список детей в state для использования на следующем шаге
            children_data = []
            for child in children:
                children_data.append({
                    "id": child.id,
                    "full_name": child.full_name,
                    "birthdate": child.date_of_birth,
                    "weight": child.weight,
                    "age": child.age if child.date_of_birth else None
                })

            await state.update_data({
                "available_children": children_data,
                "selected_children_ids": [],  # Пока никого не выбрали
                "children_weights": {},  # Словарь child_id: weight
                "selected_participants": "with_children"
            })

            # Переходим к выбору конкретных детей
            await state.set_state(UserBookingStates.selecting_children)

            # Показываем клавиатуру выбора детей
            await callback.message.answer(
                f"У вас {len(children)} зарегистрированных детей.\n"
                f"Выберите детей, которые поедут с вами (максимум 5):",
                reply_markup=await kb.create_children_selection_keyboard(children, [])
            )

    except Exception as e:
        logger.error(f"Ошибка при выборе детей пользователем {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

    await callback.answer()

@router.callback_query(UserBookingStates.selecting_children, F.data.startswith("select_child:"))
async def handle_child_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора/отмены выбора конкретного ребенка"""
    user_telegram_id = callback.from_user.id

    try:
        # Парсим ID ребенка
        child_id = int(callback.data.split(":")[1])

        data = await state.get_data()
        available_children = data.get("available_children", [])
        selected_ids = data.get("selected_children_ids", [])
        children_weights = data.get("children_weights", {})

        # Проверяем, выбран ли уже этот ребенок
        if child_id in selected_ids:
            # Убираем ребенка из выбранных
            selected_ids.remove(child_id)
            # Убираем его вес если был сохранен
            if child_id in children_weights:
                del children_weights[child_id]

            logger.info(f"Пользователь {user_telegram_id} отменил выбор ребенка {child_id}")
            message_text = f"Ребенок удален из списка. Выбрано: {len(selected_ids)}/5"
        else:
            # Проверяем лимит (максимум 5 детей)
            if len(selected_ids) >= 5:
                await callback.answer(
                    f"Нельзя выбрать более 5 детей. Сейчас выбрано: {len(selected_ids)}",
                    show_alert=True
                )
                return

            # Добавляем ребенка в выбранные
            selected_ids.append(child_id)

            # Находим данные ребенка для информационного сообщения
            child_info = None
            for child in available_children:
                if child["id"] == child_id:
                    child_info = child
                    break

            if child_info:
                age_info = f", {child_info['age']} лет" if child_info.get('age') else ""
                message_text = f"Добавлен: {child_info['full_name']}{age_info}. Выбрано: {len(selected_ids)}/5"
            else:
                message_text = f"Ребенок добавлен. Выбрано: {len(selected_ids)}/5"

            logger.info(f"Пользователь {user_telegram_id} выбрал ребенка {child_id}")

        # Обновляем данные в state
        await state.update_data({
            "selected_children_ids": selected_ids,
            "children_weights": children_weights
        })

        # Обновляем клавиатуру с новым состоянием выбора
        async with async_session() as session:
            db = DatabaseManager(session)

            # Получаем актуальные данные детей
            children_objects = []
            for child_data in available_children:
                child_obj = await db.get_user_by_id(child_data["id"])
                if child_obj:
                    children_objects.append(child_obj)

        await callback.message.edit_reply_markup(
            reply_markup=await kb.create_children_selection_keyboard(children_objects, selected_ids)
        )

        await callback.answer(message_text)

    except ValueError as e:
        logger.error(f"Ошибка парсинга child_id для пользователя {user_telegram_id}: {e}")
        await callback.answer("Ошибка: некорректный идентификатор ребенка", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка выбора ребенка для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)

async def process_to_promo_code(message: Message, state: FSMContext):
    """Переход к вводу промокода после завершения выбора детей"""
    data = await state.get_data()

    # Проверяем общий вес всех участников
    adult_weight = data.get("adult_weight", 0)
    children_weights = data.get("children_weights", {})
    available_weight = data.get("available_weight", 0)

    # Суммируем вес детей
    total_children_weight = sum(children_weights.values())
    total_weight = adult_weight + total_children_weight

    # Проверяем, не превышает ли общий вес доступный
    if total_weight > available_weight:
        await message.answer(
            f"Превышение общего допустимого веса:\n\n"
            f"Общий вес участников: {total_weight} кг\n"
            f"Доступный вес: {available_weight} кг\n\n"
            f"Пожалуйста, уменьшите количество участников или выберите другой слот.",
            reply_markup=kb.public_schedule_options()
        )
        await state.clear()
        return

    # Обновляем общий вес в state
    await state.update_data({
        "total_weight": total_weight,
        "available_weight": available_weight - total_children_weight  # Вычитаем вес детей
    })

    # Переходим к промокоду
    await state.set_state(UserBookingStates.applying_promo_code)

    total_children = len(data.get("selected_children_ids", []))
    participants_text = "1 взрослый"
    if total_children > 0:
        participants_text += f" и {total_children} детей"

    await message.answer(
        f"Вы выбрали: {participants_text}\n"
        f"Общий вес участников: {total_weight} кг\n\n"
        f"Если у вас есть промокод, введите его сейчас (например: SUMMER2024).\n"
        f"Или нажмите кнопку ниже, чтобы пропустить этот шаг.",
        reply_markup=await kb.create_promo_code_keyboard()
    )

async def get_child_info_for_display(child_id: int, db: DatabaseManager) -> dict:
    """Получает информацию о ребенке для отображения"""
    child_user = await db.get_user_by_id(child_id)
    if not child_user:
        return None

    return {
        "id": child_user.id,
        "full_name": child_user.full_name,
        "age": child_user.age,
        "weight": child_user.weight
    }

@router.callback_query(UserBookingStates.selecting_children, F.data == "finish_children_selection")
async def finish_children_selection(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора детей и переход к проверке веса"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} завершил выбор детей")

    try:
        data = await state.get_data()
        selected_ids = data.get("selected_children_ids", [])

        if not selected_ids:
            await callback.answer(
                "Вы не выбрали ни одного ребенка. Пожалуйста, выберите детей или нажмите 'Назад'.",
                show_alert=True
            )
            return

        # Сохраняем финальный список выбранных детей
        await state.update_data({
            "selected_children_ids": selected_ids,
            "total_children": len(selected_ids)
        })

        # Проверяем, нужно ли запрашивать вес для кого-то из детей
        children_without_weight = []
        children_weights = data.get("children_weights", {})

        async with async_session() as session:
            db = DatabaseManager(session)

            for child_id in selected_ids:
                child_info = await get_child_info_for_display(child_id, db)

                if child_info and child_info["weight"] is None and child_id not in children_weights:
                    children_without_weight.append({
                        "id": child_id,
                        "full_name": child_info["full_name"]
                    })

        if children_without_weight:
            # Есть дети без веса - переходим к запросу веса
            await state.update_data({
                "children_without_weight": children_without_weight,
                "current_child_weight_index": 0  # Начинаем с первого ребенка
            })

            # Переходим к запросу веса детей
            await state.set_state(UserBookingStates.requesting_child_weight)

            # Запрашиваем вес для первого ребенка
            first_child = children_without_weight[0]
            await callback.message.answer(
                f"У ребенка {first_child['full_name']} не указан вес в профиле.\n\n"
                f"Пожалуйста, введите вес в кг (только цифры, например: 25):\n"
                f"Или нажмите кнопку для использования среднего веса.",
                reply_markup=await kb.create_child_weight_keyboard(first_child["id"])
            )

        else:
            # У всех детей есть вес - переходим к промокоду
            await process_to_promo_code(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка завершения выбора детей для пользователя {user_telegram_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

    await callback.answer()

@router.callback_query(UserBookingStates.selecting_children, F.data == "back_to_participants")
async def back_to_participants(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа участия"""
    logger.info(f"Пользователь {callback.from_user.id} вернулся к выбору участников")

    data = await state.get_data()
    user_has_children = data.get("user_has_children", False)

    await state.set_state(UserBookingStates.selecting_participants)

    await callback.message.answer(
        "Выберите тип участия:",
        reply_markup=await kb.create_participants_keyboard(user_has_children)
    )

    await callback.answer()

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Отмена бронирования на любом этапе"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} отменил бронирование")

    await state.clear()

    await callback.message.answer(
        "Бронирование отменено.",
        reply_markup=kb.main
    )

    await callback.answer()

@router.message(UserBookingStates.requesting_child_weight)
async def request_child_weight(message: Message, state: FSMContext):
    """Обработка ввода веса ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} вводит вес ребенка")

    try:
        if message.text.lower() == "/cancel":
            await message.answer(
                "Бронирование отменено.",
                reply_markup=kb.main
            )
            await state.clear()
            return

        data = await state.get_data()

        # Получаем текущего ребенка, для которого запрашиваем вес
        children_without_weight = data.get("children_without_weight", [])
        current_index = data.get("current_child_weight_index", 0)

        if current_index >= len(children_without_weight):
            logger.error(f"Индекс {current_index} выходит за пределы списка детей без веса")
            await message.answer(
                "Ошибка: некорректный индекс ребенка. Начните бронирование заново.",
                reply_markup=kb.main
            )
            await state.clear()
            return

        current_child = children_without_weight[current_index]

        # Валидация веса
        from app.utils.validation import validate_weight
        try:
            weight = validate_weight(message.text)
        except ValueError as e:
            logger.warning(f"Невалидный вес ребенка от пользователя {user_telegram_id}: {message.text}")
            await message.answer(str(e))
            return

        # Сохраняем вес ребенка в БД
        async with async_session() as session:
            db = DatabaseManager(session)
            await db.update_user_data(current_child["id"], weight=weight)
            logger.info(f"Вес ребенка {current_child['id']} сохранен в БД: {weight}кг")

        # Обновляем вес в state
        children_weights = data.get("children_weights", {})
        children_weights[current_child["id"]] = weight
        await state.update_data({
            "children_weights": children_weights
        })

        # Переходим к следующему ребенку без веса
        next_index = current_index + 1

        if next_index < len(children_without_weight):
            # Есть еще дети без веса
            await state.update_data({
                "current_child_weight_index": next_index
            })

            next_child = children_without_weight[next_index]

            await message.answer(
                f"Вес ребенка {current_child['full_name']} сохранен: {weight} кг\n\n"
                f"Следующий ребенок без веса: {next_child['full_name']}\n\n"
                f"Пожалуйста, введите вес в кг (только цифры, например: 30):\n"
                f"Или нажмите кнопку для использования среднего веса.",
                reply_markup=await kb.create_child_weight_keyboard(next_child["id"])
            )
        else:
            # Все дети обработаны, переходим дальше
            await state.update_data({
                "children_without_weight": [],
                "current_child_weight_index": 0
            })

            # Переходим к промокоду
            await process_to_promo_code(message, state)

    except Exception as e:
        logger.error(
            f"Ошибка обработки веса ребенка для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await message.answer(
            "Произошла ошибка при сохранении веса. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

@router.callback_query(UserBookingStates.requesting_child_weight, F.data.startswith("skip_child_weight:"))
async def skip_child_weight(callback: CallbackQuery, state: FSMContext):
    """Пропуск ввода веса ребенка (использование среднего веса с сохранением в БД)"""
    user_telegram_id = callback.from_user.id

    try:
        # Парсим ID ребенка
        child_id = int(callback.data.split(":")[1])

        data = await state.get_data()
        children_without_weight = data.get("children_without_weight", [])
        current_index = data.get("current_child_weight_index", 0)

        if current_index >= len(children_without_weight):
            logger.error(f"Индекс {current_index} выходит за пределы списка детей без веса")
            await callback.answer("Ошибка: некорректный индекс ребенка", show_alert=True)
            return

        current_child = children_without_weight[current_index]

        if current_child["id"] != child_id:
            logger.warning(
                f"Несоответствие ID ребенка: ожидался {current_child['id']}, получен {child_id}"
            )

        # Получаем возраст ребенка из БД для точного расчета
        async with async_session() as session:
            db = DatabaseManager(session)
            child_user = await db.get_user_by_id(child_id)

            if not child_user:
                logger.error(f"Ребенок {child_id} не найден в БД")
                await callback.answer("Ошибка: ребенок не найден", show_alert=True)
                return

            # Используем проперти age из модели
            age = child_user.age

            # Рассчитываем средний вес в зависимости от возраста
            if age is None:
                # Если возраст неизвестен, используем средний вес 25 кг
                average_weight = 25
                weight_info = "средний вес 25 кг (возраст неизвестен)"
            elif age <= 3:
                average_weight = 15
                weight_info = f"средний вес 15 кг для возраста {age} лет"
            elif age <= 7:
                average_weight = 25
                weight_info = f"средний вес 25 кг для возраста {age} лет"
            elif age <= 12:
                average_weight = 40
                weight_info = f"средний вес 40 кг для возраста {age} лет"
            else:
                average_weight = 50
                weight_info = f"средний вес 50 кг для возраста {age} лет"

            # Сохраняем средний вес в БД
            await db.update_user_data(child_id, weight=average_weight)
            logger.info(
                f"Средний вес {average_weight}кг сохранен в БД для ребенка {child_id} (возраст: {age})"
            )

        # Сохраняем вес в state
        children_weights = data.get("children_weights", {})
        children_weights[child_id] = average_weight
        await state.update_data({
            "children_weights": children_weights
        })

        # Переходим к следующему ребенку без веса
        next_index = current_index + 1

        if next_index < len(children_without_weight):
            # Есть еще дети без веса
            await state.update_data({
                "current_child_weight_index": next_index
            })

            next_child = children_without_weight[next_index]

            await callback.message.answer(
                f"Для ребенка {current_child['full_name']} использован {weight_info}\n\n"
                f"Следующий ребенок без веса: {next_child['full_name']}\n\n"
                f"Пожалуйста, введите вес в кг (только цифры, например: 30):\n"
                f"Или нажмите кнопку для использования среднего веса.",
                reply_markup=await kb.create_child_weight_keyboard(next_child["id"])
            )
        else:
            # Все дети обработаны, переходим дальше
            await state.update_data({
                "children_without_weight": [],
                "current_child_weight_index": 0
            })

            # Переходим к промокоду
            await process_to_promo_code(callback.message, state)

    except ValueError as e:
        logger.error(f"Ошибка парсинга child_id для пользователя {user_telegram_id}: {e}")
        await callback.answer("Ошибка: некорректный идентификатор ребенка", show_alert=True)
    except Exception as e:
        logger.error(
            f"Ошибка пропуска веса ребенка для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=kb.main
        )
        await state.clear()

    await callback.answer()

@router.callback_query(UserBookingStates.requesting_child_weight, F.data == "cancel_booking")
async def cancel_booking_during_weight(callback: CallbackQuery, state: FSMContext):
    """Отмена бронирования во время ввода веса ребенка"""
    await cancel_booking(callback, state)
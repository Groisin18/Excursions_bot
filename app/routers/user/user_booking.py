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
                f"Стоимость:\n"
                f"• Взрослый: {excursion.base_price} руб.\n"
                f"• Детский: по возрастным категориям\n"
                f"  - до 3 лет: бесплатно\n"
                f"  - 4-7 лет: скидка 60%\n"
                f"  - 8-12 лет: скидка 40%\n"
                f"  - 13 лет и старше: полная стоимость\n"
            )

            excursion_info += (
                f"\nОграничения:\n"
                f"• Максимальное количество человек: {slot.max_people}\n"
                f"• Свободных мест: {slot.max_people - booked_places}\n"
                f"• Максимальный суммарный вес: {slot.max_weight} кг\n"
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

            await callback.message.answer(excursion_info)
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


@router.message(UserBookingStates.checking_weight)
async def check_adult_weight(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} на этапе проверки веса")

    try:
        data = await state.get_data()

        # Получаем данные из state
        slot_id = data.get("slot_id")
        user_id = data.get("user_id")
        adult_weight = data.get("adult_weight")  # может быть None
        available_weight = data.get("available_weight")
        max_weight = data.get("max_weight")

        if not all([slot_id, user_id, available_weight is not None]):
            logger.error(f"Недостаточно данных в state для пользователя {user_telegram_id}")
            await message.answer(
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
                await message.answer(
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

                await message.answer(
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

                await message.answer(
                    f"Отлично! Ваш вес подходит для этой экскурсии.\n\n"
                    f"Доступный вес после вашего бронирования: {new_available_weight} кг\n\n"
                    f"У вас зарегистрировано детей: {children_count}\n"
                    f"Вы хотите записаться на экскурсию:",
                    reply_markup=await kb.create_participants_keyboard(user_has_children)
                )
            else:
                await message.answer(
                    f"Отлично! Ваш вес подходит для этой экскурсии.\n\n"
                    f"Доступный вес после вашего бронирования: {new_available_weight} кг\n\n"
                    f"Вы хотите записаться на экскурсию:",
                    reply_markup=await kb.create_participants_keyboard(user_has_children)
                )

    except Exception as e:
        logger.error(
            f"Ошибка проверки веса для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await message.answer(
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
        from app.utils.validation import Validators
        try:
            weight = Validators.validate_weight(message.text)
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
from datetime import datetime, date, timedelta

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from app.user_panel.keyboards import main_menu
from app.captain_panel.keyboards_cap import (
    captain_main_menu,
    captain_slots_for_arrival_keyboard,
    slot_clients_arrival_keyboard,
    captain_slots_for_complete_keyboard
)
from app.database.repositories import UserRepository, SlotRepository, BookingRepository
from app.database.session import async_session
from app.database.models import (
    SlotStatus, BookingStatus, ClientStatus
)
from app.middlewares import CaptainMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)

router = Router(name="captain_main")
router.message.middleware(CaptainMiddleware())
router.callback_query.middleware(CaptainMiddleware())


# ===== ВХОД В КАПИТАН-ПАНЕЛЬ =====

@router.message(Command("captain"))
async def captain_start(message: Message):
    """Вход в капитан-панель"""
    logger.info(f"Капитан {message.from_user.id} ({message.from_user.username}) вошел в капитан-панель")

    try:
        await message.answer(
            "Панель капитана\n"
            "Выберите действие:",
            reply_markup=captain_main_menu()
        )
        logger.debug(f"Главное меню капитана показано пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при входе в капитан-панель для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Ошибка при загрузке панели капитана", reply_markup=main_menu())


@router.message(F.text == "Выход")
async def captain_exit(message: Message):
    """Выход из капитан-панели"""
    logger.info(f"Капитан {message.from_user.id} вышел из капитан-панели")

    try:
        await message.answer(
            "Вы вышли из панели капитана", reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Ошибка при выходе из капитан-панели: {e}", exc_info=True)


@router.message(F.text == "Назад", StateFilter(None))
async def back_handler(message: Message, state: FSMContext):
    """Обработка кнопки Назад - возврат в главное меню капитана"""
    logger.debug(f"Капитан {message.from_user.id} нажал 'Назад' без активного состояния")

    try:
        await state.clear()
        await message.answer(
            "Главное меню капитана:",
            reply_markup=captain_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка обработки кнопки 'Назад': {e}", exc_info=True)


# ===== ВОЗВРАТ В МЕНЮ ИЗ CALLBACK =====

@router.callback_query(F.data == 'captain_back_to_menu')
async def callback_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню капитана из колбэка"""
    logger.debug(f"Капитан {callback.from_user.id} вернулся в меню из колбэка")

    try:
        await state.clear()
        await callback.answer()
        await callback.message.answer(
            "Главное меню капитана:",
            reply_markup=captain_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка возврата в меню капитана: {e}", exc_info=True)
        await callback.answer()
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=captain_main_menu()
        )


# ===== МОЕ РАСПИСАНИЕ =====

@router.message(F.text == "Мое расписание")
async def my_schedule(message: Message):
    """Показать расписание капитана на неделю"""
    logger.info(f"Капитан {message.from_user.id} запросил расписание")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            user = await user_repo.get_by_telegram_id(message.from_user.id)
            if not user:
                await message.answer(
                    "Пользователь не найден",
                    reply_markup=captain_main_menu()
                )
                return

            today = date.today()
            end_date = today + timedelta(days=7)

            slots = await slot_repo.get_captain_slots_by_id(
                captain_id=user.id,
                start_date=datetime.combine(today, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.max.time())
            )

            if not slots:
                await message.answer(
                    "У вас нет назначенных экскурсий на ближайшую неделю.",
                    reply_markup=captain_main_menu()
                )
                return

            response_lines = ["Ваше расписание на ближайшую неделю:\n"]
            for slot in slots:
                excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
                date_str = slot.start_datetime.strftime("%d.%m.%Y")
                time_str = slot.start_datetime.strftime("%H:%M")
                end_time_str = slot.end_datetime.strftime("%H:%M")
                status_labels = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }
                status_str = status_labels.get(slot.status, str(slot.status))

                response_lines.append(
                    f"{date_str} | {time_str}-{end_time_str} | {excursion_name} | {status_str}"
                )

            await message.answer("\n".join(response_lines), reply_markup=captain_main_menu())

    except Exception as e:
        logger.error(f"Ошибка получения расписания капитана: {e}", exc_info=True)
        await message.answer(
            "Ошибка при получении расписания",
            reply_markup=captain_main_menu()
        )


# ===== МОЯ СТАТИСТИКА =====

@router.message(F.text == "Моя статистика")
async def my_statistics(message: Message):
    """Показать статистику капитана за текущий месяц"""
    logger.info(f"Капитан {message.from_user.id} запросил статистику")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            user = await user_repo.get_by_telegram_id(message.from_user.id)
            if not user:
                await message.answer(
                    "Пользователь не найден",
                    reply_markup=captain_main_menu()
                )
                return

            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            completed_slots = await slot_repo.get_captain_completed_slots_for_period(
                captain_id=user.id,
                start_date=month_start.date(),
                end_date=now.date()
            )

            total_excursions = len(completed_slots)
            total_clients = 0
            for slot in completed_slots:
                if slot.bookings:
                    total_clients += sum(
                        1 + len(b.booking_children)
                        for b in slot.bookings
                        if b.booking_status == BookingStatus.completed
                    )

            response = (
                f"Ваша статистика за {month_start.strftime('%B %Y')}:\n\n"
                f"Проведено экскурсий: {total_excursions}\n"
                f"Обслужено клиентов: {total_clients}\n"
            )

            await message.answer(response, reply_markup=captain_main_menu())

    except Exception as e:
        logger.error(f"Ошибка получения статистики капитана: {e}", exc_info=True)
        await message.answer(
            "Ошибка при получении статистики",
            reply_markup=captain_main_menu()
        )


# ===== ЗАВЕРШИТЬ ЭКСКУРСИЮ =====

@router.message(F.text == "Завершить экскурсию")
async def complete_excursion(message: Message):
    """Показать слоты, доступные для завершения"""
    logger.info(f"Капитан {message.from_user.id} открыл завершение экскурсии")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            user = await user_repo.get_by_telegram_id(message.from_user.id)
            if not user:
                await message.answer(
                    "Пользователь не найден",
                    reply_markup=captain_main_menu()
                )
                return

            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            slots = await slot_repo.get_captain_slots_by_id(
                captain_id=user.id,
                start_date=today_start,
                end_date=today_end
            )

            completable_slots = [
                s for s in slots
                if s.status in [SlotStatus.scheduled, SlotStatus.in_progress]
            ]

            if not completable_slots:
                await message.answer(
                    "Нет экскурсий, доступных для завершения.",
                    reply_markup=captain_main_menu()
                )
                return

            await message.answer(
                "Выберите экскурсию для завершения:",
                reply_markup=captain_slots_for_complete_keyboard(completable_slots)
            )

    except Exception as e:
        logger.error(f"Ошибка открытия завершения экскурсии: {e}", exc_info=True)
        await message.answer(
            "Ошибка",
            reply_markup=captain_main_menu()
        )


@router.callback_query(F.data.startswith("captain_complete_slot:"))
async def process_complete_slot(callback: CallbackQuery):
    """Завершить выбранный слот"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Капитан {callback.from_user.id} завершает слот {slot_id}")

    await callback.answer()

    try:
        async with async_session() as session:
            slot_repo = SlotRepository(session)
            user_repo = UserRepository(session)

            slot = await slot_repo.get_by_id(slot_id)
            if not slot:
                await callback.message.answer(
                    "Слот не найден",
                    reply_markup=captain_main_menu()
                )
                return

            user = await user_repo.get_by_telegram_id(callback.from_user.id)
            if not user or slot.captain_id != user.id:
                await callback.message.answer(
                    "Вы не назначены на эту экскурсию",
                    reply_markup=captain_main_menu()
                )
                return

            await slot_repo.update_status(slot_id, SlotStatus.completed)

            excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
            await callback.message.answer(
                f"Экскурсия '{excursion_name}' успешно завершена.",
                reply_markup=captain_main_menu()
            )

    except Exception as e:
        logger.error(f"Ошибка завершения слота: {e}", exc_info=True)
        await callback.message.answer(
            "Ошибка при завершении экскурсии",
            reply_markup=captain_main_menu()
        )


# ===== ОТМЕТИТЬ ПРИБЫТИЕ КЛИЕНТА =====

@router.message(F.text == "Отметить прибытие клиента")
async def mark_arrival_start(message: Message):
    """Показать слоты на сегодня для отметки прибытия"""
    logger.info(f"Капитан {message.from_user.id} открыл отметку прибытия")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            user = await user_repo.get_by_telegram_id(message.from_user.id)
            if not user:
                await message.answer(
                    "Пользователь не найден",
                    reply_markup=captain_main_menu()
                )
                return

            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            slots = await slot_repo.get_captain_slots_by_id(
                captain_id=user.id,
                start_date=today_start,
                end_date=today_end
            )

            if not slots:
                await message.answer(
                    "У вас нет назначенных экскурсий на сегодня.",
                    reply_markup=captain_main_menu()
                )
                return

            await message.answer(
                "Выберите экскурсию для отметки прибытия клиентов:",
                reply_markup=captain_slots_for_arrival_keyboard(slots)
            )

    except Exception as e:
        logger.error(f"Ошибка открытия отметки прибытия: {e}", exc_info=True)
        await message.answer(
            "Ошибка",
            reply_markup=captain_main_menu()
        )


@router.callback_query(F.data.startswith("captain_arrival_slot:"))
async def show_slot_clients_for_arrival(callback: CallbackQuery):
    """Показать список клиентов слота для отметки прибытия"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Капитан {callback.from_user.id} просматривает клиентов слота {slot_id}")

    await callback.answer()

    try:
        async with async_session() as session:
            slot_repo = SlotRepository(session)

            slot = await slot_repo.get_with_bookings(slot_id)
            if not slot:
                await callback.message.answer(
                    "Слот не найден",
                    reply_markup=captain_main_menu()
                )
                return

            if not slot.bookings:
                await callback.message.answer(
                    "На эту экскурсию нет записанных клиентов",
                    reply_markup=captain_main_menu()
                )
                return

            active_bookings = [
                b for b in slot.bookings
                if b.booking_status == BookingStatus.active
            ]

            if not active_bookings:
                await callback.message.answer(
                    "Нет активных бронирований на эту экскурсию",
                    reply_markup=captain_main_menu()
                )
                return

            excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
            time_str = slot.start_datetime.strftime("%H:%M")

            await callback.message.answer(
                f"Клиенты на экскурсию '{excursion_name}' ({time_str}):\n"
                "Нажмите на клиента для отметки прибытия.",
                reply_markup=slot_clients_arrival_keyboard(slot_id, active_bookings)
            )

    except Exception as e:
        logger.error(f"Ошибка показа клиентов слота: {e}", exc_info=True)
        await callback.message.answer(
            "Ошибка при получении списка клиентов",
            reply_markup=captain_main_menu()
        )


@router.callback_query(F.data.startswith("captain_mark_arrived:"))
async def process_mark_arrived(callback: CallbackQuery):
    """Отметить прибытие конкретного клиента"""
    parts = callback.data.split(":")
    booking_id = int(parts[1])
    slot_id = int(parts[2])
    logger.info(f"Капитан {callback.from_user.id} отмечает прибытие по брони {booking_id}")

    await callback.answer()

    try:
        async with async_session() as session:
            booking_repo = BookingRepository(session)
            slot_repo = SlotRepository(session)

            booking = await booking_repo.get_by_id(booking_id)
            if not booking:
                await callback.message.answer(
                    "Бронирование не найдено",
                    reply_markup=captain_main_menu()
                )
                return

            if booking.client_status == ClientStatus.arrived:
                await callback.message.answer(
                    "Прибытие уже отмечено",
                    reply_markup=captain_main_menu()
                )
                return

            await booking_repo.update_status(
                booking_id=booking_id,
                client_status=ClientStatus.arrived
            )

            client_name = booking.adult_user.full_name if booking.adult_user else "Клиент"
            logger.info(f"Прибытие клиента {client_name} отмечено капитаном {callback.from_user.id}")

            # Обновляем клавиатуру
            slot = await slot_repo.get_with_bookings(slot_id)
            if slot:
                active_bookings = [
                    b for b in slot.bookings
                    if b.booking_status == BookingStatus.active
                ]
                await callback.message.edit_reply_markup(
                    reply_markup=slot_clients_arrival_keyboard(slot_id, active_bookings)
                )

    except Exception as e:
        logger.error(f"Ошибка отметки прибытия: {e}", exc_info=True)
        await callback.message.answer(
            "Ошибка при отметке прибытия",
            reply_markup=captain_main_menu()
        )


@router.callback_query(F.data == "captain_back_to_slots")
async def back_to_slots_selection(callback: CallbackQuery):
    """Вернуться к выбору слота для отметки прибытия"""
    logger.debug(f"Капитан {callback.from_user.id} вернулся к выбору слота")

    await callback.answer()

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            user = await user_repo.get_by_telegram_id(callback.from_user.id)
            if not user:
                await callback.message.answer(
                    "Пользователь не найден",
                    reply_markup=captain_main_menu()
                )
                return

            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            slots = await slot_repo.get_captain_slots_by_id(
                captain_id=user.id,
                start_date=today_start,
                end_date=today_end
            )

            await callback.message.edit_text(
                "Выберите экскурсию для отметки прибытия клиентов:",
                reply_markup=captain_slots_for_arrival_keyboard(slots)
            )

    except Exception as e:
        logger.error(f"Ошибка возврата к выбору слота: {e}", exc_info=True)
        await callback.message.answer(
            "Ошибка",
            reply_markup=captain_main_menu()
        )

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta

from app.middlewares import AdminMiddleware
from app.database.session import async_session
from app.database.managers import UserManager
from app.database.repositories import UserRepository, SlotRepository
from app.database.models import UserRole, SlotStatus
from app.utils.logging_config import get_logger
from app.admin_panel.keyboards_adm import (
    find_client_for_captains,
    captains_submenu, captains_list_keyboard, captain_period_menu,
    back_to_captains_list_menu
)

logger = get_logger(__name__)

router = Router(name="admin_captains")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УПРАВЛЕНИЕ КАПИТАНАМИ =====

@router.message(F.text == "Список капитанов")
async def show_captains_list(message: Message):
    """Показать список капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил список капитанов")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            captains_data = await user_manager.get_captains_with_stats()

            if not captains_data:
                logger.debug("Капитаны не найдены")
                await message.answer("Капитаны не найдены", reply_markup=captains_submenu())
                return

            logger.info(f"Найдено капитанов: {len(captains_data)}")
            response = "Список капитанов:\n\n"
            for data in captains_data:
                captain = data['captain']
                stats = data['stats']

                response += (
                    f"Имя: {captain.full_name}\n"
                    f"Телефон: {captain.phone_number}\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список капитанов отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка капитанов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка капитанов", reply_markup=captains_submenu())


@router.message(F.text == "График работы")
async def captains_schedule(message: Message):
    """График работы капитанов - показать список капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил график работы капитанов")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            captains = await user_repo.get_users_by_role(UserRole.captain)

            if not captains:
                await message.answer(
                    "Нет зарегистрированных капитанов.",
                    reply_markup=captains_submenu()
                )
                return

            await message.answer(
                "Выберите капитана для просмотра графика работы:",
                reply_markup=captains_list_keyboard(captains)
            )

    except Exception as e:
        logger.error(f"Ошибка получения списка капитанов: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "back_to_captains_list")
async def back_to_captains_list(callback: CallbackQuery):
    """Вернуться к списку капитанов"""
    await callback.answer()

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            captains = await user_repo.get_users_by_role(UserRole.captain)

            if not captains:
                await callback.message.edit_text(
                    "Нет зарегистрированных капитанов.",
                    reply_markup=captains_submenu()
                )
                return

            await callback.message.edit_text(
                "Выберите капитана для просмотра графика работы:",
                reply_markup=captains_list_keyboard(captains)
            )

    except Exception as e:
        logger.error(f"Ошибка возврата к списку капитанов: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка.")


@router.callback_query(F.data == "back_to_captains_menu")
async def back_to_captains_menu(callback: CallbackQuery):
    """Вернуться в меню капитанов"""
    await callback.answer()
    await callback.message.edit_text(
        "Управление капитанами",
        reply_markup=captains_submenu()
    )


@router.callback_query(F.data.startswith("captain_schedule_menu:"))
async def captain_schedule_menu(callback: CallbackQuery):
    """Меню выбора периода для капитана"""
    captain_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            captain = await user_repo.get_by_id(captain_id)

            if not captain:
                await callback.message.edit_text("Капитан не найден.")
                return

            captain_name = captain.full_name or captain.username or f"ID {captain.id}"

            await callback.message.edit_text(
                f"График работы капитана: {captain_name}\n\nВыберите период:",
                reply_markup=captain_period_menu(captain_id, captain_name)
            )

    except Exception as e:
        logger.error(f"Ошибка отображения меню капитана: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка.")


@router.callback_query(F.data.startswith("captain_schedule:"))
async def show_captain_schedule(callback: CallbackQuery):
    """Показать расписание капитана за выбранный период"""
    parts = callback.data.split(":")
    captain_id = int(parts[1])
    period_type = parts[2]
    await callback.answer()

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            slot_repo = SlotRepository(session)

            captain = await user_repo.get_by_id(captain_id)
            if not captain:
                await callback.message.edit_text("Капитан не найден.")
                return

            captain_name = captain.full_name or captain.username or f"ID {captain.id}"
            now = datetime.now()

            if period_type == "last_month":
                # Прошлый месяц: с первого числа прошлого месяца по последнее число прошлого месяца
                first_day_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day_prev_month = first_day_current_month - timedelta(days=1)
                first_day_prev_month = last_day_prev_month.replace(day=1)

                start_date = first_day_prev_month
                end_date = last_day_prev_month.replace(hour=23, minute=59, second=59)

                slots = await slot_repo.get_captain_slots_by_id(
                    captain_id, start_date, end_date
                )

                title = f"Расписание за прошлый месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"

            elif period_type == "current_month":
                # Текущий месяц: с первого числа текущего месяца по сегодня
                first_day_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                start_date = first_day_current_month
                end_date = now

                slots = await slot_repo.get_captain_slots_by_id(
                    captain_id, start_date, end_date
                )

                title = f"Расписание за текущий месяц ({start_date.strftime('%d.%m.%Y')} - {now.strftime('%d.%m.%Y')})"

            else:  # all_assigned
                # Все назначенные экскурсии, которые еще не начались
                slots = await slot_repo.get_captain_upcoming_slots(captain_id)
                title = "Все назначенные экскурсии (предстоящие)"

            if not slots:
                await callback.message.edit_text(
                    f"{title}\n\nКапитан {captain_name}\n\nНет экскурсий за выбранный период.",
                    reply_markup=back_to_captains_list_menu()
                )
                return

            # Формируем текст
            text_lines = [f"{title}\n", f"Капитан: {captain_name}\n", "=" * 40]

            for slot in slots:
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"
                date_str = slot.start_datetime.strftime("%d.%m.%Y")
                time_str = slot.start_datetime.strftime("%H:%M")

                status_text = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }.get(slot.status, "Неизвестно")

                text_lines.append(
                    f"\n• {excursion_name}\n"
                    f"  Дата: {date_str}\n"
                    f"  Время начала: {time_str}\n"
                    f"  ID слота: {slot.id}\n"
                    f"  Статус: {status_text}"
                )

                # Добавляем информацию о количестве бронирований
                if slot.bookings:
                    active_bookings = [b for b in slot.bookings if b.booking_status.value == "active"]
                    if active_bookings:
                        total_people = sum(b.people_count for b in active_bookings)
                        text_lines.append(f"  Записано: {len(active_bookings)} броней, {total_people} чел.")

            # Ограничиваем длину сообщения (Telegram лимит ~4096 символов)
            full_text = "\n".join(text_lines)
            if len(full_text) > 4000:
                # Разбиваем на несколько сообщений
                chunks = []
                current_chunk = []
                current_length = 0

                for line in text_lines:
                    if current_length + len(line) + 1 > 3500:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1

                if current_chunk:
                    chunks.append("\n".join(current_chunk))

                await callback.message.edit_text(chunks[0], reply_markup=back_to_captains_list_menu())

                for chunk in chunks[1:]:
                    await callback.message.answer(chunk)
            else:
                await callback.message.edit_text(full_text, reply_markup=back_to_captains_list_menu())

    except Exception as e:
        logger.error(f"Ошибка получения расписания капитана: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка при загрузке расписания.")


@router.message(F.text == "Расчет зарплаты")
async def calculate_salaries(message: Message):
    """Расчет зарплат капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил расчет зарплат")

    try:
        await message.answer("Функция 'Расчет зарплаты капитанов' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Добавить капитана")
async def add_captain(message: Message):
    """Добавление нового капитана"""
    logger.info(f"Администратор {message.from_user.id} хочет добавить капитана")

    try:
        await message.answer("Для добавления нового капитана ему сначала нужно зарегистрироваться в качестве клиента.\n"
                             "Затем найдите его запись по фамилии-имени или номеру телефона.\n"
                             "Далее в клавиатуре нажмите пункт 'Изменить статус' и выберите роль капитана.\n",
                             reply_markup=find_client_for_captains())
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
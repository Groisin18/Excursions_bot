from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.admin_panel.states_adm import AdminStates
from app.admin_panel.keyboards_adm import (
    admin_main_menu, statistics_submenu, cancel_button,
    dashboard_quick_actions
)
from app.database.repositories import UserRepository, SlotRepository
from app.database.managers import StatisticsManager, UserManager
from app.database.models import UserRole
from app.database.session import async_session

from app.middlewares import AdminMiddleware

from app.routers.admin.bookings import show_active_bookings, show_unpaid_bookings
from app.routers.admin.clients import show_new_clients
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_statistic_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== СТАТИСТИКА =====

# TODO Делаем статистику. Надо обрабатывать еще не написанные кнопки


@router.message(Command("dashboard"))
async def dashboard_handler(message: Message):
    """Показать дашборд администратора"""
    logger.info(f"Администратор {message.from_user.id} запросил дашборд")

    try:
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        async with async_session() as session:
            stats_manager = StatisticsManager(session)

            # Статистика за сегодня
            today_stats = await stats_manager.get_daily_stats(today)

            # Статистика за вчера для сравнения
            yesterday_stats = await stats_manager.get_daily_stats(yesterday)

            # Активные экскурсии
            active_excursions = await stats_manager.get_active_excursions_count()

            # Срочные/важные данные
            urgent_bookings = await stats_manager.get_urgent_bookings_info()
            free_captains = await stats_manager.get_captains_without_slots()

        # Функция сравнения
        def compare(current, previous):
            if previous == 0:
                return "[новое]" if current > 0 else "[без изменений]"
            change = ((current - previous) / previous) * 100
            if change > 20:
                return f"[высокий рост +{change:.0f}%]"
            elif change > 0:
                return f"[рост +{change:.0f}%]"
            elif change < -20:
                return f"[сильное падение {change:.0f}%]"
            elif change < 0:
                return f"[падение {change:.0f}%]"
            else:
                return "[без изменений]"

        # Основные метрики
        dashboard_text = f"""
ДАШБОРД АДМИНИСТРАТОРА | {today.strftime('%d.%m.%Y')}

СЕГОДНЯ:
• Бронирования: {today_stats.get('total_bookings', 0)} {compare(today_stats.get('total_bookings', 0), yesterday_stats.get('total_bookings', 0))}
• Выручка: {today_stats.get('total_revenue', 0)} руб. {compare(today_stats.get('total_revenue', 0), yesterday_stats.get('total_revenue', 0))}
• Новые пользователи: {today_stats.get('new_users', 0)} {compare(today_stats.get('new_users', 0), yesterday_stats.get('new_users', 0))}
• Активные экскурсии: {active_excursions}
"""

        # Срочные задачи/внимание
        if urgent_bookings > 0 or free_captains > 0:
            dashboard_text += "\nТРЕБУЕТ ВНИМАНИЯ:\n"
            if urgent_bookings > 0:
                dashboard_text += f"• Неоплаченные брони на ближайшие дни: {urgent_bookings}\n"
            if free_captains > 0:
                dashboard_text += f"• Капитанов без слотов: {free_captains}\n"

        # Советы/рекомендации
        advice = []
        if today_stats.get('total_bookings', 0) < 3:
            advice.append("Мало бронирований сегодня")
        if urgent_bookings > 5:
            advice.append("Много неоплаченных бронирований. Напомните клиентам.")
        if free_captains > 3:
            advice.append("Много свободных капитанов. Есть возможность добавить новые слоты.")

        if advice:
            dashboard_text += "\Рекомендации:\n" + "\n".join(f"• {item}" for item in advice)

        await message.answer(dashboard_text, reply_markup=dashboard_quick_actions())
        logger.debug(f"Дашборд отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения дашборда: {e}", exc_info=True)
        await message.answer("Ошибка при получении данных дашборда", reply_markup=statistics_submenu())

@router.message(F.text == "Сегодня")
async def statistics_today(message: Message):
    """Статистика за сегодня с использованием StatisticsManager"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику за сегодня")

    try:
        today = datetime.now()

        async with async_session() as session:
            stats_manager = StatisticsManager(session)
            basic_stats = await stats_manager.get_daily_stats(today)
            excursions_stats = await stats_manager.get_daily_excursions_stats(today)
            captains_stats = await stats_manager.get_daily_captains_stats(today)

        response = f"СТАТИСТИКА ЗА СЕГОДНЯ ({today.strftime('%d.%m.%Y')})\n\n"
        response += f"Основные показатели:\n"
        response += f"• Новые бронирования: {basic_stats.get('total_bookings', 0)}\n"
        response += f"• Выручка: {basic_stats.get('total_revenue', 0)} руб.\n"
        response += f"• Новые пользователи: {basic_stats.get('new_users', 0)}\n\n"

        if excursions_stats:
            response += "По экскурсиям:\n"
            for exc in excursions_stats:
                response += f"- {exc.name}: {exc.total_bookings} записей, {exc.total_people} человек\n"

        if captains_stats:
            response += "\nПо капитанам:\n"
            for cap in captains_stats:
                response += f"- {cap.full_name}: {cap.total_bookings} рейсов\n"

        if not excursions_stats and not captains_stats:
            response += "Статистика за сегодня отсутствует"

        await message.answer(response, reply_markup=statistics_submenu())
        logger.debug(f"Статистика за сегодня отправлена администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения статистики за сегодня: {e}", exc_info=True)
        await message.answer("Ошибка при получении статистики", reply_markup=statistics_submenu())

@router.message(F.text == "Общая статистика")
async def general_statistics(message: Message):
    """Общая статистика"""
    logger.info(f"Администратор {message.from_user.id} запросил общую статистику")

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        async with async_session() as session:
            stats_manager = StatisticsManager(session)
            period_stats = await stats_manager.get_period_stats(start_date, end_date)

        response = (
            f"Общая статистика за 30 дней:\n\n"
            f"Всего бронирований: {period_stats.get('total_bookings', 0)}\n"
            f"Всего участников: {period_stats.get('total_people', 0)}\n"
            f"Общая выручка: {period_stats.get('total_revenue', 0)} руб.\n"
            f"Новых пользователей: {period_stats.get('new_users', 0)}\n"
            f"Проведено экскурсий: {period_stats.get('completed_excursions', 0)}\n"
            f"Средний чек: {period_stats.get('avg_check', 0)} руб.\n"
            f"Конверсия: {period_stats.get('conversion_rate', 0)}%\n"
            f"Самый популярный маршрут: {period_stats.get('popular_excursion', 'Нет данных')}"
        )

        await message.answer(response, reply_markup=statistics_submenu())

    except Exception as e:
        logger.error(f"Ошибка получения общей статистики: {e}", exc_info=True)
        await message.answer("Ошибка при получении статистики", reply_markup=statistics_submenu())

@router.message(F.text == "За период")
async def statistics_period_start(message: Message, state: FSMContext):
    """Начало выбора периода для статистики"""
    logger.info(f"Администратор {message.from_user.id} начал выбор периода для статистики")

    try:
        await message.answer(
            "Введите период в формате:\n"
            "дд.мм.гггг-дд.мм.гггг\n\n"
            "Например: 01.12.2024-07.12.2024",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminStates.waiting_for_statistics_period)
        logger.debug(f"Пользователь {message.from_user.id} перешел в состояние ожидания периода")
    except Exception as e:
        logger.error(f"Ошибка начала выбора периода: {e}", exc_info=True)
        await message.answer("Ошибка начала выбора периода", reply_markup=statistics_submenu())

@router.message(AdminStates.waiting_for_statistics_period)
async def statistics_period_process(message: Message, state: FSMContext):
    """Обработка введенного периода"""
    logger.info(f"Администратор {message.from_user.id} отправил период: {message.text}")

    try:
        date_range = message.text.split('-')
        start_datetime = datetime.strptime(date_range[0].strip(), "%d.%m.%Y")
        end_datetime = datetime.strptime(date_range[1].strip(), "%d.%m.%Y")

        # Устанавливаем время для полного дня
        end_datetime = end_datetime.replace(hour=23, minute=59, second=59)

        logger.debug(f"Парсинг периода: {start_datetime.date()} - {end_datetime.date()}")

        async with async_session() as session:
            stats_manager = StatisticsManager(session)
            logger.debug(f"Запрос статистики за период {start_datetime.date()} - {end_datetime.date()}")

            report = await stats_manager.generate_period_report(start_datetime, end_datetime)

            await message.answer(report, reply_markup=statistics_submenu())
            logger.debug(f"Статистика за период отправлена администратору {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Неверный формат периода от пользователя {message.from_user.id}: {message.text}")
        await message.answer("Ошибка формата. Используйте: дд.мм.гггг-дд.мм.гггг")
        return
    except Exception as e:
        logger.error(f"Ошибка обработки периода: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке периода")

    await state.clear()
    logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

@router.message(F.text == "Отмена", AdminStates.waiting_for_statistics_period)
async def cancel_statistics_period(message: Message, state: FSMContext):
    """Отмена выбора периода статистики"""
    logger.info(f"Администратор {message.from_user.id} отменил выбор периода")

    try:
        await state.clear()
        await message.answer(
            "Выбор периода отменен",
            reply_markup=statistics_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка отмены выбора периода: {e}", exc_info=True)
        await message.answer("Ошибка", reply_markup=admin_main_menu())

@router.callback_query(F.data == "refresh_dashboard")
async def refresh_dashboard_callback(callback: CallbackQuery):
    """Обновить дашборд"""
    await callback.answer()
    await dashboard_handler(callback.message)

@router.callback_query(F.data == "show_near_slots")
async def show_near_slots_callback(callback: CallbackQuery):
    """Показать ближайшие слоты"""
    await callback.answer()

    today = datetime.now()
    three_days_later = today + timedelta(days=3)

    try:
        async with async_session() as session:
            slot_repo = SlotRepository(session)
            slots = await slot_repo.get_for_period(today, three_days_later)

            if not slots:
                await callback.message.answer("На ближайшие 3 дней нет слотов")
                return

            response = "Ближайшие слоты (3 дня):\n\n"
            for slot in slots[:15]:  # Можно увеличить лимит
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестно"
                time_str = slot.start_datetime.strftime('%d.%m %H:%M')
                status = slot.status.value

                response += f"• {time_str} - {excursion_name} ({status})\n"
                if slot.captain:
                    response += f"  Капитан: {slot.captain.full_name}\n"

            if len(slots) > 15:
                response += f"\n... и еще {len(slots) - 15} слотов"

            await callback.message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка показа ближайших слотов: {e}")
        await callback.message.answer("Ошибка при получении слотов", reply_markup=statistics_submenu())

@router.callback_query(F.data == "show_free_captains")
async def show_free_captains_callback(callback: CallbackQuery):
    """Показать свободных капитанов"""
    await callback.answer()

    try:
        async with async_session() as session:
            stats_manager = StatisticsManager(session)
            user_repo = UserRepository(session)

            free_captains_count = await stats_manager.get_captains_without_slots()
            all_captains = await user_repo.get_users_by_role(UserRole.captain)
            response = f"Капитаны: {len(all_captains)} всего, {free_captains_count} свободны\n\n"

            for captain in all_captains[:10]:  # Показываем первых 10
                response += f"• {captain.full_name} ({captain.phone_number})\n"

            if len(all_captains) > 10:
                response += f"\n... и еще {len(all_captains) - 10} капитанов"

            await callback.message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка показа капитанов: {e}")
        await callback.message.answer("Ошибка при получении данных", reply_markup=statistics_submenu())

@router.callback_query(F.data == "show_unpaid_bookings")
async def show_unpaid_bookings_callback(callback: CallbackQuery):
    """Показать неоплаченные бронирования"""
    await callback.answer()
    await show_unpaid_bookings(callback.message)

@router.callback_query(F.data == "show_new_clients")
async def show_new_clients_callback(callback: CallbackQuery):
    """Показать новых клиентов"""
    await callback.answer()
    await show_new_clients(callback.message)

@router.callback_query(F.data == "show_active_bookings")
async def show_active_bookings_callback(callback: CallbackQuery):
    """Показать активные записи"""
    await callback.answer()
    await show_active_bookings(callback.message)





@router.message(F.text == "По экскурсиям")
async def statistics_by_excursions(message: Message):
    """Статистика по экскурсиям"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику по экскурсиям")

    try:
        await message.answer("Функция 'Статистика по экскурсиям' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "По капитанам")
async def statistics_by_captains(message: Message):
    """Статистика по капитанам"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику по капитанам")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)

            # Получаем статистику за текущий месяц
            captains_data = await user_manager.get_captains_with_stats()

            if not captains_data:
                logger.debug("Нет данных для статистики по капитанам")
                await message.answer(
                    "Нет данных о капитанах за текущий месяц",
                    reply_markup=statistics_submenu()
                )
                return

            # Получаем период
            period_info = "текущий месяц"
            if captains_data and captains_data[0]['stats'].get('period_start'):
                start = captains_data[0]['stats']['period_start']
                end = captains_data[0]['stats']['period_end']
                period_info = f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}"

            response = f"Статистика по капитанам за {period_info}:\n\n"

            for data in captains_data:
                captain = data['captain']
                stats = data['stats']

                response += (
                    f"{captain.full_name}:\n"
                    f"  Рейсов: {stats.get('total_bookings', 0)}\n"
                    f"  Людей: {stats.get('total_people', 0)}\n"
                    f"  Выручка: {stats.get('total_revenue', 0)} руб.\n"
                    f"  Зарплата: {stats.get('total_amount', 0)} руб.\n"
                    f"---\n"
                )

            await message.answer(response, reply_markup=statistics_submenu())
            logger.debug(f"Статистика по капитанам отправлена администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения статистики по капитанам: {e}", exc_info=True)
        await message.answer(
            "Ошибка при получении статистики",
            reply_markup=statistics_submenu()
        )

@router.message(F.text == "Отказы и неявки")
async def statistics_cancellations(message: Message):
    """Статистика отказов и неявок"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику отказов и неявок")

    try:
        await message.answer("Функция 'Отказы и неявки' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

@router.callback_query(F.data.startswith("excursion_stats:"))
async def excursion_stats_callback(callback: CallbackQuery):
    """Статистика экскурсии (inline)"""
    excursion_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} запросил статистику экскурсии {excursion_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Статистика экскурсии #{excursion_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
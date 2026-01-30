import asyncio

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, date, timedelta
from sqlalchemy import select, text, func
from app.admin_panel.states_adm import AdminStates
from app.admin_panel.keyboards_adm import (
    admin_main_menu, bookings_submenu, statistics_submenu, cancel_button
)
from app.admin_panel.services.statistics_service import StatisticsService
from app.database.requests import DatabaseManager
from app.database.models import (
    engine, async_session, User, Booking, ExcursionSlot, Excursion
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_statistic_router")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== СТАТИСТИКА =====

#Делаем статистику. Используем файл statistics_service, надо начинать обрабатывать еще не написанные кнопки


@router.message(Command("dashboard"))
async def dashboard_handler(message: Message):
    """Показать дашборд администратора"""
    logger.info(f"Администратор {message.from_user.id} запросил дашборд")

    try:
        stats_service = StatisticsService()

        # Статистика за сегодня
        today = datetime.now()
        today_stats = await stats_service.get_daily_stats(today)

        # Статистика за вчера для сравнения
        yesterday = today - timedelta(days=1)
        yesterday_stats = await stats_service.get_daily_stats(yesterday)

        # Сравнение
        def compare(current, previous):
            if previous == 0:
                return "+∞%" if current > 0 else "0%"
            change = ((current - previous) / previous) * 100
            prefix = "+" if change > 0 else ""
            return f"{prefix}{change:.1f}%"

        dashboard_text = f"""
ДАШБОРД АДМИНИСТРАТОРА | {today.strftime('%d.%m.%Y')}

СЕГОДНЯ:
• Бронирования: {today_stats['total_bookings']} ({compare(today_stats['total_bookings'], yesterday_stats['total_bookings'])})
• Выручка: {today_stats['total_revenue']} руб. ({compare(today_stats['total_revenue'], yesterday_stats['total_revenue'])})
• Новые пользователи: {today_stats['new_users']} ({compare(today_stats['new_users'], yesterday_stats['new_users'])})
• Активные экскурсии: {today_stats['active_excursions']}
        """

        await message.answer(dashboard_text)
        logger.debug(f"Дашборд отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения дашборда: {e}", exc_info=True)
        await message.answer("Ошибка при получении данных дашборда")


@router.message(F.text == "Сегодня")
async def statistics_today(message: Message):
    """Статистика за сегодня с использованием StatisticsService"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику за сегодня")

    try:
        stats_service = StatisticsService()
        today = datetime.now()
        stats = await stats_service.get_daily_stats(today)

        # Также получаем дополнительные данные из БД для деталей
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Детали по экскурсиям за сегодня
            excursions_query = await session.execute(
                select(
                    Excursion.name,
                    func.count(Booking.id).label('total_bookings'),
                    func.sum(Booking.people_count).label('total_people')
                ).select_from(Booking)
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .join(Excursion, ExcursionSlot.excursion_id == Excursion.id)
                .where(func.date(Booking.created_at) == today.date())
                .where(Booking.booking_status.in_(['active', 'confirmed', 'completed']))
                .group_by(Excursion.name)
            )
            excursions_stats = excursions_query.all()

            # Детали по капитанам за сегодня
            captains_query = await session.execute(
                select(
                    User.full_name,
                    func.count(Booking.id).label('total_bookings')
                ).select_from(Booking)
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .join(User, ExcursionSlot.captain_id == User.id)
                .where(func.date(Booking.created_at) == today.date())
                .where(Booking.booking_status.in_(['active', 'confirmed', 'completed']))
                .group_by(User.full_name)
            )
            captains_stats = captains_query.all()

        response = f"СТАТИСТИКА ЗА СЕГОДНЯ ({today.strftime('%d.%m.%Y')})\n\n"
        response += f"Основные показатели:\n"
        response += f"• Новые бронирования: {stats['total_bookings']}\n"
        response += f"• Выручка: {stats['total_revenue']} руб.\n"
        response += f"• Новые пользователи: {stats['new_users']}\n"
        response += f"• Активные экскурсии: {stats['active_excursions']}\n\n"

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
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Статистика за последние 30 дней
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            logger.debug(f"Сбор статистики за период {start_date} - {end_date}")
            stats = await db_manager.get_statistics(start_date, end_date)

            total_bookings = sum(exc['total_bookings'] for exc in stats['excursions'])
            total_people = sum(exc['total_people'] for exc in stats['excursions'])
            total_revenue = sum(exc['total_revenue'] for exc in stats['excursions'])

            response = (
                f"Общая статистика за 30 дней:\n\n"
                f"Всего записей: {total_bookings}\n"
                f"Всего человек: {total_people}\n"
                f"Общий доход: {total_revenue} руб.\n"
            )

            logger.debug(f"Общая статистика: {total_bookings} записей, {total_people} человек, {total_revenue} руб.")
            await message.answer(response, reply_markup=statistics_submenu())

    except Exception as e:
        logger.error(f"Ошибка получения общей статистики: {e}", exc_info=True)
        await message.answer("Ошибка при получении статистики", reply_markup=bookings_submenu())


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


@router.message(AdminStates.waiting_for_statistics_period)
async def statistics_period_process(message: Message, state: FSMContext):
    """Обработка введенного периода"""
    logger.info(f"Администратор {message.from_user.id} отправил период: {message.text}")

    try:
        date_range = message.text.split('-')
        start_date = datetime.strptime(date_range[0].strip(), "%d.%m.%Y").date()
        end_date = datetime.strptime(date_range[1].strip(), "%d.%m.%Y").date()

        logger.debug(f"Парсинг периода: {start_date} - {end_date}")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            logger.debug(f"Запрос статистики за период {start_date} - {end_date}")
            stats = await db_manager.get_statistics(start_date, end_date)

            response = f"Статистика за период {start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}:\n\n"

            if stats['excursions']:
                logger.debug(f"Найдено {len(stats['excursions'])} экскурсий за период")
                response += "Экскурсии:\n"
                for exc in stats['excursions']:
                    response += f"- {exc['name']}: {exc['total_bookings']} записей, {exc['total_people']} человек, {exc['total_revenue']} руб.\n"

            if not stats['excursions']:
                response = f"За период {start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')} статистики нет"

            await message.answer(response, reply_markup=statistics_submenu())
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
        await message.answer("Функция 'Статистика по капитанам' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Отказы и неявки")
async def statistics_cancellations(message: Message):
    """Статистика отказов и неявок"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику отказов и неявок")

    try:
        await message.answer("Функция 'Отказы и неявки' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(AdminStates.waiting_for_statistics_period)
async def statistics_period_process(message: Message, state: FSMContext):
    """Обработка введенного периода с использованием StatisticsService"""
    logger.info(f"Администратор {message.from_user.id} отправил период: {message.text}")

    try:
        # Проверяем специальные ключевые слова
        if message.text.lower() == "неделя":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        elif message.text.lower() == "месяц":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
        elif message.text.lower() == "квартал":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
        else:
            # Парсим период из формата дд.мм.гггг-дд.мм.гггг
            date_range = message.text.split('-')
            start_date = datetime.strptime(date_range[0].strip(), "%d.%m.%Y")
            end_date = datetime.strptime(date_range[1].strip(), "%d.%m.%Y")

        logger.debug(f"Парсинг периода: {start_date.date()} - {end_date.date()}")

        # Используем StatisticsService для генерации отчета
        stats_service = StatisticsService()
        report = await stats_service.generate_period_report(start_date, end_date)

        await message.answer(report, reply_markup=statistics_submenu())
        logger.debug(f"Отчет за период отправлен администратору {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Неверный формат периода от пользователя {message.from_user.id}: {message.text}")
        await message.answer("Ошибка формата. Используйте: дд.мм.гггг-дд.мм.гггг или ключевые слова: неделя, месяц, квартал")
        return
    except Exception as e:
        logger.error(f"Ошибка обработки периода: {e}", exc_info=True)
        await message.answer("Произошла ошибка при генерации отчета")

    await state.clear()
    logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")




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
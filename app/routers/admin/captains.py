from aiogram import F, Router
from aiogram.types import Message
from datetime import date
from sqlalchemy import select

from app.admin_panel.keyboards_adm import (
    admin_main_menu, captains_submenu
)
from app.database.requests import DatabaseManager
from app.database.models import (
    engine, async_session, UserRole, User
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_admin_logger

router = Router(name="admin_captains")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = get_admin_logger()


# ===== УПРАВЛЕНИЕ КАПИТАНАМИ =====

@router.message(F.text == "Список капитанов")
async def show_captains_list(message: Message):
    """Показать список капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил список капитанов")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            result = await session.execute(
                select(User)
                .where(User.role == UserRole.captain)
                .where(User.telegram_id.isnot(None))
            )
            captains = result.scalars().all()

            if not captains:
                logger.debug("Капитаны не найдены")
                await message.answer("Капитаны не найдены")
                return

            logger.info(f"Найдено капитанов: {len(captains)}")
            response = "Список капитанов:\n\n"
            for captain in captains:
                # Получаем статистику капитана
                captain_stats = await db_manager.calculate_captain_salary(
                    captain.id,
                    date.today().replace(day=1)  # С начала месяца
                )

                response += (
                    f"Имя: {captain.full_name}\n"
                    f"Телефон: {captain.phone_number}\n"
                    f"Рейсов: {captain_stats.get('total_bookings', 0)}\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список капитанов отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка капитанов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка капитанов")


@router.message(F.text == "График работы")
async def captains_schedule(message: Message):
    """График работы капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил график работы капитанов")

    try:
        await message.answer("Функция 'График работы капитанов' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


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
        await message.answer("Функция 'Добавить капитана' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
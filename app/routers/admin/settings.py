from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.database.requests import DatabaseManager
from app.database.models import (
    engine, async_session, UserRole, User
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_settings")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

# ===== НАСТРОЙКИ =====

@router.message(F.text == "Управление администраторами")
async def manage_admins(message: Message):
    """Управление администраторами"""
    logger.info(f"Администратор {message.from_user.id} открыл управление администраторами")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            result = await session.execute(
                select(User).where(User.role == UserRole.admin)
            )
            admins = result.scalars().all()

            logger.info(f"Найдено администраторов: {len(admins)}")
            response = "Текущие администраторы:\n\n"
            for admin in admins:
                response += (
                    f"Имя: {admin.full_name}\n"
                    f"Телефон: {admin.phone_number}\n"
                    f"Telegram ID: {admin.telegram_id}\n"
                    f"---\n"
                )

            response += "\nДля назначения нового администратора используйте команду /promote"
            await message.answer(response)
            logger.debug(f"Список администраторов отправлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка администраторов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка администраторов")


@router.message(F.text == "Настройки базы данных")
async def settings_database(message: Message):
    """Настройки базы данных"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки базы данных")

    try:
        # Можно использовать существующую команду /optimize_db
        await message.answer(
            "Настройки базы данных:\n\n"
            "Доступные команды:\n"
            "/optimize_db - оптимизация базы данных\n"
            "/reset_db - сброс сессий БД (принудительно)\n"
            "/debug - отладка состояния БД"
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
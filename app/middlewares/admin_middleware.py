from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from app.database.requests import DatabaseManager
from app.database.models import async_session, UserRole
from app.utils.logging_config import get_logger
from app.user_panel.keyboards import main as main_kb


logger = get_logger(__name__)


async def is_user_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    logger.debug(f"Проверка прав администратора для пользователя {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(telegram_id)

            # Явно проверяем все условия
            if user is None:
                logger.debug(f"Пользователь {telegram_id} не найден в базе")
                return False

            is_admin = user.role == UserRole.admin

            logger.debug(f"Пользователь {telegram_id}: {user.full_name}, роль: {user.role.value}, is_admin: {is_admin}")
            return is_admin

    except Exception as e:
        logger.error(f"Ошибка при проверке прав администратора для пользователя {telegram_id}: {e}", exc_info=True)
        return False

class AdminMiddleware(BaseMiddleware):
    """Мидлварь для проверки прав администратора"""
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        telegram_id = event.from_user.id

        # Ловим исключение из is_user_admin
        try:
            is_admin = await is_user_admin(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора для пользователя {telegram_id}: {e}", exc_info=True)
            is_admin = False

        if not is_admin:
            logger.warning(f"Попытка доступа к админ-панели без прав: {telegram_id}")

            # Используем импортированную клавиатуру
            if isinstance(event, Message):
                await event.answer(
                    "У вас нет прав доступа к админ-панели",
                    reply_markup=main_kb
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет прав доступа", show_alert=True)
            return None

        return await handler(event, data)
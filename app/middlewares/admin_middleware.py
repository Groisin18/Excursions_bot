from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from app.database.requests import DatabaseManager
from app.database.models import async_session, UserRole
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


async def is_user_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    logger.debug(f"Проверка прав администратора для пользователя {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(telegram_id)
            is_admin = user and user.role == UserRole.admin

            if user:
                logger.debug(f"Пользователь {telegram_id}: {user.full_name}, роль: {user.role.value}, is_admin: {is_admin}")
            else:
                logger.debug(f"Пользователь {telegram_id} не найден в базе, is_admin: {is_admin}")

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

        if not await is_user_admin(telegram_id):
            logger.warning(f"Попытка доступа к админ-панели без прав: {telegram_id}")

            # Импорты здесь чтобы избежать циклических импортов
            from app.user_panel.keyboards import main as main_kb
            if isinstance(event, Message):
                await event.answer(
                    "У вас нет прав доступа к админ-панели",
                    reply_markup=main_kb
                )
            else:
                await event.answer("У вас нет прав доступа", show_alert=True)
            return
        return await handler(event, data)
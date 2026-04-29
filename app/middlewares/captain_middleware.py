from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from app.database.repositories.user_repository import UserRepository
from app.database.models import UserRole
from app.database.session import async_session
from app.utils.logging_config import get_logger
from app.user_panel.keyboards import main_menu


logger = get_logger(__name__)


async def is_user_captain(telegram_id: int) -> bool:
    """Проверка, является ли пользователь капитаном (только чтение)"""
    logger.debug(f"Проверка прав капитана для пользователя {telegram_id}")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)

            if user is None:
                logger.debug(f"Пользователь {telegram_id} не найден в базе")
                return False

            is_captain = user.role == UserRole.captain
            logger.debug(f"Пользователь {telegram_id}: роль={user.role.value}, is_captain={is_captain}")
            return is_captain

    except Exception as e:
        logger.error(f"Ошибка при проверке прав капитана: {e}", exc_info=True)
        return False


class CaptainMiddleware(BaseMiddleware):
    """Мидлварь для проверки прав капитана"""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        telegram_id = event.from_user.id

        try:
            is_captain = await is_user_captain(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при проверке прав капитана для пользователя {telegram_id}: {e}", exc_info=True)
            is_captain = False

        if not is_captain:
            logger.warning(f"Попытка доступа к капитан-панели без прав: {telegram_id}")

            if isinstance(event, Message):
                await event.answer(
                    "У вас нет прав доступа к панели капитана",
                    reply_markup=main_menu()
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет прав доступа", show_alert=True)
            return None

        return await handler(event, data)
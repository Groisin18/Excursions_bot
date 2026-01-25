from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
import logging

from app.utils.auth import is_user_admin

logger = logging.getLogger(__name__)

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
            from app.keyboards import main as main_kb
            if isinstance(event, Message):
                await event.answer(
                    "У вас нет прав доступа к админ-панели",
                    reply_markup=main_kb
                )
            else:
                await event.answer("У вас нет прав доступа", show_alert=True)
            return
        return await handler(event, data)
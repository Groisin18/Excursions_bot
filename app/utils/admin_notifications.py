"""
Утилиты для отправки уведомлений администраторам
"""
from typing import List

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.user_repository import UserRepository
from app.database.models import UserRole
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def notify_admins(
    bot: Bot,
    session: AsyncSession,
    message: str,
    parse_mode: str = "HTML"
) -> List[int]:
    """
    Отправить сообщение всем администраторам.

    Args:
        bot: Экземпляр бота
        session: Сессия базы данных
        message: Текст сообщения
        parse_mode: Режим парсинга сообщения

    Returns:
        List[int]: Список ID администраторов, которым удалось отправить сообщение
    """
    user_repo = UserRepository(session)

    try:
        # Получаем всех администраторов
        admins = await user_repo.get_users_by_role(UserRole.admin)

        if not admins:
            logger.warning("Нет администраторов для уведомления")
            return []

        success_ids = []

        for admin in admins:
            if admin.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=admin.telegram_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                    success_ids.append(admin.telegram_id)
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение админу {admin.telegram_id}: {e}")

        logger.info(f"Уведомление отправлено {len(success_ids)} из {len(admins)} администраторов")
        return success_ids

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администраторам: {e}", exc_info=True)
        return []


async def notify_admins_about_refund_failure(
    bot: Bot,
    session: AsyncSession,
    refund_id: int,
    booking_id: int,
    error_message: str
) -> None:
    """
    Уведомить администраторов об ошибке возврата.

    Args:
        bot: Экземпляр бота
        session: Сессия базы данных
        refund_id: ID возврата в нашей системе
        booking_id: ID бронирования
        error_message: Сообщение об ошибке
    """
    message = (
        "Ошибка возврата средств\n\n"
        f"Бронирование: #{booking_id}\n"
        f"Возврат: #{refund_id}\n"
        f"Ошибка: {error_message}\n\n"
        "Требуется ручное вмешательство."
    )

    await notify_admins(bot, session, message)
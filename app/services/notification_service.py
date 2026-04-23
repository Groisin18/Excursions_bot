# app/services/notification_service.py

"""Сервис для массовых рассылок с rate limiting"""

import asyncio
import re
from typing import Optional

from aiogram import Bot

from app.database.unit_of_work import UnitOfWork
from app.database.session import async_session
from app.database.repositories.notification_repository import NotificationRepository
from app.database.models import NotificationStatus, UserRole
from app.utils.logging_config import get_logger
from app.utils.admin_notifications import notify_admins

logger = get_logger(__name__)


class NotificationService:
    """Сервис для управления массовыми рассылками"""

    MAX_MESSAGES_PER_SECOND = 25
    RETRY_AFTER_DEFAULT = 60

    def __init__(self, bot: Bot):
        self.bot = bot
        self._semaphore = asyncio.Semaphore(self.MAX_MESSAGES_PER_SECOND)

    async def send_mass_notification(
        self,
        notification_id: int,
        audience_type: UserRole
    ) -> None:
        """Отправить массовую рассылку"""

        recipients = []
        notification = None
        total = 0

        # Чтение данных
        async with async_session() as session:
            repo = NotificationRepository(session)

            notification = await repo.get_notification_by_id(notification_id)
            if not notification:
                logger.error(f"Рассылка {notification_id} не найдена")
                return

            if notification.status != NotificationStatus.PENDING:
                logger.warning(f"Рассылка {notification_id} уже в статусе {notification.status.value}")
                return

            recipients = await repo.get_recipients_by_audience(audience_type)
            total = len(recipients)

            logger.info(f"Начинаем рассылку #{notification_id} для {total} получателей")

        # Обновление статуса (прямая сессия, без UoW)
        async with async_session() as session:
            repo = NotificationRepository(session)
            await repo.update_notification_status(notification_id, NotificationStatus.IN_PROGRESS)
            await repo.update_notification_stats(notification_id, 0, 0, total)
            await session.commit()

        # Отправка сообщений
        sent_count = 0
        failed_count = 0

        for i, recipient in enumerate(recipients):
            if not recipient.telegram_id:
                failed_count += 1
                logger.warning(f"Пользователь {recipient.id} не имеет telegram_id")
                continue

            try:
                await self._send_with_rate_limit(
                    chat_id=recipient.telegram_id,
                    text=notification.message
                )
                sent_count += 1

                if (i + 1) % 100 == 0:
                    logger.info(f"Рассылка #{notification_id}: отправлено {sent_count}/{total}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка отправки пользователю {recipient.telegram_id}: {e}")

            # Периодическое обновление статистики
            if (i + 1) % 50 == 0:
                async with async_session() as session:
                    repo = NotificationRepository(session)
                    await repo.update_notification_stats(notification_id, sent_count, failed_count)
                    await session.commit()

        # Финальное обновление статистики
        async with async_session() as session:
            repo = NotificationRepository(session)
            await repo.update_notification_stats(notification_id, sent_count, failed_count)

            status = NotificationStatus.COMPLETED if failed_count == 0 else NotificationStatus.FAILED
            await repo.update_notification_status(notification_id, status)
            await session.commit()

        logger.info(f"Рассылка #{notification_id} завершена. Отправлено: {sent_count}, ошибок: {failed_count}")

        # Уведомление администраторов
        async with async_session() as session:
            status_text = "завершена" if failed_count == 0 else "завершена с ошибками"
            message = (
                f"Массовая рассылка #{notification.id} {status_text}\n\n"
                f"Аудитория: {notification.audience_type.value}\n"
                f"Отправлено: {sent_count}\n"
                f"Ошибок: {failed_count}\n"
                f"Всего: {total}\n\n"
                f"Текст сообщения:\n{notification.short_message}"
            )
            await notify_admins(self.bot, session, message)

    async def _send_with_rate_limit(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML"
    ) -> None:
        """Отправить сообщение с rate limiting"""
        async with self._semaphore:
            while True:
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode
                    )
                    await asyncio.sleep(0.04)  # 25 сообщений/сек
                    break
                except Exception as e:
                    if "429" in str(e):
                        match = re.search(r'retry_after[=:]?\s*(\d+)', str(e), re.IGNORECASE)
                        retry_after = int(match.group(1)) if match else self.RETRY_AFTER_DEFAULT
                        logger.warning(f"Ошибка 429. Пауза {retry_after} сек")
                        await asyncio.sleep(retry_after)
                        continue
                    raise

    async def cancel_notification(self, notification_id: int) -> bool:
        """Отменить рассылку"""
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                repo = NotificationRepository(uow.session)

                notification = await repo.get_notification_by_id(notification_id)
                if not notification:
                    logger.error(f"Рассылка {notification_id} не найдена")
                    return False

                if notification.status != NotificationStatus.PENDING:
                    logger.warning(f"Нельзя отменить рассылку в статусе {notification.status.value}")
                    return False

                success = await repo.cancel_notification(notification_id)
                await uow.commit()
                return success


# Глобальный экземпляр
notification_service: Optional[NotificationService] = None


def get_notification_service() -> Optional[NotificationService]:
    return notification_service


def init_notification_service(bot: Bot):
    global notification_service
    notification_service = NotificationService(bot)
    logger.info("NotificationService инициализирован")
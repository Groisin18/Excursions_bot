"""Репозиторий для работы с уведомлениями (CRUD операции)"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from app.database.models import Notification, NotificationType


class NotificationRepository(BaseRepository):
    """Репозиторий для CRUD операций с уведомлениями"""

    def __init__(self, session):
        super().__init__(session)

    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        message: str
    ) -> Notification:
        """Создать уведомление"""
        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                message=message
            )

            return await self._create(notification)

        except Exception as e:
            self.logger.error(f"Ошибка создания уведомления: {e}", exc_info=True)
            raise

    async def get_undelivered_notifications(self) -> List[Notification]:
        """Получить недоставленные уведомления"""
        try:
            query = (
                select(Notification)
                .options(selectinload(Notification.user))
                .where(Notification.is_delivered == False)
            )

            result = await self._execute_query(query)
            return list(result.scalars().all())

        except Exception as e:
            self.logger.error(f"Ошибка получения недоставленных уведомлений: {e}", exc_info=True)
            return []

    async def mark_notification_delivered(self, notification_id: int) -> bool:
        """Пометить уведомление как доставленное"""
        return await self._update(
            Notification,
            Notification.id == notification_id,
            is_delivered=True
        ) > 0

    async def get_notification_by_id(self, notification_id: int) -> Optional[Notification]:
        """Получить уведомление по ID"""
        return await self._get_one(Notification, Notification.id == notification_id)

    async def get_user_notifications(
        self,
        user_id: int,
        limit: int = 50,
        only_undelivered: bool = False
    ) -> List[Notification]:
        """Получить уведомления пользователя"""
        try:
            conditions = [Notification.user_id == user_id]
            if only_undelivered:
                conditions.append(Notification.is_delivered == False)

            return await self._get_many(
                Notification,
                *conditions,
                order_by=Notification.created_at.desc(),
                limit=limit
            )

        except Exception as e:
            self.logger.error(f"Ошибка получения уведомлений пользователя {user_id}: {e}")
            return []
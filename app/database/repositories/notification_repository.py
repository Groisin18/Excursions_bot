"""Репозиторий для работы с массовыми рассылками"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select

from .base import BaseRepository
from app.database.models import Notification, NotificationStatus, User, UserRole


class NotificationRepository(BaseRepository):
    """Репозиторий для CRUD операций с массовыми рассылками"""

    def __init__(self, session):
        super().__init__(session)

    async def create_notification(
        self,
        message: str,
        audience_type: UserRole,
        created_by_id: int
    ) -> Notification:
        """Создать массовую рассылку"""
        try:
            return await self._create(
                Notification,
                message=message,
                audience_type=audience_type,
                created_by_id=created_by_id,
                status=NotificationStatus.PENDING,
                sent_count=0,
                failed_count=0,
                total_recipients=0
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания рассылки: {e}", exc_info=True)
            raise

    async def update_notification_stats(
        self,
        notification_id: int,
        sent_count: int,
        failed_count: int,
        total_recipients: Optional[int] = None
    ) -> bool:
        """Обновить статистику рассылки"""
        try:
            update_data = {
                'sent_count': sent_count,
                'failed_count': failed_count
            }

            if total_recipients is not None:
                update_data['total_recipients'] = total_recipients

            return await self._update(
                Notification,
                Notification.id == notification_id,
                **update_data
            ) > 0

        except Exception as e:
            self.logger.error(f"Ошибка обновления статистики рассылки {notification_id}: {e}", exc_info=True)
            return False

    async def update_notification_status(
        self,
        notification_id: int,
        status: NotificationStatus
    ) -> bool:
        """Обновить статус рассылки"""
        try:
            update_data = {'status': status}

            if status == NotificationStatus.COMPLETED:
                update_data['completed_at'] = datetime.now()

            return await self._update(
                Notification,
                Notification.id == notification_id,
                **update_data
            ) > 0

        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса рассылки {notification_id}: {e}", exc_info=True)
            return False

    async def get_notification_by_id(self, notification_id: int) -> Optional[Notification]:
        """Получить рассылку по ID"""
        return await self._get_one(Notification, Notification.id == notification_id)

    async def get_notifications(
        self,
        limit: int = 50,
        status: Optional[NotificationStatus] = None,
        audience_type: Optional[UserRole] = None
    ) -> List[Notification]:
        """Получить список рассылок с фильтрацией"""
        try:
            conditions = []
            if status:
                conditions.append(Notification.status == status)
            if audience_type:
                conditions.append(Notification.audience_type == audience_type)

            return await self._get_many(
                Notification,
                *conditions,
                order_by=Notification.created_at.desc(),
                limit=limit
            )

        except Exception as e:
            self.logger.error(f"Ошибка получения рассылок: {e}")
            return []

    async def get_pending_notifications(self) -> List[Notification]:
            """Получить рассылки со статусом PENDING"""
            return await self.get_notifications(status=NotificationStatus.PENDING)

    async def get_recipients_by_audience(self, audience_type: UserRole) -> List[User]:
        """Получить список получателей по типу аудитории (только подписанных)"""
        try:
            # Только client и captain могут быть получателями
            if audience_type not in [UserRole.client, UserRole.captain]:
                self.logger.warning(f"Некорректный тип аудитории для рассылки: {audience_type.value}")
                return []

            query = (
                select(User)
                .where(
                    User.role == audience_type,
                    User.telegram_id.isnot(None),
                    User.is_virtual == False,
                    User.receive_mass_notifications == True  # Только подписанные
                )
            )

            result = await self._execute_query(query)
            users = list(result.scalars().all())

            self.logger.info(f"Найдено {len(users)} получателей для аудитории {audience_type.value} (с учетом подписки)")
            return users

        except Exception as e:
            self.logger.error(f"Ошибка получения получателей для аудитории {audience_type.value}: {e}")
            return []

    async def cancel_notification(self, notification_id: int) -> bool:
        """Отменить рассылку (только если она в статусе PENDING)"""
        notification = await self.get_notification_by_id(notification_id)
        if notification and notification.status == NotificationStatus.PENDING:
            return await self.update_notification_status(notification_id, NotificationStatus.CANCELLED)
        return False
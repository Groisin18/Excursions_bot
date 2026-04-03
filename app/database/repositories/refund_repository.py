"""
Репозиторий для работы с возвратами
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.base import BaseRepository
from app.database.models import Refund, RefundStatus

from app.utils.logging_config import get_logger
logger = get_logger(__name__)


class RefundRepository(BaseRepository):
    """Репозиторий для работы с возвратами"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create_refund(
        self,
        payment_id: int,
        booking_id: int,
        amount: int,
        reason: str = None,
        status: RefundStatus = RefundStatus.PENDING
    ) -> Refund:
        """
        Создать запись о возврате.

        Args:
            amount: Сумма в РУБЛЯХ (для хранения в БД)
        """
        refund = Refund(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=amount,  # amount в рублях
            reason=reason,
            status=status
        )
        self.session.add(refund)
        await self.session.flush()
        self.logger.info(f"Создана запись о возврате #{refund.id} для платежа {payment_id}, сумма={amount} руб.")
        return refund

    async def get_refund_by_id(self, refund_id: int) -> Optional[Refund]:
        """Получить возврат по ID"""
        result = await self.session.execute(
            select(Refund).where(Refund.id == refund_id)
        )
        return result.scalar_one_or_none()

    async def get_refund_by_yookassa_id(self, yookassa_refund_id: str) -> Optional[Refund]:
        """Получить возврат по ID из YooKassa"""
        result = await self.session.execute(
            select(Refund).where(Refund.yookassa_refund_id == yookassa_refund_id)
        )
        return result.scalar_one_or_none()

    async def get_refunds_by_booking(self, booking_id: int) -> List[Refund]:
        """Получить все возвраты по бронированию"""
        result = await self.session.execute(
            select(Refund)
            .where(Refund.booking_id == booking_id)
            .order_by(Refund.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_refunds_by_payment(self, payment_id: int) -> List[Refund]:
        """Получить все возвраты по платежу"""
        result = await self.session.execute(
            select(Refund)
            .where(Refund.payment_id == payment_id)
            .order_by(Refund.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_refunds_by_statuses(self, statuses: list, limit: int = 20) -> List[Refund]:
        """Получить возвраты по списку статусов"""
        result = await self.session.execute(
            select(Refund)
            .where(Refund.status.in_(statuses))
            .order_by(Refund.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_pending_refunds(self) -> List[Refund]:
        """Получить возвраты в статусе PENDING (ожидают создания в YooKassa)"""
        result = await self.session.execute(
            select(Refund).where(Refund.status == RefundStatus.PENDING)
        )
        return list(result.scalars().all())

    async def get_processing_refunds(self) -> List[Refund]:
        """Получить возвраты в статусе PROCESSING (ожидают завершения)"""
        result = await self.session.execute(
            select(Refund).where(Refund.status == RefundStatus.PROCESSING)
        )
        return list(result.scalars().all())

    async def get_failed_refunds(self, limit: int = None) -> List[Refund]:
        """
        Получить все неудачные возвраты (статус FAILED).

        Args:
            limit: Максимальное количество записей (опционально)

        Returns:
            List[Refund]: Список неудачных возвратов
        """
        query = select(Refund).where(Refund.status == RefundStatus.FAILED).order_by(Refund.created_at.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_refund_status(
        self,
        refund_id: int,
        status: RefundStatus,
        yookassa_refund_id: str = None,
        completed_at: datetime = None,
        cancellation_party: str = None,
        cancellation_reason: str = None
    ) -> bool:
        """Обновить статус возврата"""
        update_data = {'status': status}

        if yookassa_refund_id is not None:
            update_data['yookassa_refund_id'] = yookassa_refund_id

        if completed_at is not None:
            update_data['completed_at'] = completed_at
        elif status in (RefundStatus.SUCCEEDED, RefundStatus.FAILED, RefundStatus.CANCELED):
            update_data['completed_at'] = datetime.now()

        if cancellation_party is not None:
            update_data['cancellation_details_party'] = cancellation_party

        if cancellation_reason is not None:
            update_data['cancellation_details_reason'] = cancellation_reason

        result = await self.session.execute(
            update(Refund)
            .where(Refund.id == refund_id)
            .values(**update_data)
        )

        if result.rowcount > 0:
            self.logger.info(f"Обновлен статус возврата #{refund_id}: {status.value}")
            return True

        self.logger.warning(f"Возврат #{refund_id} не найден для обновления статуса")
        return False

    async def increment_retry_count(self, refund_id: int) -> int:
        """Увеличить счетчик попыток"""
        refund = await self.get_refund_by_id(refund_id)
        if refund:
            refund.retry_count += 1
            await self.session.flush()
            self.logger.info(f"Счетчик попыток возврата #{refund_id} увеличен до {refund.retry_count}")
            return refund.retry_count
        return 0

    async def get_refunds_for_retry(self, max_retries: int = 1) -> List[Refund]:
        """Получить возвраты, которые нужно повторить (неудачные, но не превысившие лимит)"""
        result = await self.session.execute(
            select(Refund)
            .where(Refund.status == RefundStatus.FAILED)
            .where(Refund.retry_count < max_retries)
        )
        return list(result.scalars().all())
"""Репозиторий для работы с платежами (CRUD операции)"""

from typing import Optional, List
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from datetime import datetime

from .base import BaseRepository
from app.database.models import (
    Payment, PaymentMethod, YooKassaStatus, PaymentStatus, Booking
)
from app.database.repositories.booking_repository import BookingRepository


class PaymentRepository(BaseRepository):
    """Репозиторий для CRUD операций с платежами"""

    def __init__(self, session):
        super().__init__(session)

    async def create_payment(
        self,
        booking_id: int,
        amount: int,
        payment_method: PaymentMethod,
        yookassa_payment_id: str = None
    ) -> Payment:
        """Создать запись о платеже"""
        try:
            payment = Payment(
                booking_id=booking_id,
                amount=amount,
                payment_method=payment_method,
                yookassa_payment_id=yookassa_payment_id,
                status=YooKassaStatus.pending if payment_method == PaymentMethod.online else None
            )

            return await self._create(payment)

        except Exception as e:
            self.logger.error(f"Ошибка создания платежа: {e}", exc_info=True)
            raise

    async def update_payment_status(
        self,
        yookassa_payment_id: str,
        status: YooKassaStatus,
        booking_repo: BookingRepository = None  # опционально
    ) -> bool:
        """Обновить статус онлайн платежа"""
        try:
            # Обновляем статус платежа
            updated_count = await self._update(
                Payment,
                Payment.yookassa_payment_id == yookassa_payment_id,
                status=status
            )

            if updated_count > 0 and status == YooKassaStatus.succeeded:
                payment = await self.get_payment_by_yookassa_id(yookassa_payment_id)

                if payment and booking_repo:
                    # Обновляем статус бронирования
                    await booking_repo.update_payment_status(
                        payment.booking_id,
                        PaymentStatus.paid
                    )

            return updated_count > 0

        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса платежа {yookassa_payment_id}: {e}", exc_info=True)
            return False

    async def get_payment_by_yookassa_id(self, yookassa_payment_id: str) -> Optional[Payment]:
        """Получить платеж по ID YooKassa"""
        return await self._get_one(Payment, Payment.yookassa_payment_id == yookassa_payment_id)

    async def get_payments_by_booking(self, booking_id: int) -> List[Payment]:
        """Получить все платежи по бронированию"""
        return await self._get_many(
            Payment,
            Payment.booking_id == booking_id,
            order_by=Payment.created_at.desc()
        )

    async def get_payment_by_id(self, payment_id: int) -> Optional[Payment]:
        """Получить платеж по ID"""
        return await self._get_one(Payment, Payment.id == payment_id)

    async def get_today_online_payments(self):
        """Получить сегодняшние онлайн-платежи"""

        today = datetime.now().date()

        result = await self.session.execute(
            select(Payment)
            .options(selectinload(Payment.booking).selectinload(Booking.client))
            .where(Payment.payment_method == PaymentMethod.online)
            .where(Payment.created_at >= today)
            .order_by(Payment.created_at.desc())
        )
        return result.scalars().all()
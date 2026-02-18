"""Репозиторий для работы с бронированиями (CRUD операции)"""

from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.database.models import (
    Booking, User, ExcursionSlot,
    BookingStatus, ClientStatus, PaymentStatus
)


class BookingRepository(BaseRepository):
    """Репозиторий для CRUD операций с бронированиями"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_id(self, booking_id: int) -> Optional[Booking]:
        """Получить бронирование по ID с полной загрузкой"""
        query = (
            select(Booking)
            .options(
                selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                selectinload(Booking.slot).selectinload(ExcursionSlot.captain),
                selectinload(Booking.adult_user),
                selectinload(Booking.payments),
                selectinload(Booking.booking_children)
            )
            .where(Booking.id == booking_id)
        )

        result = await self._execute_query(query)
        return result.scalar_one_or_none()

    async def get_user_bookings(self, user_telegram_id: int) -> List[Booking]:
        """Получить бронирования пользователя"""
        query = (
            select(Booking)
            .options(
                selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                selectinload(Booking.slot).selectinload(ExcursionSlot.captain),
                selectinload(Booking.booking_children)
            )
            .join(User, Booking.adult_user_id == User.id)
            .where(User.telegram_id == user_telegram_id)
            .order_by(Booking.created_at.desc())
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_user_active_for_slot(self, user_id: int, slot_id: int) -> Optional[Booking]:
        """Получить активную бронь пользователя на конкретный слот"""
        query = (
            select(Booking)
            .where(
                and_(
                    Booking.adult_user_id == user_id,
                    Booking.slot_id == slot_id,
                    Booking.booking_status == BookingStatus.active
                )
            )
            .limit(1)
        )

        result = await self._execute_query(query)
        return result.scalar_one_or_none()

    async def get_upcoming_bookings_for_reminder(self, hours_before: int = 24) -> List[Booking]:
        """Получить бронирования для отправки напоминаний"""
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import select, and_
            from sqlalchemy.orm import selectinload
            from app.database.models import BookingStatus, PaymentStatus, ExcursionSlot

            reminder_time = datetime.now() + timedelta(hours=hours_before)

            query = (
                select(Booking)
                .options(
                    selectinload(Booking.adult_user),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion)
                )
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .where(
                    and_(
                        ExcursionSlot.start_datetime >= datetime.now(),
                        ExcursionSlot.start_datetime <= reminder_time,
                        Booking.booking_status == BookingStatus.active,
                        Booking.payment_status == PaymentStatus.paid
                    )
                )
            )

            result = await self._execute_query(query)
            return list(result.scalars().all())

        except Exception as e:
            self.logger.error(f"Ошибка поиска бронирований для напоминаний: {e}", exc_info=True)
            return []

    async def get_booked_people_count(self, slot_id: int) -> int:
        """Получить количество забронированных людей в слоте"""
        try:
            # Получаем все активные брони на слот
            query = (
                select(Booking)
                .options(
                    selectinload(Booking.booking_children)
                )
                .where(
                    and_(
                        Booking.slot_id == slot_id,
                        Booking.booking_status == BookingStatus.active
                    )
                )
            )

            result = await self._execute_query(query)
            bookings = result.scalars().all()

            total_people = sum(booking.people_count for booking in bookings)
            return total_people

        except Exception as e:
            self.logger.error(f"Ошибка получения количества забронированных людей: {e}")
            return 0

    async def create(
        self,
        slot_id: int,
        adult_user_id: int,
        total_price: int,
        admin_creator_id: int = None,
        promo_code_id: int = None
    ) -> Booking:
        """Создать бронирование"""
        booking_data = {
            'slot_id': slot_id,
            'adult_user_id': adult_user_id,
            'admin_creator_id': admin_creator_id,
            'total_price': total_price,
            'promo_code_id': promo_code_id
        }

        return await self._create(Booking, **booking_data)

    async def create_with_token(
        self,
        user_id: int,
        slot_id: int,
        token: str,
        booked_by_id: int = None
    ) -> Optional[Booking]:
        """Создать бронирование с токеном (CRUD операция)"""
        try:
            booking = Booking(
                adult_user_id=user_id,
                slot_id=slot_id,
                booking_token=token,
                booked_by_id=booked_by_id,
                booking_status=BookingStatus.active,
                payment_status=PaymentStatus.pending
            )

            return await self._create(booking)
        except Exception as e:
            self.logger.error(f"Ошибка создания бронирования с токеном: {e}", exc_info=True)
            return None

    async def update_status(
        self,
        booking_id: int,
        client_status: ClientStatus = None,
        payment_status: PaymentStatus = None
    ) -> bool:
        """Обновить статусы бронирования"""
        update_data = {}
        if client_status:
            update_data['client_status'] = client_status
        if payment_status:
            update_data['payment_status'] = payment_status

        if not update_data:
            return False

        updated = await self._update(Booking, Booking.id == booking_id, **update_data)
        return updated > 0

    async def cancel(self, booking_id: int) -> bool:
        """Отменить бронирование"""
        return await self.update_status(booking_id, booking_status=BookingStatus.cancelled)

    async def update(self, booking_id: int, **data) -> bool:
        """Обновить данные бронирования"""
        clean_data = {k: v for k, v in data.items() if v is not None}
        if not clean_data:
            return False

        updated = await self._update(Booking, Booking.id == booking_id, **clean_data)
        return updated > 0

    async def update_payment_status(self, booking_id: int, payment_status: PaymentStatus) -> bool:
        """Обновить статус оплаты бронирования"""
        return await self._update(
            Booking,
            Booking.id == booking_id,
            payment_status=payment_status
        ) > 0
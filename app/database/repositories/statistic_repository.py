"""Репозиторий для статистических SQL-запросов"""

from datetime import date, datetime
from typing import Tuple
from sqlalchemy import select, func, and_

from .base import BaseRepository
from app.database.models import (
    Booking, Payment, YooKassaStatus,
    User, Excursion, ExcursionSlot, SlotStatus
)


class StatisticsRepository(BaseRepository):
    """Репозиторий для статистических SQL-запросов"""

    def __init__(self, session):
        super().__init__(session)

    async def get_daily_bookings_count(self, date_val: date) -> int:
        """Количество бронирований за день"""
        try:
            query = select(func.count(Booking.id)).where(
                and_(
                    func.date(Booking.created_at) == date_val,
                    Booking.booking_status.in_(['active', 'confirmed', 'completed'])
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения бронирований за день: {e}")
            return 0

    async def get_daily_revenue(self, date_val: date) -> int:
        """Выручка за день"""
        try:
            query = select(func.sum(Payment.amount)).where(
                and_(
                    func.date(Payment.created_at) == date_val,
                    Payment.status == YooKassaStatus.succeeded
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения выручки за день: {e}")
            return 0

    async def get_daily_new_users(self, date_val: date) -> int:
        """Новые пользователи за день"""
        try:
            query = select(func.count(User.id)).where(
                func.date(User.created_at) == date_val
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения новых пользователей за день: {e}")
            return 0

    async def get_period_bookings_count(self, start_date: datetime, end_date: datetime) -> int:
        """Количество бронирований за период"""
        try:
            query = select(func.count(Booking.id)).where(
                and_(
                    Booking.created_at >= start_date,
                    Booking.created_at <= end_date,
                    Booking.booking_status.in_(['active', 'confirmed', 'completed'])
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения бронирований за период: {e}")
            return 0

    async def get_period_revenue(self, start_date: datetime, end_date: datetime) -> int:
        """Выручка за период"""
        try:
            query = select(func.sum(Payment.amount)).where(
                and_(
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date,
                    Payment.status == YooKassaStatus.succeeded
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения выручки за период: {e}")
            return 0

    async def get_period_new_users(self, start_date: datetime, end_date: datetime) -> int:
        """Новые пользователи за период"""
        try:
            query = select(func.count(User.id)).where(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения новых пользователей за период: {e}")
            return 0

    async def get_period_completed_excursions(self, start_date: datetime, end_date: datetime) -> int:
        """Завершенные экскурсии за период"""
        try:
            query = select(func.count(ExcursionSlot.id)).where(
                and_(
                    ExcursionSlot.start_datetime >= start_date,
                    ExcursionSlot.start_datetime <= end_date,
                    ExcursionSlot.status == SlotStatus.completed
                )
            )
            result = await self._execute_query(query)
            return result.scalar() or 0
        except Exception as e:
            self.logger.error(f"Ошибка получения завершенных экскурсий: {e}")
            return 0

    async def get_popular_excursion(self, start_date: datetime, end_date: datetime) -> Tuple[str, int]:
        """Самая популярная экскурсия за период"""
        try:
            query = (
                select(
                    Excursion.name,
                    func.count(Booking.id).label('booking_count')
                )
                .select_from(Booking)
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .join(Excursion, ExcursionSlot.excursion_id == Excursion.id)
                .where(
                    and_(
                        Booking.created_at >= start_date,
                        Booking.created_at <= end_date
                    )
                )
                .group_by(Excursion.name)
                .order_by(func.count(Booking.id).desc())
                .limit(1)
            )

            result = await self._execute_query(query)
            row = result.first()
            return (row[0], row[1]) if row else ("Нет данных", 0)

        except Exception as e:
            self.logger.error(f"Ошибка получения популярной экскурсии: {e}")
            return ("Нет данных", 0)
"""Репозиторий для работы со слотами (CRUD операции)"""

from typing import List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.database.models import (
    ExcursionSlot, Excursion, SlotStatus, User,
    Booking
)


class SlotRepository(BaseRepository):
    """Репозиторий для CRUD операций со слотами"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_id(self, slot_id: int) -> Optional[ExcursionSlot]:
        """Получить слот по ID с загрузкой экскурсии"""
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .where(ExcursionSlot.id == slot_id)
        )
        result = await self._execute_query(query)
        return result.scalar_one_or_none()

    async def get_for_date(self, target_date: date) -> List[ExcursionSlot]:
        """Получить слоты на дату с предзагруженной экскурсией"""
        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .where(
                (ExcursionSlot.start_datetime >= date_from) &
                (ExcursionSlot.start_datetime <= date_to)
            )
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_for_period(self, date_from: datetime, date_to: datetime) -> List[ExcursionSlot]:
        """Получить слоты за период с предзагруженной экскурсией"""
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .where(
                (ExcursionSlot.start_datetime >= date_from) &
                (ExcursionSlot.start_datetime <= date_to)
            )
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_schedule(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        excursion_id: Optional[int] = None,
        include_cancelled: bool = False
    ) -> List[ExcursionSlot]:
        """Получить расписание экскурсий"""
        query = select(ExcursionSlot).join(Excursion)

        if date_from:
            query = query.where(ExcursionSlot.start_datetime >= date_from)
        if date_to:
            query = query.where(ExcursionSlot.start_datetime <= date_to)
        if excursion_id:
            query = query.where(ExcursionSlot.excursion_id == excursion_id)
        if not include_cancelled:
            query = query.where(ExcursionSlot.status != SlotStatus.cancelled)

        query = query.order_by(ExcursionSlot.start_datetime)
        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_public_schedule(self, date_from: datetime, date_to: datetime) -> List[ExcursionSlot]:
        """Получить публичное расписание за период"""
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .where(
                and_(
                    ExcursionSlot.start_datetime >= date_from,
                    ExcursionSlot.start_datetime <= date_to,
                    ExcursionSlot.status == SlotStatus.scheduled,
                    ExcursionSlot.captain_id.is_not(None)
                )
            )
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_available(
        self,
        excursion_id: int,
        date_from: datetime,
        date_to: datetime
    ) -> List[ExcursionSlot]:
        """Получить доступные слоты для экскурсии в указанный период"""
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion), selectinload(ExcursionSlot.captain))
            .where(
                and_(
                    ExcursionSlot.excursion_id == excursion_id,
                    ExcursionSlot.start_datetime >= date_from,
                    ExcursionSlot.end_datetime <= date_to,
                    ExcursionSlot.status == SlotStatus.scheduled
                )
            )
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_with_bookings(self, slot_id: int) -> Optional[ExcursionSlot]:
        """Получить слот с информацией о бронированиях"""
        query = (
            select(ExcursionSlot)
            .options(
                selectinload(ExcursionSlot.excursion),
                selectinload(ExcursionSlot.captain),
                selectinload(ExcursionSlot.bookings).selectinload(Booking.adult_user)
            )
            .where(ExcursionSlot.id == slot_id)
        )

        result = await self._execute_query(query)
        return result.scalar_one_or_none()

    async def get_captain_slots(
        self,
        captain_telegram_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[ExcursionSlot]:
        """Получить слоты капитана за период"""
        query = (
            select(ExcursionSlot)
            .options(
                selectinload(ExcursionSlot.excursion),
                selectinload(ExcursionSlot.bookings).selectinload(Booking.adult_user)
            )
            .join(User, ExcursionSlot.captain_id == User.id)
            .where(
                and_(
                    User.telegram_id == captain_telegram_id,
                    ExcursionSlot.start_datetime >= start_date,
                    ExcursionSlot.end_datetime <= end_date
                )
            )
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_captain_completed_slots_for_period(
        self,
        captain_id: int,
        start_date: date,
        end_date: date
    ) -> List[ExcursionSlot]:
        """Получить завершенные слоты капитана за период"""
        try:
            from sqlalchemy import select, and_
            from sqlalchemy.orm import selectinload
            from app.database.models import SlotStatus

            query = (
                select(ExcursionSlot)
                .options(selectinload(ExcursionSlot.bookings))
                .where(
                    and_(
                        ExcursionSlot.captain_id == captain_id,
                        ExcursionSlot.start_datetime >= start_date,
                        ExcursionSlot.start_datetime < end_date,
                        ExcursionSlot.status == SlotStatus.completed
                    )
                )
            )

            result = await self._execute_query(query)
            return list(result.scalars().all())

        except Exception as e:
            self.logger.error(f"Ошибка получения слотов капитана: {e}")
            return []

    async def get_conflicting(
        self,
        excursion_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_slot_id: Optional[int] = None
    ) -> Optional[ExcursionSlot]:
        """Проверить наличие конфликтующего слота"""
        conditions = [
            ExcursionSlot.excursion_id == excursion_id,
            ExcursionSlot.status != SlotStatus.cancelled,
            or_(
                and_(
                    ExcursionSlot.start_datetime <= start_datetime,
                    ExcursionSlot.end_datetime > start_datetime
                ),
                and_(
                    ExcursionSlot.start_datetime < end_datetime,
                    ExcursionSlot.end_datetime >= end_datetime
                ),
                and_(
                    ExcursionSlot.start_datetime >= start_datetime,
                    ExcursionSlot.end_datetime <= end_datetime
                )
            )
        ]

        if exclude_slot_id:
            conditions.append(ExcursionSlot.id != exclude_slot_id)

        query = select(ExcursionSlot).where(and_(*conditions))
        result = await self._execute_query(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        excursion_id: int,
        start_datetime: datetime,
        max_people: int,
        max_weight: int,
        captain_id: Optional[int] = None,
        status: SlotStatus = SlotStatus.scheduled
    ) -> ExcursionSlot:
        """Создать новый слот в расписании"""
        from app.database.repositories.excursion_repository import ExcursionRepository
        excursion_repo = ExcursionRepository(self.session)
        excursion = await excursion_repo.get_by_id(excursion_id)

        if not excursion:
            raise ValueError(f"Экскурсия с id {excursion_id} не найдена")
        end_datetime = start_datetime + timedelta(minutes=excursion.base_duration_minutes)
        slot_data = {
            'excursion_id': excursion_id,
            'captain_id': captain_id,
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'max_people': max_people,
            'max_weight': max_weight,
            'status': status
        }

        return await self._create(ExcursionSlot, **slot_data)

    async def update_status(self, slot_id: int, status: SlotStatus) -> bool:
        """Обновить статус слота"""
        updated = await self._update(
            ExcursionSlot,
            ExcursionSlot.id == slot_id,
            status=status
        )
        return updated > 0

    async def assign_captain(self, slot_id: int, captain_id: int) -> bool:
        """Назначить капитана на слот"""
        updated = await self._update(
            ExcursionSlot,
            ExcursionSlot.id == slot_id,
            captain_id=captain_id
        )
        return updated > 0

    async def update(self, slot_id: int, **data) -> bool:
        """Обновить данные слота"""
        clean_data = {k: v for k, v in data.items() if v is not None}
        if not clean_data:
            return False

        # Если обновляем start_datetime, нужно пересчитать end_datetime
        if 'start_datetime' in clean_data:
            # Получаем слот чтобы узнать экскурсию
            slot = await self.get_by_id(slot_id)
            if slot and slot.excursion:
                clean_data['end_datetime'] = clean_data['start_datetime'] + \
                    timedelta(minutes=slot.excursion.base_duration_minutes)

        updated = await self._update(ExcursionSlot, ExcursionSlot.id == slot_id, **clean_data)
        return updated > 0
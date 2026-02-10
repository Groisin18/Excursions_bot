"""Менеджер для бизнес-логики слотов"""

from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from ..repositories.slot_repository import SlotRepository
from ..repositories.excursion_repository import ExcursionRepository
from ..repositories.user_repository import UserRepository
from app.database.models import (
    ExcursionSlot, SlotStatus, BookingStatus
)


class SlotManager(BaseManager):
    """Менеджер для бизнес-логики слотов"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.slot_repo = SlotRepository(session)
        self.excursion_repo = ExcursionRepository(session)
        self.user_repo = UserRepository(session)

    async def create_slot(
        self,
        excursion_id: int,
        start_datetime: datetime,
        max_people: int,
        max_weight: int,
        captain_id: Optional[int] = None,
        status: SlotStatus = SlotStatus.scheduled
    ) -> Tuple[Optional[ExcursionSlot], str]:
        """Создать слот с проверкой конфликтов"""
        self._log_operation_start("create_slot",
                                 excursion_id=excursion_id,
                                 start_datetime=start_datetime,
                                 max_people=max_people)

        try:
            # Получаем экскурсию для расчета времени окончания
            excursion = await self.excursion_repo.get_by_id(excursion_id)
            if not excursion:
                error_msg = "Экскурсия не найдена"
                self.logger.warning(error_msg)
                return None, error_msg

            end_datetime = start_datetime + timedelta(minutes=excursion.base_duration_minutes)

            # Проверяем конфликты
            conflicting_slot = await self.slot_repo.get_conflicting(
                excursion_id, start_datetime, end_datetime
            )

            if conflicting_slot:
                error_msg = f"Конфликт с существующим слотом #{conflicting_slot.id}"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем доступность капитана
            if captain_id:
                captain_busy = await self.user_repo.check_captain_availability(
                    captain_id, start_datetime, end_datetime
                )
                if captain_busy:
                    captain = await self.user_repo.get_user_by_id(captain_id)
                    captain_name = captain.full_name if captain else f"ID {captain_id}"
                    error_msg = f"Капитан {captain_name} занят в это время"
                    self.logger.warning(error_msg)
                    return None, error_msg

            # Создаем слот
            slot = await self.slot_repo.create(
                excursion_id=excursion_id,
                start_datetime=start_datetime,
                max_people=max_people,
                max_weight=max_weight,
                captain_id=captain_id,
                status=status
            )

            # Рассчитываем время окончания и обновляем
            await self.slot_repo.update(slot.id, end_datetime=end_datetime)
            await self._refresh(slot)

            self._log_operation_end("create_slot",
                                   success=True,
                                   slot_id=slot.id)

            return slot, ""

        except Exception as e:
            self._log_operation_end("create_slot", success=False)
            error_msg = f"Ошибка создания слота: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return None, error_msg

    async def reschedule_slot(
        self,
        slot_id: int,
        new_start_datetime: datetime
    ) -> Tuple[bool, str]:
        """Перенести слот на новое время"""
        self._log_operation_start("reschedule_slot",
                                 slot_id=slot_id,
                                 new_start=new_start_datetime)

        try:
            # Получаем текущий слот
            slot = await self.slot_repo.get_by_id(slot_id)
            if not slot:
                error_msg = "Слот не найден"
                self.logger.warning(error_msg)
                return False, error_msg

            # Рассчитываем новое время окончания
            excursion = await self.excursion_repo.get_by_id(slot.excursion_id)
            if not excursion:
                error_msg = "Экскурсия не найдена"
                self.logger.warning(error_msg)
                return False, error_msg

            new_end_datetime = new_start_datetime + timedelta(minutes=excursion.base_duration_minutes)

            # Проверяем конфликты (исключая текущий слот)
            conflicting_slot = await self.slot_repo.get_conflicting(
                slot.excursion_id,
                new_start_datetime,
                new_end_datetime,
                exclude_slot_id=slot_id
            )

            if conflicting_slot:
                error_msg = f"Конфликт с слотом #{conflicting_slot.id}"
                self.logger.warning(error_msg)
                return False, error_msg

            # Проверяем доступность капитана
            if slot.captain_id:
                captain_busy = await self.user_repo.check_captain_availability(
                    slot.captain_id,
                    new_start_datetime,
                    new_end_datetime,
                    exclude_slot_id=slot_id
                )

                if captain_busy:
                    captain = await self.user_repo.get_user_by_id(slot.captain_id)
                    captain_name = captain.full_name if captain else f"ID {slot.captain_id}"
                    error_msg = f"Капитан {captain_name} занят в это время"
                    self.logger.warning(error_msg)
                    return False, error_msg

            # Обновляем слот
            updated = await self.slot_repo.update(
                slot_id,
                start_datetime=new_start_datetime,
                end_datetime=new_end_datetime
            )

            if updated:
                self._log_operation_end("reschedule_slot", success=True)
                return True, ""
            else:
                error_msg = "Не удалось обновить слот"
                self.logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            self._log_operation_end("reschedule_slot", success=False)
            error_msg = f"Ошибка переноса слота: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def get_booked_places(self, slot_id: int) -> int:
        """Получить количество забронированных мест для слота"""
        try:
            # Получаем слот с бронированиями
            slot = await self.slot_repo.get_with_bookings(slot_id)
            if not slot:
                return 0

            # Считаем активные бронирования
            total = 0
            for booking in slot.bookings:
                if booking.booking_status == BookingStatus.active:
                    total += booking.people_count  # взрослые
                    # дети считаются отдельно через BookingChild

            return total

        except Exception as e:
            self.logger.error(f"Ошибка расчета занятых мест для слота {slot_id}: {e}")
            return 0

    async def get_current_weight(self, slot_id: int) -> int:
        """Получить текущий вес для слота"""
        try:
            # Получаем слот с бронированиями
            slot = await self.slot_repo.get_with_bookings(slot_id)
            if not slot:
                return 0

            total_weight = 0

            # Вес капитана
            if slot.captain and slot.captain.weight:
                total_weight += slot.captain.weight

            # Вес клиентов из активных бронирований
            for booking in slot.bookings:
                if booking.booking_status == BookingStatus.active:
                    if booking.client and booking.client.weight:
                        total_weight += booking.client.weight

            return total_weight

        except Exception as e:
            self.logger.error(f"Ошибка расчета веса для слота {slot_id}: {e}")
            return 0

    async def get_slot_full_info(self, slot_id: int) -> Optional[Dict]:
        """Получить полную информацию о слоте"""
        try:
            slot = await self.slot_repo.get_with_bookings(slot_id)
            if not slot:
                return None

            booked_places = await self.get_booked_places(slot_id)
            current_weight = await self.get_current_weight(slot_id)

            return {
                'slot': slot,
                'available_places': max(0, slot.max_people - booked_places),
                'booked_places': booked_places,
                'current_weight': current_weight,
                'available_weight': max(0, slot.max_weight - current_weight),
                'is_available': (
                    slot.status == SlotStatus.scheduled and
                    slot.start_datetime > datetime.now()
                )
            }

        except Exception as e:
            self.logger.error(f"Ошибка получения полной информации о слоте {slot_id}: {e}")
            return None

    async def check_availability(
        self,
        slot_id: int,
        additional_people: int = 0,
        additional_weight: int = 0
    ) -> bool:
        """Проверить доступность слота для бронирования"""
        try:
            slot = await self.slot_repo.get_by_id(slot_id)
            if not slot:
                return False

            booked_places = await self.get_booked_places(slot_id)
            current_weight = await self.get_current_weight(slot_id)

            places_available = (booked_places + additional_people) <= slot.max_people
            weight_available = (current_weight + additional_weight) <= slot.max_weight

            return places_available and weight_available

        except Exception as e:
            self.logger.error(f"Ошибка проверки доступности слота {slot_id}: {e}")
            return False
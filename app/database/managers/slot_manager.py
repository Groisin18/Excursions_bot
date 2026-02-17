"""Менеджер для бизнес-логики слотов"""

from typing import Tuple, Optional, Dict, List, Union
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from .base import BaseManager
from app.database.repositories import (
    SlotRepository, ExcursionRepository, UserRepository
)
from app.database.models import (
    ExcursionSlot, SlotStatus, BookingStatus, Booking, PaymentStatus,
    SchedulePeriod, Excursion
)
from app.utils.datetime_utils import get_weekday_name


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
                    captain = await self.user_repo.get_by_id(captain_id)
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
                    captain = await self.user_repo.get_by_id(slot.captain_id)
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

    async def cancel_slot(self, slot_id: int) -> Tuple[bool, Optional[ExcursionSlot]]:
        """Отменить слот и все связанные бронирования"""

        slot = await self.slot_repo.get_by_id(slot_id)
        if not slot:
            return False, None

        slot.status = SlotStatus.cancelled

        # Отменяем все связанные бронирования
        if slot.bookings:
            for booking in slot.bookings:
                if booking.booking_status == BookingStatus.active:
                    booking.booking_status = BookingStatus.cancelled

        await self.slot_repo.update(slot)
        return True, slot

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

            # Используем свойства Booking
            active_bookings = []
            if hasattr(slot, 'bookings'):
                active_bookings = [b for b in slot.bookings if b.is_active]

            return {
                'slot': slot,
                'available_places': max(0, slot.max_people - booked_places),
                'booked_places': booked_places,
                'current_weight': current_weight,
                'available_weight': max(0, slot.max_weight - current_weight),
                'is_available': (
                    slot.status == SlotStatus.scheduled and
                    slot.start_datetime > datetime.now()
                ),
                'active_bookings': active_bookings,
                'active_booking_count': len(active_bookings)
            }

        except Exception as e:
            self.logger.error(f"Ошибка получения полной информации о слоте {slot_id}: {e}")
            return None

    async def get_active_bookings(self):
        """Получить все активные бронирования с джойнами"""
        result = await self.session.execute(
            select(Booking)
            .options(selectinload(Booking.slot).selectinload(ExcursionSlot.excursion))
            .options(selectinload(Booking.slot).selectinload(ExcursionSlot.captain))
            .options(selectinload(Booking.adult_user))
            .where(Booking.booking_status == BookingStatus.active)
            .order_by(Booking.created_at.desc())
        )
        return result.scalars().all()

    async def get_unpaid_bookings(self):
        """Получить все неоплаченные активные бронирования"""

        result = await self.session.execute(
            select(Booking)
            .options(selectinload(Booking.adult_user))
            .options(selectinload(Booking.slot).selectinload(ExcursionSlot.excursion))
            .where(Booking.payment_status != PaymentStatus.paid)
            .where(Booking.booking_status == BookingStatus.active)
        )
        return result.scalars().all()

    async def get_detailed_schedule_for_date(self, target_date: date) -> str:
        """Получить детальное расписание на дату с полной информацией"""

        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        # Получаем слоты с расписанием, предзагружаем экскурсию
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .options(selectinload(ExcursionSlot.captain))  # если нужен капитан
            .where(ExcursionSlot.start_datetime >= date_from)
            .where(ExcursionSlot.start_datetime <= date_to)
            .where(ExcursionSlot.status != SlotStatus.cancelled)  # include_cancelled=False
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self.session.execute(query)
        slots = result.scalars().all()

        if not slots:
            return ""

        response = f"Расписание на {target_date.strftime('%d.%m.%Y (%A)')}:\n\n"

        for slot in slots:
            excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

            status_text = {
                SlotStatus.scheduled: "Запланирована",
                SlotStatus.in_progress: "В процессе",
                SlotStatus.completed: "Завершена",
                SlotStatus.cancelled: "Отменена"
            }.get(slot.status, "Неизвестно")

            booked_places = await self.get_booked_places(slot.id)
            current_weight = await self.get_current_weight(slot.id)

            start_time = slot.start_datetime.strftime("%H:%M")
            end_time = slot.end_datetime.strftime("%H:%M") if slot.end_datetime else "?"

            response += (
                f"• {start_time}-{end_time} "
                f"({excursion_name})\n"
                f"  ID слота: {slot.id}\n"
                f"Свободно мест: {slot.max_people - booked_places}/{slot.max_people}\n"
                f"Занято веса: {current_weight}/{slot.max_weight} кг\n"
                f"({status_text})\n"
            )

            if slot.captain_id and slot.captain:
                response += f"  Капитан: {slot.captain.full_name}\n"

            response += "\n"

        return response

    async def get_weekly_schedule(self, days_ahead: int = 7) -> Tuple[str, Dict[date, List]]:
        """Получить расписание на неделю вперед"""

        date_from = datetime.now()
        date_to = date_from + timedelta(days=days_ahead)

        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .options(selectinload(ExcursionSlot.captain))
            .where(ExcursionSlot.start_datetime >= date_from)
            .where(ExcursionSlot.start_datetime <= date_to)
            .where(ExcursionSlot.status != SlotStatus.cancelled)
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self.session.execute(query)
        slots = result.scalars().all()

        if not slots:
            return "", {}

        # Группируем по датам
        slots_by_date = {}
        for slot in slots:
            date_key = slot.start_datetime.date()
            if date_key not in slots_by_date:
                slots_by_date[date_key] = []
            slots_by_date[date_key].append(slot)

        response = f"Расписание на ближайшие {days_ahead} дней:\n\n"

        for slot_date, date_slots in sorted(slots_by_date.items()):
            response += f"{slot_date.strftime('%d.%m.%Y (%A)')}:\n"

            for slot in date_slots:
                excursion_name = slot.excursion.name if slot.excursion else "Неизвестная экскурсия"

                status_text = {
                    SlotStatus.scheduled: "Запланирована",
                    SlotStatus.in_progress: "В процессе",
                    SlotStatus.completed: "Завершена",
                    SlotStatus.cancelled: "Отменена"
                }.get(slot.status, "Неизвестно")

                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M") if slot.end_datetime else "?"

                response += f"  • {start_time}-{end_time} ({excursion_name}) - {status_text}\n"

            response += "\n"

        return response, slots_by_date

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

    async def format_public_schedule_for_date(
        self,
        target_date: date,
        slots: list
    ) -> str:
        """Форматировать расписание для пользователей"""
        response = f"Расписание на {target_date.strftime('%d.%m.%Y')}:\n\n"

        for slot in slots:
            excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
            start_time = slot.start_datetime.strftime("%H:%M")
            end_time = slot.end_datetime.strftime("%H:%M")

            booked = await self.get_booked_places(slot.id)
            free_places = slot.max_people - booked
            places_text = f"({free_places} мест)" if free_places > 0 else "(Мест нет)"

            response += f"• {start_time}-{end_time} {excursion_name} {places_text}\n"

        response += "\nНажмите на экскурсию, чтобы увидеть детали и записаться"
        return response

    async def _get_schedule(
        self,
        period_type: SchedulePeriod = SchedulePeriod.DATE,
        target_date: Optional[date] = None,
        days_ahead: Optional[int] = None,
        max_slots_per_day: Optional[int] = None
    ) -> Union[Tuple[Optional[str], List], Tuple[Optional[str], Dict]]:
        """
        Универсальный метод получения расписания
        """
        # Определяем временной диапазон
        if period_type == SchedulePeriod.DATE:
            if not target_date:
                target_date = datetime.now().date()
            date_from = datetime.combine(target_date, datetime.min.time())
            date_to = datetime.combine(target_date, datetime.max.time())
        elif period_type in (SchedulePeriod.WEEK, SchedulePeriod.MONTH):
            if not days_ahead:
                days_ahead = 7 if period_type == SchedulePeriod.WEEK else 30
            date_from = datetime.now()
            date_to = date_from + timedelta(days=days_ahead)
        else:
            raise ValueError(f"Неизвестный тип периода: {period_type}")

        # Получаем слоты с предзагрузкой экскурсии
        query = (
            select(ExcursionSlot)
            .options(selectinload(ExcursionSlot.excursion))
            .where(ExcursionSlot.start_datetime >= date_from)
            .where(ExcursionSlot.start_datetime <= date_to)
            .where(ExcursionSlot.status == SlotStatus.scheduled)
            .order_by(ExcursionSlot.start_datetime)
        )

        result = await self.session.execute(query)
        slots = result.scalars().all()

        if not slots:
            return None, [] if period_type == SchedulePeriod.DATE else {}

        # Форматирование в зависимости от типа периода
        if period_type == SchedulePeriod.DATE:
            formatted_text = await self.format_public_schedule_for_date(target_date, slots)
            return formatted_text, slots

        # Для WEEK и MONTH группируем по датам
        slots_by_date = {}
        for slot in slots:
            date_key = slot.start_datetime.date()
            if date_key not in slots_by_date:
                slots_by_date[date_key] = []
            slots_by_date[date_key].append(slot)

        # Форматируем текст
        period_names = {
            SchedulePeriod.WEEK: "неделю",
            SchedulePeriod.MONTH: "месяц"
        }
        text = f"Расписание на {period_names[period_type]}:\n\n"

        for date_key in sorted(slots_by_date.keys()):
            date_slots = slots_by_date[date_key]
            text += f"{date_key.strftime('%d.%m.%Y')} ({get_weekday_name(date_key)}):\n"

            # Для MONTH ограничиваем количество слотов на день
            slots_to_show = date_slots
            if period_type == SchedulePeriod.MONTH and max_slots_per_day:
                slots_to_show = date_slots[:max_slots_per_day]

            for slot in slots_to_show:
                excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M")

                booked = await self.get_booked_places(slot.id)
                free_places = slot.max_people - booked
                places_text = f"({free_places} мест)" if free_places > 0 else "(Мест нет)"

                text += f"• {start_time}-{end_time} {excursion_name} {places_text}\n"

            if period_type == SchedulePeriod.MONTH and max_slots_per_day and len(date_slots) > max_slots_per_day:
                text += f"  ... и еще {len(date_slots) - max_slots_per_day} экскурсий\n"

            text += "\n"

        return text, slots_by_date

    async def get_date_schedule(self, target_date: date) -> Tuple[Optional[str], List]:
        """Обертка для получения расписания на дату"""
        return await self._get_schedule(
            period_type=SchedulePeriod.DATE,
            target_date=target_date
        )

    async def get_week_schedule(self) -> Tuple[Optional[str], Dict]:
        """Обертка для получения расписания на неделю"""
        return await self._get_schedule(
            period_type=SchedulePeriod.WEEK,
            days_ahead=7
        )

    async def get_month_schedule(self) -> Tuple[Optional[str], Dict]:
        """Обертка для получения расписания на месяц"""
        return await self._get_schedule(
            period_type=SchedulePeriod.MONTH,
            days_ahead=30,
            max_slots_per_day=3
        )

    async def _get_excursion_schedule(
        self,
        exc_id: int,
        period_type: SchedulePeriod = SchedulePeriod.PERIOD,
        target_date: Optional[date] = None,
        days_ahead: Optional[int] = None
    ) -> Tuple[Optional[Excursion], Optional[str], Union[List, Dict]]:
        """
        Универсальный метод получения расписания экскурсии

        Args:
            exc_id: ID экскурсии
            period_type: тип периода (PERIOD для интервала, DATE для конкретной даты)
            target_date: дата (для DATE)
            days_ahead: дней вперед (для PERIOD)

        Returns:
            (excursion, formatted_text, slots_data)
            - Для PERIOD: slots_data = slots_by_date_dict
            - Для DATE: slots_data = list_of_slots
        """

        # Получаем экскурсию
        result = await self.session.execute(
            select(Excursion)
            .where(Excursion.id == exc_id)
        )
        excursion = result.scalar_one_or_none()

        if not excursion:
            return None, None, ({} if period_type == SchedulePeriod.PERIOD else [])

        # Определяем временной диапазон
        if period_type == SchedulePeriod.DATE:
            if not target_date:
                target_date = datetime.now().date()
            date_from = datetime.combine(target_date, datetime.min.time())
            date_to = datetime.combine(target_date, datetime.max.time())
        else:  # PERIOD
            if not days_ahead:
                days_ahead = 30
            date_from = datetime.now()
            date_to = date_from + timedelta(days=days_ahead)

        # Получаем слоты
        result = await self.session.execute(
            select(ExcursionSlot)
            .where(ExcursionSlot.excursion_id == exc_id)
            .where(ExcursionSlot.start_datetime >= date_from)
            .where(ExcursionSlot.start_datetime <= date_to)
            .where(ExcursionSlot.status == SlotStatus.scheduled)
            .order_by(ExcursionSlot.start_datetime)
        )
        slots = result.scalars().all()

        # Форматирование в зависимости от типа периода
        if period_type == SchedulePeriod.DATE:
            if not slots:
                return excursion, None, []

            text = (
                f"Экскурсия: {excursion.name}\n"
                f"Дата: {target_date.strftime('%d.%m.%Y')} ({get_weekday_name(target_date)})\n\n"
            )

            for slot in slots:
                start_time = slot.start_datetime.strftime("%H:%M")
                end_time = slot.end_datetime.strftime("%H:%M")

                booked = await self.get_booked_places(slot.id)
                free_places = slot.max_people - booked

                current_weight = await self.get_current_weight(slot.id)
                free_weight = slot.max_weight - current_weight

                if free_places > 0 and free_weight > 0:
                    places_text = f"({free_places} мест, ограничение по весу - не более {free_weight} кг)"
                else:
                    places_text = "(Мест нет)"

                text += f"• {start_time}-{end_time} {places_text}\n"

            text += "\nНажмите на экскурсию, чтобы увидеть детали и записаться"
            return excursion, text, slots

        else:  # PERIOD
            if not slots:
                return excursion, None, {}

            # Группируем по датам и форматируем
            slots_by_date = {}
            for slot in slots:
                date_key = slot.start_datetime.date()
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)

            # Форматируем текст

            text = f"{excursion.name}\n"

            for date_key in sorted(slots_by_date.keys()):
                date_slots = slots_by_date[date_key]
                text += f"\n{date_key.strftime('%d.%m.%Y')} ({get_weekday_name(date_key)}):\n"

                for slot in date_slots:
                    start_time = slot.start_datetime.strftime("%H:%M")
                    end_time = slot.end_datetime.strftime("%H:%M")

                    booked = await self.get_booked_places(slot.id)
                    free_places = slot.max_people - booked
                    places_text = f"({free_places} мест)" if free_places > 0 else "(Мест нет)"

                    text += f"• {start_time}-{end_time} {places_text}\n"

            return excursion, text, slots_by_date

    async def get_excursion_schedule_period(self, exc_id: int, days_ahead: int):
        """Обертка для получения расписания экскурсии на период"""
        return await self._get_excursion_schedule(
            exc_id=exc_id,
            period_type=SchedulePeriod.PERIOD,
            days_ahead=days_ahead
        )

    async def get_excursion_slots_for_date(self, exc_id: int, target_date: date):
        """Обертка для получения слотов экскурсии на дату"""
        return await self._get_excursion_schedule(
            exc_id=exc_id,
            period_type=SchedulePeriod.DATE,
            target_date=target_date
        )
"""Тесты для SlotManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, date

from app.database.managers.slot_manager import SlotManager
from app.database.models import SlotStatus, BookingStatus


class TestSlotManager:
    """Тесты для SlotManager."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканными зависимостями."""
        with patch("app.database.managers.slot_manager.BaseManager.__init__", return_value=None):
            manager = SlotManager(mock_session)
            manager.session = mock_session
            manager.logger = MagicMock()
            manager.slot_repo = AsyncMock()
            manager.excursion_repo = AsyncMock()
            manager.user_repo = AsyncMock()
            return manager

    # ========== create_slot ==========

    @pytest.mark.asyncio
    async def test_create_slot_excursion_not_found(self, manager):
        """Экскурсия не найдена."""
        manager.excursion_repo.get_by_id.return_value = None

        slot, error = await manager.create_slot(
            excursion_id=1, start_datetime=datetime.now(),
            max_people=10, max_weight=1000
        )

        assert slot is None
        assert "не найдена" in error.lower()

    @pytest.mark.asyncio
    async def test_create_slot_conflict(self, manager):
        """Конфликт с существующим слотом."""
        excursion = MagicMock()
        excursion.base_duration_minutes = 60
        manager.excursion_repo.get_by_id.return_value = excursion

        conflict = MagicMock()
        conflict.id = 5
        manager.slot_repo.get_conflicting.return_value = conflict

        slot, error = await manager.create_slot(
            excursion_id=1, start_datetime=datetime.now(),
            max_people=10, max_weight=1000
        )

        assert slot is None
        assert "конфликт" in error.lower()

    @pytest.mark.asyncio
    async def test_create_slot_captain_busy(self, manager):
        """Капитан занят."""
        excursion = MagicMock()
        excursion.base_duration_minutes = 60
        manager.excursion_repo.get_by_id.return_value = excursion
        manager.slot_repo.get_conflicting.return_value = None
        manager.user_repo.check_captain_availability.return_value = True

        captain = MagicMock()
        captain.full_name = "Иван Иванов"
        manager.user_repo.get_by_id.return_value = captain

        slot, error = await manager.create_slot(
            excursion_id=1, start_datetime=datetime.now(),
            max_people=10, max_weight=1000, captain_id=5
        )

        assert slot is None
        assert "занят" in error.lower()

    @pytest.mark.asyncio
    async def test_create_slot_success(self, manager):
        """Успешное создание слота."""
        excursion = MagicMock()
        excursion.base_duration_minutes = 60
        manager.excursion_repo.get_by_id.return_value = excursion
        manager.slot_repo.get_conflicting.return_value = None

        mock_slot = MagicMock()
        mock_slot.id = 1
        manager.slot_repo.create.return_value = mock_slot

        slot, error = await manager.create_slot(
            excursion_id=1, start_datetime=datetime.now(),
            max_people=10, max_weight=1000
        )

        assert slot is not None
        assert error == ""

    @pytest.mark.asyncio
    async def test_create_slot_exception(self, manager):
        """Ошибка при создании слота."""
        manager.excursion_repo.get_by_id.side_effect = Exception("DB error")

        slot, error = await manager.create_slot(
            excursion_id=1, start_datetime=datetime.now(),
            max_people=10, max_weight=1000
        )

        assert slot is None
        assert "ошибка" in error.lower()

    # ========== cancel_slot ==========

    @pytest.mark.asyncio
    async def test_cancel_slot_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_by_id.return_value = None

        success, slot = await manager.cancel_slot(1)

        assert success is False
        assert slot is None

    @pytest.mark.asyncio
    async def test_cancel_slot_success(self, manager):
        """Успешная отмена слота."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        mock_slot.bookings = []
        manager.slot_repo.get_by_id.return_value = mock_slot

        success, slot = await manager.cancel_slot(1)

        assert success is True
        assert mock_slot.status == SlotStatus.cancelled

    @pytest.mark.asyncio
    async def test_cancel_slot_cancels_active_bookings(self, manager):
        """Отмена слота отменяет активные бронирования."""
        mock_booking = MagicMock()
        mock_booking.booking_status = BookingStatus.active

        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        mock_slot.bookings = [mock_booking]
        manager.slot_repo.get_by_id.return_value = mock_slot

        success, slot = await manager.cancel_slot(1)

        assert success is True
        assert mock_booking.booking_status == BookingStatus.cancelled

    # ========== check_availability ==========

    @pytest.mark.asyncio
    async def test_check_availability_slot_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_by_id.return_value = None

        result = await manager.check_availability(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_availability_true(self, manager):
        """Слот доступен."""
        mock_slot = MagicMock()
        mock_slot.max_people = 10
        mock_slot.max_weight = 1000
        manager.slot_repo.get_by_id.return_value = mock_slot

        # get_booked_places и get_current_weight вызываются внутри
        manager.get_booked_places = AsyncMock(return_value=3)
        manager.get_current_weight = AsyncMock(return_value=300)

        result = await manager.check_availability(1, additional_people=2, additional_weight=100)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_availability_false_places(self, manager):
        """Недостаточно мест."""
        mock_slot = MagicMock()
        mock_slot.max_people = 5
        mock_slot.max_weight = 1000
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.get_booked_places = AsyncMock(return_value=4)
        manager.get_current_weight = AsyncMock(return_value=0)

        result = await manager.check_availability(1, additional_people=2)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_availability_false_weight(self, manager):
        """Превышение веса."""
        mock_slot = MagicMock()
        mock_slot.max_people = 10
        mock_slot.max_weight = 500
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.get_booked_places = AsyncMock(return_value=0)
        manager.get_current_weight = AsyncMock(return_value=450)

        result = await manager.check_availability(1, additional_weight=100)

        assert result is False

    # ========== get_slots_to_start ==========

    @pytest.mark.asyncio
    async def test_get_slots_to_start(self, manager):
        """Получение слотов для старта."""
        mock_slot = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result

        result = await manager.get_slots_to_start()

        assert len(result) == 1

    # ========== get_slots_to_complete ==========

    @pytest.mark.asyncio
    async def test_get_slots_to_complete(self, manager):
        """Получение слотов для завершения."""
        mock_slot = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result

        result = await manager.get_slots_to_complete()

        assert len(result) == 1

    # ========== get_empty_slots_to_cancel ==========

    @pytest.mark.asyncio
    async def test_get_empty_slots_to_cancel(self, manager):
        """Получение пустых слотов для отмены."""
        mock_slot = MagicMock()
        manager.slot_repo.get_empty_slots_in_progress.return_value = [mock_slot]

        result = await manager.get_empty_slots_to_cancel()

        assert len(result) == 1

    # ========== reschedule_slot ==========

    @pytest.mark.asyncio
    async def test_reschedule_slot_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_by_id.return_value = None

        success, error = await manager.reschedule_slot(1, datetime.now())

        assert success is False
        assert "не найден" in error.lower()

    @pytest.mark.asyncio
    async def test_reschedule_slot_success(self, manager):
        """Успешный перенос слота."""
        mock_slot = MagicMock()
        mock_slot.excursion_id = 1
        mock_slot.captain_id = None
        manager.slot_repo.get_by_id.return_value = mock_slot

        excursion = MagicMock()
        excursion.base_duration_minutes = 60
        manager.excursion_repo.get_by_id.return_value = excursion

        manager.slot_repo.get_conflicting.return_value = None
        manager.slot_repo.update.return_value = True

        success, error = await manager.reschedule_slot(1, datetime.now())

        assert success is True
        assert error == ""

    # ========== get_slots_without_captain ==========

    @pytest.mark.asyncio
    async def test_get_slots_without_captain(self, manager):
        """Получение слотов без капитана."""
        mock_slot = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result

        result = await manager.get_slots_without_captain()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_slots_without_captain_error(self, manager):
        """Ошибка при получении слотов без капитана."""
        manager.session.execute.side_effect = Exception("DB error")

        result = await manager.get_slots_without_captain()

        assert result == []

    # ========== get_slot_full_info ==========

    @pytest.mark.asyncio
    async def test_get_slot_full_info_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_with_bookings.return_value = None

        result = await manager.get_slot_full_info(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_slot_full_info_success(self, manager):
        """Успешное получение полной информации."""
        mock_slot = MagicMock()
        mock_slot.max_people = 10
        mock_slot.max_weight = 1000
        mock_slot.status = SlotStatus.scheduled
        mock_slot.start_datetime = datetime.now() + timedelta(hours=5)
        mock_slot.bookings = []
        manager.slot_repo.get_with_bookings.return_value = mock_slot
        manager.get_booked_places = AsyncMock(return_value=3)
        manager.get_current_weight = AsyncMock(return_value=300)

        result = await manager.get_slot_full_info(1)

        assert result is not None
        assert result['available_places'] == 7
        assert result['available_weight'] == 700
        assert result['is_available'] is True

    # ========== get_weekly_schedule ==========

    @pytest.mark.asyncio
    async def test_get_weekly_schedule_empty(self, manager):
        """Пустое расписание."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        manager.session.execute.return_value = mock_result

        text, slots_dict = await manager.get_weekly_schedule()

        assert text == ""
        assert slots_dict == {}

    @pytest.mark.asyncio
    async def test_get_weekly_schedule_with_slots(self, manager):
        """Расписание со слотами."""
        mock_slot = MagicMock()
        mock_slot.start_datetime = datetime.now() + timedelta(hours=3)
        mock_slot.end_datetime = datetime.now() + timedelta(hours=4)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = MagicMock()
        mock_slot.excursion.name = "Тест"
        mock_slot.captain = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result

        text, slots_dict = await manager.get_weekly_schedule()

        assert "Расписание на ближайшие" in text
        assert len(slots_dict) > 0

    # ========== get_detailed_schedule_for_date ==========

    @pytest.mark.asyncio
    async def test_get_detailed_schedule_empty(self, manager):
        """Пустое детальное расписание."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        manager.session.execute.return_value = mock_result

        text = await manager.get_detailed_schedule_for_date(date(2026, 4, 25))

        assert text == ""

    # ========== get_date_schedule ==========

    @pytest.mark.asyncio
    async def test_get_date_schedule(self, manager):
        """Расписание на дату."""
        mock_slot = MagicMock()
        mock_slot.id = 1
        mock_slot.max_people = 10
        mock_slot.start_datetime = datetime.now() + timedelta(hours=2)
        mock_slot.end_datetime = datetime.now() + timedelta(hours=3)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = MagicMock()
        mock_slot.excursion.name = "Тест"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result
        manager.get_booked_places = AsyncMock(return_value=2)

        text, slots = await manager.get_date_schedule(date(2026, 4, 25))

        assert "Расписание" in text
        assert len(slots) == 1

    # ========== get_active_bookings ==========

    @pytest.mark.asyncio
    async def test_get_active_bookings(self, manager):
        """Получение активных бронирований."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_active_bookings()

        assert len(result) == 1

    # ========== get_unpaid_bookings ==========

    @pytest.mark.asyncio
    async def test_get_unpaid_bookings(self, manager):
        """Получение неоплаченных бронирований."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_unpaid_bookings()

        assert len(result) == 1


    # ========== get_week_schedule ==========

    @pytest.mark.asyncio
    async def test_get_week_schedule(self, manager):
        """Расписание на неделю."""
        mock_slot = MagicMock()
        mock_slot.id = 1
        mock_slot.max_people = 10
        mock_slot.start_datetime = datetime.now() + timedelta(hours=5)
        mock_slot.end_datetime = datetime.now() + timedelta(hours=6)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = MagicMock()
        mock_slot.excursion.name = "Тест"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result
        manager.get_booked_places = AsyncMock(return_value=2)

        text, slots_dict = await manager.get_week_schedule()

        assert "Расписание на неделю" in text
        assert len(slots_dict) > 0

    @pytest.mark.asyncio
    async def test_get_week_schedule_empty(self, manager):
        """Пустое расписание на неделю."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        manager.session.execute.return_value = mock_result

        text, slots_dict = await manager.get_week_schedule()

        assert text is None
        assert slots_dict == {}

    # ========== get_month_schedule ==========

    @pytest.mark.asyncio
    async def test_get_month_schedule(self, manager):
        """Расписание на месяц."""
        mock_slot = MagicMock()
        mock_slot.id = 1
        mock_slot.max_people = 10
        mock_slot.start_datetime = datetime.now() + timedelta(days=2, hours=3)
        mock_slot.end_datetime = datetime.now() + timedelta(days=2, hours=4)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = MagicMock()
        mock_slot.excursion.name = "Тест"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slot]
        manager.session.execute.return_value = mock_result
        manager.get_booked_places = AsyncMock(return_value=0)

        text, slots_dict = await manager.get_month_schedule()

        assert "Расписание на месяц" in text

    # ========== get_excursion_schedule_period ==========

    @pytest.mark.asyncio
    async def test_get_excursion_schedule_period_not_found(self, manager):
        """Экскурсия не найдена."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        manager.session.execute.return_value = mock_result

        excursion, text, slots = await manager.get_excursion_schedule_period(999, 7)

        assert excursion is None
        assert text is None
        assert slots == {}

    @pytest.mark.asyncio
    async def test_get_excursion_schedule_period_success(self, manager):
        """Успешное получение расписания экскурсии на период."""
        mock_excursion = MagicMock()
        mock_excursion.name = "Морская прогулка"

        mock_slot = MagicMock()
        mock_slot.id = 1
        mock_slot.max_people = 10
        mock_slot.start_datetime = datetime.now() + timedelta(days=1, hours=10)
        mock_slot.end_datetime = datetime.now() + timedelta(days=1, hours=11)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = mock_excursion

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_excursion

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_slot]

        manager.session.execute.side_effect = [mock_result1, mock_result2]
        manager.get_booked_places = AsyncMock(return_value=1)

        excursion, text, slots = await manager.get_excursion_schedule_period(1, 7)

        assert excursion is not None
        assert "Морская прогулка" in text
        assert len(slots) == 1

    @pytest.mark.asyncio
    async def test_get_excursion_schedule_period_no_slots(self, manager):
        """Экскурсия есть, но слотов нет."""
        mock_excursion = MagicMock()
        mock_excursion.name = "Морская прогулка"

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_excursion

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        manager.session.execute.side_effect = [mock_result1, mock_result2]

        excursion, text, slots = await manager.get_excursion_schedule_period(1, 7)

        assert excursion is not None
        assert text is None
        assert slots == {}

    # ========== get_excursion_slots_for_date ==========

    @pytest.mark.asyncio
    async def test_get_excursion_slots_for_date_success(self, manager):
        """Слоты экскурсии на дату."""
        mock_excursion = MagicMock()
        mock_excursion.name = "Тест"

        mock_slot = MagicMock()
        mock_slot.id = 1
        mock_slot.max_people = 10
        mock_slot.max_weight = 1000
        mock_slot.start_datetime = datetime.now() + timedelta(hours=10)
        mock_slot.end_datetime = datetime.now() + timedelta(hours=11)
        mock_slot.status = SlotStatus.scheduled
        mock_slot.excursion = mock_excursion

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_excursion

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_slot]

        manager.session.execute.side_effect = [mock_result1, mock_result2]
        manager.get_booked_places = AsyncMock(return_value=0)
        manager.get_current_weight = AsyncMock(return_value=100)

        excursion, text, slots = await manager.get_excursion_slots_for_date(
            1, date(2026, 4, 25)
        )

        assert excursion is not None
        assert "Тест" in text
        assert len(slots) == 1

    @pytest.mark.asyncio
    async def test_get_excursion_slots_for_date_no_slots(self, manager):
        """Нет слотов на дату."""
        mock_excursion = MagicMock()
        mock_excursion.name = "Тест"

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_excursion

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        manager.session.execute.side_effect = [mock_result1, mock_result2]

        excursion, text, slots = await manager.get_excursion_slots_for_date(
            1, date(2026, 4, 25)
        )

        assert excursion is not None
        assert text is None
        assert slots == []
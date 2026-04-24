"""Тесты для BookingManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.database.managers.booking_manager import BookingManager
from app.database.models import (
    BookingStatus, SlotStatus, ClientStatus, PaymentStatus
)


class TestBookingManager:
    """Тесты для BookingManager."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканными зависимостями."""
        with patch("app.database.managers.booking_manager.BaseManager.__init__", return_value=None):
            manager = BookingManager(mock_session)
            manager.session = mock_session
            manager.logger = MagicMock()
            manager.booking_repo = AsyncMock()
            manager.slot_repo = AsyncMock()
            manager.user_repo = AsyncMock()
            manager.promo_repo = AsyncMock()
            return manager

    # ========== create_booking ==========

    @pytest.mark.asyncio
    async def test_create_booking_slot_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_by_id.return_value = None

        booking, error = await manager.create_booking(
            slot_id=1, adult_user_id=5, children_count=0, total_price=5000
        )

        assert booking is None
        assert "не найден" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_slot_cancelled(self, manager):
        """Слот отменён."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.cancelled
        manager.slot_repo.get_by_id.return_value = mock_slot

        booking, error = await manager.create_booking(
            slot_id=1, adult_user_id=5, children_count=0, total_price=5000
        )

        assert booking is None
        assert "cancelled" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_client_not_found(self, manager):
        """Клиент не найден."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.user_repo.get_by_id.return_value = None

        booking, error = await manager.create_booking(
            slot_id=1, adult_user_id=5, children_count=0, total_price=5000
        )

        assert booking is None
        assert "клиент не найден" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_duplicate(self, manager):
        """Уже есть активная бронь."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.user_repo.get_by_id.return_value = MagicMock()
        manager.booking_repo.get_user_active_for_slot.return_value = MagicMock()

        booking, error = await manager.create_booking(
            slot_id=1, adult_user_id=5, children_count=0, total_price=5000
        )

        assert booking is None
        assert "уже есть активная бронь" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_not_enough_places(self, manager):
        """Недостаточно мест."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        mock_slot.max_people = 5
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.user_repo.get_by_id.return_value = MagicMock()
        manager.booking_repo.get_user_active_for_slot.return_value = None

        with patch("app.database.managers.booking_manager.SlotManager") as MockSlotManager:
            mock_slot_mgr = AsyncMock()
            mock_slot_mgr.get_booked_places.return_value = 5  # Все заняты
            MockSlotManager.return_value = mock_slot_mgr

            booking, error = await manager.create_booking(
                slot_id=1, adult_user_id=5, children_count=0, total_price=5000
            )

            assert booking is None
            assert "недостаточно" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_weight_exceeded(self, manager):
        """Превышение веса."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        mock_slot.max_people = 10
        mock_slot.max_weight = 100
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.user_repo.get_by_id.return_value = MagicMock()
        manager.booking_repo.get_user_active_for_slot.return_value = None

        with patch("app.database.managers.booking_manager.SlotManager") as MockSlotManager:
            mock_slot_mgr = AsyncMock()
            mock_slot_mgr.get_booked_places.return_value = 0
            mock_slot_mgr.get_current_weight.return_value = 90
            MockSlotManager.return_value = mock_slot_mgr

            booking, error = await manager.create_booking(
                slot_id=1, adult_user_id=5, children_count=0,
                total_price=5000, total_weight=20
            )

            assert booking is None
            assert "превышение" in error.lower() or "вес" in error.lower()

    @pytest.mark.asyncio
    async def test_create_booking_success(self, manager):
        """Успешное создание бронирования."""
        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        mock_slot.max_people = 10
        mock_slot.max_weight = 1000
        manager.slot_repo.get_by_id.return_value = mock_slot
        manager.user_repo.get_by_id.return_value = MagicMock()
        manager.booking_repo.get_user_active_for_slot.return_value = None

        mock_booking = MagicMock()
        mock_booking.id = 1
        manager.booking_repo.create.return_value = mock_booking

        with patch("app.database.managers.booking_manager.SlotManager") as MockSlotManager:
            mock_slot_mgr = AsyncMock()
            mock_slot_mgr.get_booked_places.return_value = 0
            mock_slot_mgr.get_current_weight.return_value = 0
            MockSlotManager.return_value = mock_slot_mgr

            booking, error = await manager.create_booking(
                slot_id=1, adult_user_id=5, children_count=0, total_price=5000
            )

            assert booking is not None
            assert error == ""

    @pytest.mark.asyncio
    async def test_create_booking_exception(self, manager):
        """Ошибка при создании бронирования."""
        manager.slot_repo.get_by_id.side_effect = Exception("DB error")

        booking, error = await manager.create_booking(
            slot_id=1, adult_user_id=5, children_count=0, total_price=5000
        )

        assert booking is None
        assert "ошибка" in error.lower()

    # ========== mark_client_arrived ==========

    @pytest.mark.asyncio
    async def test_mark_client_arrived_success(self, manager):
        """Успешная отметка о прибытии."""
        mock_booking = MagicMock()
        mock_booking.client_status = ClientStatus.not_arrived
        manager.booking_repo.get_by_id.return_value = mock_booking

        result = await manager.mark_client_arrived(1)

        assert result is True
        assert mock_booking.client_status == ClientStatus.arrived
        manager.booking_repo.update.assert_called_once_with(mock_booking)

    @pytest.mark.asyncio
    async def test_mark_client_arrived_not_found(self, manager):
        """Бронирование не найдено."""
        manager.booking_repo.get_by_id.return_value = None

        result = await manager.mark_client_arrived(999)

        assert result is False

    # ========== get_user_active_bookings ==========

    @pytest.mark.asyncio
    async def test_get_user_active_bookings(self, manager):
        """Получение активных бронирований."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_user_active_bookings(5)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_user_active_bookings_error(self, manager):
        """Ошибка при получении активных бронирований."""
        manager.session.execute.side_effect = Exception("DB error")

        result = await manager.get_user_active_bookings(5)

        assert result == []

    # ========== get_user_history_bookings ==========

    @pytest.mark.asyncio
    async def test_get_user_history_bookings(self, manager):
        """Получение истории бронирований."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_user_history_bookings(5)

        assert len(result) == 1

    # ========== get_bookings_by_promocode ==========

    @pytest.mark.asyncio
    async def test_get_bookings_by_promocode(self, manager):
        """Получение бронирований по промокоду."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_bookings_by_promocode(10)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_bookings_by_promocode_error(self, manager):
        """Ошибка при получении бронирований по промокоду."""
        manager.session.execute.side_effect = Exception("DB error")

        result = await manager.get_bookings_by_promocode(10)

        assert result == []

    # ========== cancel_booking ==========

    @pytest.mark.asyncio
    async def test_cancel_booking_not_found(self, manager):
        """Отмена несуществующего бронирования."""
        manager.booking_repo.get_with_slot.return_value = None

        success, msg, refund = await manager.cancel_booking(999)

        assert success is False
        assert "не найдено" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_booking_already_cancelled(self, manager):
        """Бронирование уже отменено."""
        mock_booking = MagicMock()
        mock_booking.booking_status = BookingStatus.cancelled
        manager.booking_repo.get_with_slot.return_value = mock_booking

        success, msg, refund = await manager.cancel_booking(1)

        assert success is False
        assert "уже отменено" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_booking_already_completed(self, manager):
        """Нельзя отменить завершённое бронирование."""
        mock_booking = MagicMock()
        mock_booking.booking_status = BookingStatus.completed
        manager.booking_repo.get_with_slot.return_value = mock_booking

        success, msg, refund = await manager.cancel_booking(1)

        assert success is False
        assert "завершён" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_booking_success_no_refund(self, manager):
        """Успешная отмена без возврата (не оплачено)."""
        mock_booking = MagicMock()
        mock_booking.booking_status = BookingStatus.active
        mock_booking.is_paid = False
        mock_booking.total_price = 5000
        mock_booking.slot = MagicMock()
        mock_booking.slot.start_datetime = datetime.now() + timedelta(hours=5)
        manager.booking_repo.get_with_slot.return_value = mock_booking

        success, msg, refund = await manager.cancel_booking(1)

        assert success is True
        assert "отменено" in msg.lower()
        assert refund is None

    @pytest.mark.asyncio
    async def test_cancel_booking_exception(self, manager):
        """Ошибка при отмене бронирования."""
        manager.booking_repo.get_with_slot.side_effect = Exception("DB error")

        success, msg, refund = await manager.cancel_booking(1)

        assert success is False
        assert "ошибка" in msg.lower()

    # ========== get_expired_unpaid_bookings ==========

    @pytest.mark.asyncio
    async def test_get_expired_unpaid_bookings(self, manager):
        """Получение просроченных неоплаченных бронирований."""
        mock_booking = MagicMock()
        mock_booking.created_at = datetime.now() - timedelta(hours=25)
        mock_booking.slot.start_datetime = datetime.now() + timedelta(hours=2)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_expired_unpaid_bookings()

        assert len(result) == 1

    # ========== get_paid_bookings_for_reminder ==========

    @pytest.mark.asyncio
    async def test_get_paid_bookings_for_reminder(self, manager):
        """Получение оплаченных бронирований для напоминания."""
        mock_booking = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_booking]
        manager.session.execute.return_value = mock_result

        result = await manager.get_paid_bookings_for_reminder(hours_before=24)

        assert len(result) == 1

    # ========== create_booking_with_token ==========

    @pytest.mark.asyncio
    async def test_create_booking_with_token_invalid_token(self, manager):
        """Неверный токен."""
        mock_user = MagicMock()
        mock_user.verification_token = "wrong_token"
        manager.user_repo.get_by_id.return_value = mock_user

        result = await manager.create_booking_with_token(
            user_id=5, slot_id=1, token="correct_token"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_booking_with_token_not_virtual(self, manager):
        """Пользователь не виртуальный."""
        mock_user = MagicMock()
        mock_user.verification_token = "token123"
        mock_user.is_virtual = False
        manager.user_repo.get_by_id.return_value = mock_user

        result = await manager.create_booking_with_token(
            user_id=5, slot_id=1, token="token123"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_booking_with_token_slot_unavailable(self, manager):
        """Слот недоступен."""
        mock_user = MagicMock()
        mock_user.verification_token = "token123"
        mock_user.is_virtual = True
        manager.user_repo.get_by_id.return_value = mock_user
        manager.slot_repo.get_by_id.return_value = None

        result = await manager.create_booking_with_token(
            user_id=5, slot_id=1, token="token123"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_booking_with_token_success(self, manager):
        """Успешное бронирование с токеном."""
        mock_user = MagicMock()
        mock_user.verification_token = "token123"
        mock_user.is_virtual = True
        manager.user_repo.get_by_id.return_value = mock_user

        mock_slot = MagicMock()
        mock_slot.status = SlotStatus.scheduled
        manager.slot_repo.get_by_id.return_value = mock_slot

        manager.booking_repo.get_user_active_for_slot.return_value = None

        mock_booking = MagicMock()
        mock_booking.id = 1
        manager.booking_repo.create_booking_with_token.return_value = mock_booking

        result = await manager.create_booking_with_token(
            user_id=5, slot_id=1, token="token123"
        )

        assert result is not None
        assert result.id == 1

    # ========== calculate_price ==========

    @pytest.mark.asyncio
    async def test_calculate_price_slot_not_found(self, manager):
        """Слот не найден."""
        manager.slot_repo.get_with_bookings.return_value = None

        price, details = await manager.calculate_price(1, 5)

        assert price == 0
        assert details == {}

    @pytest.mark.asyncio
    async def test_calculate_price_adult_only(self, manager):
        """Только взрослый."""
        mock_slot = MagicMock()
        mock_slot.excursion.base_price = 5000
        manager.slot_repo.get_with_bookings.return_value = mock_slot

        price, details = await manager.calculate_price(1, 5)

        assert price == 5000
        assert details['base_price'] == 5000
        assert details['total'] == 5000

    # ========== get_full_info ==========

    @pytest.mark.asyncio
    async def test_get_full_info_not_found(self, manager):
        """Бронирование не найдено."""
        manager.booking_repo.get_by_id.return_value = None

        result = await manager.get_full_info(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_full_info_success(self, manager):
        """Успешное получение полной информации."""
        mock_booking = MagicMock()
        mock_booking.id = 1
        mock_booking.slot_id = 10
        mock_booking.adult_user_id = 5
        mock_booking.booking_children = []
        mock_booking.payments = []
        mock_booking.adult_user = MagicMock()
        manager.booking_repo.get_by_id.return_value = mock_booking

        mock_slot = MagicMock()
        mock_slot.excursion.base_price = 5000
        manager.slot_repo.get_with_bookings.return_value = mock_slot

        result = await manager.get_full_info(1)

        assert result is not None
        assert result['booking'] is mock_booking
        assert 'calculated_price' in result
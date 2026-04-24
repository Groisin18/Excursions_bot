"""Тесты для PaymentRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.database.repositories.payment_repository import PaymentRepository
from app.database.models import PaymentMethod, YooKassaStatus, PaymentStatus


class TestPaymentRepository:
    """Тесты для PaymentRepository."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Создать репозиторий с замоканной сессией."""
        with patch("app.database.repositories.payment_repository.BaseRepository.__init__", return_value=None):
            repo = PaymentRepository(mock_session)
            repo.session = mock_session
            repo.logger = MagicMock()
            return repo

    # ========== create_payment ==========

    @pytest.mark.asyncio
    async def test_create_payment_online(self, repo):
        """Создание онлайн-платежа."""
        mock_payment = MagicMock(spec=PaymentMethod)
        mock_payment.id = 1
        repo._create = AsyncMock(return_value=mock_payment)

        result = await repo.create_payment(
            booking_id=10,
            amount=5000,
            payment_method=PaymentMethod.online,
            yookassa_payment_id="test-yookassa-id"
        )

        assert result is mock_payment
        repo._create.assert_called_once()
        call_kwargs = repo._create.call_args[1]
        assert call_kwargs['booking_id'] == 10
        assert call_kwargs['amount'] == 5000
        assert call_kwargs['payment_method'] == PaymentMethod.online
        assert call_kwargs['yookassa_payment_id'] == "test-yookassa-id"
        assert call_kwargs['status'] == YooKassaStatus.pending

    @pytest.mark.asyncio
    async def test_create_payment_cash(self, repo):
        """Создание платежа наличными."""
        mock_payment = MagicMock()
        repo._create = AsyncMock(return_value=mock_payment)

        result = await repo.create_payment(
            booking_id=10,
            amount=5000,
            payment_method=PaymentMethod.cash
        )

        call_kwargs = repo._create.call_args[1]
        assert call_kwargs['status'] is None

    @pytest.mark.asyncio
    async def test_create_payment_error(self, repo):
        """Ошибка при создании платежа."""
        repo._create = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception, match="DB error"):
            await repo.create_payment(
                booking_id=10,
                amount=5000,
                payment_method=PaymentMethod.online
            )

    # ========== get_payment_by_id ==========

    @pytest.mark.asyncio
    async def test_get_payment_by_id_found(self, repo):
        """Получить платёж по ID — найден."""
        mock_payment = MagicMock()
        mock_payment.id = 1
        repo._get_one = AsyncMock(return_value=mock_payment)

        result = await repo.get_payment_by_id(1)

        assert result is mock_payment
        repo._get_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_payment_by_id_not_found(self, repo):
        """Получить платёж по ID — не найден."""
        repo._get_one = AsyncMock(return_value=None)

        result = await repo.get_payment_by_id(999)

        assert result is None

    # ========== get_payment_by_yookassa_id ==========

    @pytest.mark.asyncio
    async def test_get_payment_by_yookassa_id_found(self, repo):
        """Получить платёж по yookassa_id."""
        mock_payment = MagicMock()
        repo._get_one = AsyncMock(return_value=mock_payment)

        result = await repo.get_payment_by_yookassa_id("test-id")

        assert result is mock_payment

    # ========== get_payments_by_booking ==========

    @pytest.mark.asyncio
    async def test_get_payments_by_booking(self, repo):
        """Получить платежи по бронированию."""
        mock_payments = [MagicMock(), MagicMock()]
        repo._get_many = AsyncMock(return_value=mock_payments)

        result = await repo.get_payments_by_booking(10)

        assert len(result) == 2
        repo._get_many.assert_called_once()

    # ========== update_payment_by_id ==========

    @pytest.mark.asyncio
    async def test_update_payment_by_id_success(self, repo):
        """Успешное обновление платежа."""
        repo._update = AsyncMock()

        result = await repo.update_payment_by_id(
            payment_id=1,
            status=YooKassaStatus.succeeded
        )

        assert result is True
        repo._update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_payment_by_id_error(self, repo):
        """Ошибка при обновлении платежа."""
        repo._update = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.update_payment_by_id(
            payment_id=1,
            status=YooKassaStatus.succeeded
        )

        assert result is False

    # ========== update_payment_status_by_yookassa_id ==========

    @pytest.mark.asyncio
    async def test_update_payment_status_succeeded(self, repo):
        """Успешное обновление статуса с succeeded."""
        repo._update = AsyncMock(return_value=1)

        mock_payment = MagicMock()
        mock_payment.booking_id = 5
        repo.get_payment_by_yookassa_id = AsyncMock(return_value=mock_payment)

        mock_booking_repo = AsyncMock()
        mock_booking_repo.update_payment_status = AsyncMock()

        result = await repo.update_payment_status_by_yookassa_id(
            yookassa_payment_id="test-id",
            status=YooKassaStatus.succeeded,
            booking_repo=mock_booking_repo
        )

        assert result is True
        mock_booking_repo.update_payment_status.assert_called_once_with(5, PaymentStatus.paid)

    @pytest.mark.asyncio
    async def test_update_payment_status_not_succeeded(self, repo):
        """Обновление статуса не на succeeded — не обновляет бронирование."""
        repo._update = AsyncMock(return_value=1)
        repo.get_payment_by_yookassa_id = AsyncMock()

        mock_booking_repo = AsyncMock()

        result = await repo.update_payment_status_by_yookassa_id(
            yookassa_payment_id="test-id",
            status=YooKassaStatus.canceled,
            booking_repo=mock_booking_repo
        )

        assert result is True
        mock_booking_repo.update_payment_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_payment_status_not_found(self, repo):
        """Платёж не найден — false."""
        repo._update = AsyncMock(return_value=0)

        result = await repo.update_payment_status_by_yookassa_id(
            yookassa_payment_id="nonexistent",
            status=YooKassaStatus.succeeded
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_payment_status_error(self, repo):
        """Ошибка при обновлении статуса."""
        repo._update = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.update_payment_status_by_yookassa_id(
            yookassa_payment_id="test-id",
            status=YooKassaStatus.succeeded
        )

        assert result is False

    # ========== get_successful_payments_stats ==========

    @pytest.mark.asyncio
    async def test_get_successful_payments_stats(self, repo):
        """Тест статистики успешных платежей."""
        mock_row = MagicMock()
        mock_row.total_amount = 15000
        mock_row.count = 3

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        repo.session.execute.return_value = mock_result

        start = datetime(2026, 4, 1)
        end = datetime(2026, 4, 30)

        result = await repo.get_successful_payments_stats(start, end)

        assert result['total_amount'] == 15000
        assert result['count'] == 3

    # ========== get_pending_payments_by_booking ==========

    @pytest.mark.asyncio
    async def test_get_pending_payments_by_booking(self, repo):
        """Тест получения pending платежей по бронированию."""
        mock_payments = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_payments
        repo.session.execute.return_value = mock_result

        result = await repo.get_pending_payments_by_booking(10)

        assert len(result) == 1

    # ========== get_pending_payments_by_user ==========

    @pytest.mark.asyncio
    async def test_get_pending_payments_by_user(self, repo):
        """Тест получения pending платежей пользователя."""
        mock_payments = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_payments
        repo.session.execute.return_value = mock_result

        result = await repo.get_pending_payments_by_user(5)

        assert len(result) == 2
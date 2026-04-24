"""Тесты для RefundRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.database.repositories.refund_repository import RefundRepository
from app.database.models import RefundStatus


class TestRefundRepository:
    """Тесты для RefundRepository."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Создать репозиторий с замоканной сессией."""
        with patch("app.database.repositories.refund_repository.BaseRepository.__init__", return_value=None):
            repo = RefundRepository(mock_session)
            repo.session = mock_session
            repo.logger = MagicMock()
            return repo

    # ========== create_refund ==========

    @pytest.mark.asyncio
    async def test_create_refund_success(self, repo):
        """Успешное создание возврата."""
        result = await repo.create_refund(
            payment_id=10,
            booking_id=5,
            amount=5000,
            reason="Отмена пользователем"
        )

        repo.session.add.assert_called_once()
        repo.session.flush.assert_called_once()
        assert result is not None
        assert result.amount == 5000
        assert result.payment_id == 10
        assert result.booking_id == 5
        assert result.reason == "Отмена пользователем"
        assert result.status == RefundStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_refund_with_status(self, repo):
        """Создание возврата с указанным статусом."""
        result = await repo.create_refund(
            payment_id=10,
            booking_id=5,
            amount=3000,
            status=RefundStatus.PROCESSING
        )

        assert result.status == RefundStatus.PROCESSING

    # ========== get_refund_by_id ==========

    @pytest.mark.asyncio
    async def test_get_refund_by_id_found(self, repo):
        """Возврат найден."""
        mock_refund = MagicMock()
        mock_refund.id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_refund
        repo.session.execute.return_value = mock_result

        result = await repo.get_refund_by_id(1)

        assert result is mock_refund

    @pytest.mark.asyncio
    async def test_get_refund_by_id_not_found(self, repo):
        """Возврат не найден."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        repo.session.execute.return_value = mock_result

        result = await repo.get_refund_by_id(999)

        assert result is None

    # ========== get_refund_by_yookassa_id ==========

    @pytest.mark.asyncio
    async def test_get_refund_by_yookassa_id_found(self, repo):
        """Возврат найден по yookassa_id."""
        mock_refund = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_refund
        repo.session.execute.return_value = mock_result

        result = await repo.get_refund_by_yookassa_id("test-yookassa-id")

        assert result is mock_refund

    # ========== get_refunds_by_booking ==========

    @pytest.mark.asyncio
    async def test_get_refunds_by_booking(self, repo):
        """Получить возвраты по бронированию."""
        mock_refunds = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_refunds_by_booking(5)

        assert len(result) == 2

    # ========== get_refunds_by_payment ==========

    @pytest.mark.asyncio
    async def test_get_refunds_by_payment(self, repo):
        """Получить возвраты по платежу."""
        mock_refunds = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_refunds_by_payment(10)

        assert len(result) == 1

    # ========== get_refunds_by_statuses ==========

    @pytest.mark.asyncio
    async def test_get_refunds_by_statuses(self, repo):
        """Получить возвраты по нескольким статусам."""
        mock_refunds = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_refunds_by_statuses(
            [RefundStatus.PENDING, RefundStatus.PROCESSING]
        )

        assert len(result) == 3

    # ========== get_pending_refunds ==========

    @pytest.mark.asyncio
    async def test_get_pending_refunds(self, repo):
        """Получить ожидающие возвраты."""
        mock_refunds = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_pending_refunds()

        assert len(result) == 1

    # ========== get_processing_refunds ==========

    @pytest.mark.asyncio
    async def test_get_processing_refunds(self, repo):
        """Получить возвраты в обработке."""
        mock_refunds = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_processing_refunds()

        assert len(result) == 2

    # ========== get_failed_refunds ==========

    @pytest.mark.asyncio
    async def test_get_failed_refunds_all(self, repo):
        """Получить все неудачные возвраты."""
        mock_refunds = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_failed_refunds()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_failed_refunds_with_limit(self, repo):
        """Получить неудачные возвраты с лимитом."""
        mock_refunds = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_failed_refunds(limit=5)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_failed_refunds_no_limit(self, repo):
        """Получить неудачные возвраты без лимита."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        repo.session.execute.return_value = mock_result

        result = await repo.get_failed_refunds(limit=None)

        assert result == []

    # ========== update_refund_status ==========

    @pytest.mark.asyncio
    async def test_update_refund_status_success(self, repo):
        """Успешное обновление статуса."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        repo.session.execute.return_value = mock_result

        result = await repo.update_refund_status(
            refund_id=1,
            status=RefundStatus.SUCCEEDED,
            yookassa_refund_id="yookassa-123"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_refund_status_not_found(self, repo):
        """Возврат не найден для обновления."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        repo.session.execute.return_value = mock_result

        result = await repo.update_refund_status(
            refund_id=999,
            status=RefundStatus.FAILED
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_refund_status_auto_completed_at(self, repo):
        """Автоматическая установка completed_at для финальных статусов."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        repo.session.execute.return_value = mock_result

        result = await repo.update_refund_status(
            refund_id=1,
            status=RefundStatus.CANCELED
        )

        assert result is True
        call_kwargs = repo.session.execute.call_args[0][0]
        # Проверяем что completed_at присутствует в values
        compiled = str(call_kwargs)
        assert "completed_at" in compiled.lower()

    @pytest.mark.asyncio
    async def test_update_refund_status_with_cancellation_details(self, repo):
        """Обновление с деталями отмены."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        repo.session.execute.return_value = mock_result

        result = await repo.update_refund_status(
            refund_id=1,
            status=RefundStatus.CANCELED,
            cancellation_party="yookassa",
            cancellation_reason="expired"
        )

        assert result is True

    # ========== increment_retry_count ==========

    @pytest.mark.asyncio
    async def test_increment_retry_count_success(self, repo):
        """Увеличение счётчика попыток."""
        mock_refund = MagicMock()
        mock_refund.retry_count = 2
        repo.get_refund_by_id = AsyncMock(return_value=mock_refund)

        result = await repo.increment_retry_count(1)

        assert result == 3
        assert mock_refund.retry_count == 3
        repo.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_retry_count_not_found(self, repo):
        """Возврат не найден — возвращает 0."""
        repo.get_refund_by_id = AsyncMock(return_value=None)

        result = await repo.increment_retry_count(999)

        assert result == 0

    # ========== get_refunds_for_retry ==========

    @pytest.mark.asyncio
    async def test_get_refunds_for_retry(self, repo):
        """Получить возвраты для повторной обработки."""
        mock_refunds = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_refunds
        repo.session.execute.return_value = mock_result

        result = await repo.get_refunds_for_retry(max_retries=3)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_refunds_for_retry_empty(self, repo):
        """Нет возвратов для повторной обработки."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        repo.session.execute.return_value = mock_result

        result = await repo.get_refunds_for_retry()

        assert result == []
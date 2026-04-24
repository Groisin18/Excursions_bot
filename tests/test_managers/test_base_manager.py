"""Тесты для BaseManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.managers.base import BaseManager


class TestBaseManager:
    """Тесты для BaseManager."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканной сессией."""
        with patch("app.database.managers.base.get_logger", return_value=MagicMock()):
            manager = BaseManager(mock_session)
            manager.logger = MagicMock()
            return manager

    # ========== __init__ ==========

    def test_init(self, manager, mock_session):
        """Инициализация менеджера."""
        assert manager.session is mock_session
        assert manager.logger is not None

    # ========== _commit ==========

    @pytest.mark.asyncio
    async def test_commit_success(self, manager):
        """Успешный коммит."""
        await manager._commit()

        manager.session.commit.assert_called_once()
        manager.logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back(self, manager):
        """Ошибка коммита — вызывает rollback и пробрасывает исключение."""
        manager.session.commit.side_effect = Exception("Commit error")

        with pytest.raises(Exception, match="Commit error"):
            await manager._commit()

        manager.session.rollback.assert_called_once()
        manager.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_commit_failure_rollback_also_fails(self, manager):
        """Ошибка коммита и rollback тоже падает — пробрасывает исключение rollback."""
        manager.session.commit.side_effect = Exception("Commit error")
        manager.session.rollback.side_effect = Exception("Rollback error")

        with pytest.raises(Exception, match="Rollback error"):
            await manager._commit()

    # ========== _rollback ==========

    @pytest.mark.asyncio
    async def test_rollback_success(self, manager):
        """Успешный откат."""
        await manager._rollback()

        manager.session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_failure(self, manager):
        """Ошибка при откате — пробрасывает исключение."""
        manager.session.rollback.side_effect = Exception("Rollback error")

        with pytest.raises(Exception, match="Rollback error"):
            await manager._rollback()

    # ========== _refresh ==========

    @pytest.mark.asyncio
    async def test_refresh_success(self, manager):
        """Успешное обновление объекта."""
        mock_entity = MagicMock()
        mock_entity.__class__.__name__ = "TestEntity"

        await manager._refresh(mock_entity)

        manager.session.refresh.assert_called_once_with(mock_entity)

    @pytest.mark.asyncio
    async def test_refresh_failure_not_raised(self, manager):
        """Ошибка обновления — не пробрасывается (не критично)."""
        manager.session.refresh.side_effect = Exception("Refresh error")

        # Не должно вызывать исключение
        await manager._refresh(MagicMock())

        manager.logger.error.assert_called_once()

    # ========== _execute_in_transaction ==========

    @pytest.mark.asyncio
    async def test_execute_in_transaction_success(self, manager):
        """Успешное выполнение в транзакции."""
        mock_operation = AsyncMock(return_value="result")

        result = await manager._execute_in_transaction(mock_operation, "arg1", kw="arg2")

        assert result == "result"
        mock_operation.assert_called_once_with("arg1", kw="arg2")
        manager.session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_in_transaction_failure_rolls_back(self, manager):
        """Ошибка в операции — вызывает rollback и пробрасывает исключение."""
        mock_operation = AsyncMock(side_effect=Exception("Operation error"))

        with pytest.raises(Exception, match="Operation error"):
            await manager._execute_in_transaction(mock_operation)

        manager.session.rollback.assert_called_once()
        manager.session.commit.assert_not_called()

    # ========== _log_operation_start ==========

    def test_log_operation_start(self, manager):
        """Логирование начала операции."""
        manager._log_operation_start(
            "test_operation",
            user_id=5,
            booking_id=10
        )

        manager.logger.info.assert_called_once()
        call_args = manager.logger.info.call_args[0][0]
        assert "test_operation" in call_args
        assert "user_id=5" in call_args
        assert "booking_id=10" in call_args

    def test_log_operation_start_no_context(self, manager):
        """Логирование начала операции без контекста."""
        manager._log_operation_start("simple_operation")

        manager.logger.info.assert_called_once()
        call_args = manager.logger.info.call_args[0][0]
        assert "simple_operation" in call_args

    # ========== _log_operation_end ==========

    def test_log_operation_end_success(self, manager):
        """Логирование успешного завершения."""
        manager._log_operation_end(
            "test_operation",
            success=True,
            user_id=5
        )

        manager.logger.info.assert_called_once()
        call_args = manager.logger.info.call_args[0][0]
        assert "успешно" in call_args
        assert "user_id" in call_args
        assert "5" in call_args

    def test_log_operation_end_failure(self, manager):
        """Логирование завершения с ошибкой."""
        manager._log_operation_end(
            "test_operation",
            success=False
        )

        call_args = manager.logger.info.call_args[0][0]
        assert "с ошибкой" in call_args

    def test_log_operation_end_no_result(self, manager):
        """Логирование без результата."""
        manager._log_operation_end("simple_operation")

        call_args = manager.logger.info.call_args[0][0]
        assert "результат" not in call_args

    # ========== _log_business_event ==========

    def test_log_business_event(self, manager):
        """Логирование бизнес-события."""
        manager._log_business_event(
            "booking_cancelled",
            booking_id=10,
            reason="no_payment"
        )

        manager.logger.info.assert_called_once()
        call_args = manager.logger.info.call_args[0][0]
        assert "booking_cancelled" in call_args
        assert "booking_id=10" in call_args
        assert "reason=no_payment" in call_args
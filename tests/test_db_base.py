"""Тесты для базовых классов."""

import pytest
from unittest.mock import AsyncMock

from app.database.base import BaseRepository, BaseManager


class TestBaseRepository:
    """Тесты для BaseRepository."""

    def test_init(self):
        """Тест инициализации BaseRepository."""
        mock_session = AsyncMock()
        repo = BaseRepository(mock_session)

        assert repo.session is mock_session
        assert repo.logger is not None
        # Проверяем, что имя логгера содержит имя класса
        assert "BaseRepository" in repo.logger.name

    def test_init_with_subclass(self):
        """Тест что подклассы получают правильное имя логгера."""
        mock_session = AsyncMock()

        class TestRepo(BaseRepository):
            pass

        repo = TestRepo(mock_session)
        assert "TestRepo" in repo.logger.name

    def test_session_is_accessible(self):
        """Тест что сессия доступна для использования."""
        mock_session = AsyncMock()
        repo = BaseRepository(mock_session)

        # Сессия должна быть тем же объектом
        assert repo.session is mock_session


class TestBaseManager:
    """Тесты для BaseManager."""

    def test_init(self):
        """Тест инициализации BaseManager."""
        mock_session = AsyncMock()
        manager = BaseManager(mock_session)

        assert manager.session is mock_session
        assert manager.logger is not None
        assert "BaseManager" in manager.logger.name

    def test_init_with_subclass(self):
        """Тест что подклассы получают правильное имя логгера."""
        mock_session = AsyncMock()

        class TestManager(BaseManager):
            pass

        manager = TestManager(mock_session)
        assert "TestManager" in manager.logger.name

    def test_session_is_accessible(self):
        """Тест что сессия доступна для использования."""
        mock_session = AsyncMock()
        manager = BaseManager(mock_session)

        assert manager.session is mock_session
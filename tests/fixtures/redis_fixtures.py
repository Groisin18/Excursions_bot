"""Фикстуры для Redis."""

import pytest
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager


class MockRedisClient:
    """Полноценный мок для Redis клиента."""

    def __init__(self):
        self.is_locked = AsyncMock(return_value=False)
        # Важно! Добавляем _redis для имитации инициализации
        self._redis = AsyncMock()

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 30, blocking_timeout: int = 10):
        """Мок для контекстного менеджера блокировки."""
        # Просто возвращаем контекст, не делаем никаких проверок
        yield self

    async def acquire_lock(self, key: str, timeout: int = 30, token: str = None):
        """Мок для acquire_lock."""
        return token or "mock-token"

    async def release_lock(self, key: str, token: str):
        """Мок для release_lock."""
        return True

    async def initialize(self):
        """Мок для initialize."""
        pass


@pytest.fixture
def mock_redis_client():
    """Мок для Redis клиента."""
    return MockRedisClient()


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch, mock_redis_client):
    """Автоматически подменяет реальный Redis на mock во всех тестах."""
    # Патчим redis_client в модулях, где он точно используется
    modules_to_patch = [
        "app.services.scheduler.tasks.redis_client",
        "app.services.redis.client.redis_client",
    ]

    for module_path in modules_to_patch:
        try:
            monkeypatch.setattr(module_path, mock_redis_client)
        except AttributeError:
            pass  # Модуль ещё не импортирован — ок, пропускаем

    return mock_redis_client
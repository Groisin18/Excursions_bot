"""Фикстуры специфичные для тестов роутеров."""

import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def fake_message():
    """Локальная фикстура для создания message в тестах роутеров."""
    return AsyncMock()
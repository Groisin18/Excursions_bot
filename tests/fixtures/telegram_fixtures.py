"""Фикстуры для Telegram объектов."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def telegram_message_mock():
    """Мок для сообщения Telegram."""
    message = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 123456
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.from_user.username = "test_user"
    message.chat = MagicMock()
    message.chat.id = 123456
    message.text = "test message"
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_state():
    """Мок для FSMContext."""
    state = AsyncMock()
    state.set_state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    return state


@pytest.fixture
def mock_callback_query(telegram_message_mock):
    """Мок для callback-запроса."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = 123456
    callback.message = telegram_message_mock
    callback.data = "test_callback"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def fake_message():
    """Фикстура для создания message в тестах."""
    return AsyncMock()
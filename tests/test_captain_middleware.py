"""Тесты для captain middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, CallbackQuery

from app.middlewares.captain_middleware import (
    is_user_captain,
    CaptainMiddleware
)
from app.database.models import UserRole


# ========== ТЕСТЫ ДЛЯ is_user_captain ==========

class TestIsUserCaptain:
    """Тесты для функции is_user_captain."""

    @pytest.fixture
    def mock_user_captain(self):
        """Мок пользователя-капитана."""
        user = MagicMock()
        user.role = UserRole.captain
        return user

    @pytest.fixture
    def mock_user_client(self):
        """Мок пользователя-клиента."""
        user = MagicMock()
        user.role = UserRole.client
        return user

    @pytest.fixture
    def mock_user_admin(self):
        """Мок пользователя-админа."""
        user = MagicMock()
        user.role = UserRole.admin
        return user

    @pytest.mark.asyncio
    async def test_captain_returns_true(self, mock_user_captain):
        """Капитан должен возвращать True."""
        mock_repo = AsyncMock()
        mock_repo.get_by_telegram_id.return_value = mock_user_captain

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("app.middlewares.captain_middleware.async_session", return_value=mock_session):
            with patch("app.middlewares.captain_middleware.UserRepository", return_value=mock_repo):
                result = await is_user_captain(123456)

        assert result is True
        mock_repo.get_by_telegram_id.assert_called_once_with(123456)

    @pytest.mark.asyncio
    async def test_client_returns_false(self, mock_user_client):
        """Клиент должен возвращать False."""
        mock_repo = AsyncMock()
        mock_repo.get_by_telegram_id.return_value = mock_user_client

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("app.middlewares.captain_middleware.async_session", return_value=mock_session):
            with patch("app.middlewares.captain_middleware.UserRepository", return_value=mock_repo):
                result = await is_user_captain(123456)

        assert result is False

    @pytest.mark.asyncio
    async def test_admin_returns_false(self, mock_user_admin):
        """Админ должен возвращать False (если он не капитан)."""
        mock_repo = AsyncMock()
        mock_repo.get_by_telegram_id.return_value = mock_user_admin

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("app.middlewares.captain_middleware.async_session", return_value=mock_session):
            with patch("app.middlewares.captain_middleware.UserRepository", return_value=mock_repo):
                result = await is_user_captain(123456)

        assert result is False

    @pytest.mark.asyncio
    async def test_user_not_found_returns_false(self):
        """Несуществующий пользователь возвращает False."""
        mock_repo = AsyncMock()
        mock_repo.get_by_telegram_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("app.middlewares.captain_middleware.async_session", return_value=mock_session):
            with patch("app.middlewares.captain_middleware.UserRepository", return_value=mock_repo):
                result = await is_user_captain(999999)

        assert result is False

    @pytest.mark.asyncio
    async def test_db_error_returns_false(self):
        """Ошибка БД должна возвращать False."""
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("app.middlewares.captain_middleware.async_session", return_value=mock_session):
            with patch("app.middlewares.captain_middleware.UserRepository", side_effect=Exception("DB error")):
                result = await is_user_captain(123456)

        assert result is False


# ========== ТЕСТЫ ДЛЯ CaptainMiddleware ==========

class TestCaptainMiddleware:
    """Тесты для класса CaptainMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Создать экземпляр мидлвари."""
        return CaptainMiddleware()

    @pytest.fixture
    def mock_handler(self):
        """Мок для хендлера."""
        handler = AsyncMock()
        handler.return_value = "handler_result"
        return handler

    @pytest.fixture
    def mock_message(self):
        """Мок для сообщения."""
        msg = AsyncMock(spec=Message)
        msg.from_user = MagicMock()
        msg.from_user.id = 123456
        msg.answer = AsyncMock()
        return msg

    @pytest.fixture
    def mock_callback(self):
        """Мок для callback query."""
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = MagicMock()
        cb.from_user.id = 123456
        cb.answer = AsyncMock()
        return cb

    @pytest.fixture
    def mock_data(self):
        """Мок для data."""
        return {"raw_state": None}

    @pytest.mark.asyncio
    async def test_captain_passes_through_message(self, middleware, mock_handler, mock_message, mock_data):
        """Капитан должен проходить мидлварь для сообщений."""
        with patch("app.middlewares.captain_middleware.is_user_captain", return_value=True):
            result = await middleware(mock_handler, mock_message, mock_data)

        assert result == "handler_result"
        mock_handler.assert_called_once_with(mock_message, mock_data)
        mock_message.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_captain_passes_through_callback(self, middleware, mock_handler, mock_callback, mock_data):
        """Капитан должен проходить мидлварь для callback-запросов."""
        with patch("app.middlewares.captain_middleware.is_user_captain", return_value=True):
            result = await middleware(mock_handler, mock_callback, mock_data)

        assert result == "handler_result"
        mock_handler.assert_called_once_with(mock_callback, mock_data)
        mock_callback.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_captain_blocked_message(self, middleware, mock_handler, mock_message, mock_data):
        """Не-капитан должен быть заблокирован для сообщений."""
        with patch("app.middlewares.captain_middleware.is_user_captain", return_value=False):
            result = await middleware(mock_handler, mock_message, mock_data)

        assert result is None
        mock_handler.assert_not_called()
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "нет прав" in call_args.lower()

    @pytest.mark.asyncio
    async def test_non_captain_blocked_callback(self, middleware, mock_handler, mock_callback, mock_data):
        """Не-капитан должен быть заблокирован для callback-запросов."""
        with patch("app.middlewares.captain_middleware.is_user_captain", return_value=False):
            result = await middleware(mock_handler, mock_callback, mock_data)

        assert result is None
        mock_handler.assert_not_called()
        mock_callback.answer.assert_called_once()
        call_kwargs = mock_callback.answer.call_args[1]
        assert call_kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_is_user_captain_exception_message(self, middleware, mock_handler, mock_message, mock_data):
        """Ошибка в is_user_captain должна блокировать доступ (сообщение)."""
        with patch("app.middlewares.captain_middleware.is_user_captain", side_effect=Exception("Test error")):
            result = await middleware(mock_handler, mock_message, mock_data)

        assert result is None
        mock_handler.assert_not_called()
        mock_message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_user_captain_exception_callback(self, middleware, mock_handler, mock_callback, mock_data):
        """Ошибка в is_user_captain должна блокировать доступ (callback)."""
        with patch("app.middlewares.captain_middleware.is_user_captain", side_effect=Exception("Test error")):
            result = await middleware(mock_handler, mock_callback, mock_data)

        assert result is None
        mock_handler.assert_not_called()
        mock_callback.answer.assert_called_once()
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import User, Chat, Message, CallbackQuery
from datetime import datetime

from app.middlewares.admin_middleware import AdminMiddleware, is_user_admin
from app.database.models import UserRole


# ==================== Фикстуры ====================
@pytest.fixture
def middleware():
    """Фикстура для middleware."""
    return AdminMiddleware()


# ==================== Тесты для is_user_admin ====================
class TestIsUserAdmin:
    """Тесты для функции проверки прав администратора."""

    @pytest.mark.asyncio
    async def test_is_user_admin_true(self):
        """Тест, когда пользователь является администратором."""
        telegram_id = 123456

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                mock_user = AsyncMock()
                mock_user.role = UserRole.admin
                mock_user.full_name = "Admin User"
                mock_db.get_user_by_telegram_id.return_value = mock_user
                MockDBManager.return_value = mock_db

                result = await is_user_admin(telegram_id)

                assert result is True
                mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)

    @pytest.mark.asyncio
    async def test_is_user_admin_false_client(self):
        """Тест, когда пользователь является клиентом."""
        telegram_id = 654321

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                mock_user = AsyncMock()
                mock_user.role = UserRole.client
                mock_user.full_name = "Client User"
                mock_db.get_user_by_telegram_id.return_value = mock_user
                MockDBManager.return_value = mock_db

                result = await is_user_admin(telegram_id)

                assert result is False
                mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)

    @pytest.mark.asyncio
    async def test_is_user_admin_false_captain(self):
        """Тест, когда пользователь является капитаном."""
        telegram_id = 789012

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                mock_user = AsyncMock()
                mock_user.role = UserRole.captain
                mock_user.full_name = "Captain User"
                mock_db.get_user_by_telegram_id.return_value = mock_user
                MockDBManager.return_value = mock_db

                result = await is_user_admin(telegram_id)

                assert result is False
                mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)

    @pytest.mark.asyncio
    async def test_is_user_admin_user_not_found(self):
        """Тест, когда пользователь не найден."""
        telegram_id = 999999

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                # Возвращаем None - пользователь не найден
                mock_db.get_user_by_telegram_id.return_value = None
                MockDBManager.return_value = mock_db

                result = await is_user_admin(telegram_id)

                # После исправления middleware должен возвращать False
                assert result is False
                mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)

    @pytest.mark.asyncio
    async def test_is_user_admin_database_error(self):
        """Тест обработки ошибки базы данных."""
        telegram_id = 111111

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                mock_db.get_user_by_telegram_id.side_effect = Exception("DB Connection Error")
                MockDBManager.return_value = mock_db

                result = await is_user_admin(telegram_id)

                assert result is False
                mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)

    @pytest.mark.asyncio
    async def test_is_user_admin_session_error(self):
        """Тест ошибки при создании сессии."""
        telegram_id = 222222

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            mock_session.return_value.__aenter__.side_effect = Exception("Session Creation Error")

            result = await is_user_admin(telegram_id)

            assert result is False


# ==================== Тесты для AdminMiddleware ====================
class TestAdminMiddleware:
    """Тесты для middleware проверки администраторов."""

    @pytest.fixture
    def admin_user(self):
        """Фикстура для пользователя-администратора."""
        user = AsyncMock(spec=User)
        user.id = 123456
        user.username = "admin_user"
        user.first_name = "Admin"
        user.last_name = "User"
        return user

    @pytest.fixture
    def regular_user(self):
        """Фикстура для обычного пользователя."""
        user = AsyncMock(spec=User)
        user.id = 654321
        user.username = "regular_user"
        user.first_name = "Regular"
        user.last_name = "User"
        return user

    @pytest.fixture
    def chat(self):
        """Фикстура для чата."""
        chat = AsyncMock(spec=Chat)
        chat.id = 123456
        chat.type = "private"
        return chat

    @pytest.fixture
    def admin_message(self, admin_user, chat):
        """Фикстура для сообщения от администратора."""
        message = AsyncMock(spec=Message)
        message.from_user = admin_user
        message.chat = chat
        message.text = "/admin_command"
        message.date = datetime.now()
        message.message_id = 1
        message.answer = AsyncMock()
        return message

    @pytest.fixture
    def regular_message(self, regular_user, chat):
        """Фикстура для сообщения от обычного пользователя."""
        message = AsyncMock(spec=Message)
        message.from_user = regular_user
        message.chat = chat
        message.text = "/some_command"
        message.date = datetime.now()
        message.message_id = 2
        message.answer = AsyncMock()
        return message

    @pytest.fixture
    def admin_callback_query(self, admin_user, admin_message):
        """Фикстура для callback запроса от администратора."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = admin_user
        callback.message = admin_message
        callback.data = "admin_action"
        callback.id = "callback_123"
        callback.answer = AsyncMock()
        return callback

    @pytest.fixture
    def regular_callback_query(self, regular_user, regular_message):
        """Фикстура для callback запроса от обычного пользователя."""
        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = regular_user
        callback.message = regular_message
        callback.data = "user_action"
        callback.id = "callback_456"
        callback.answer = AsyncMock()
        return callback

    @pytest.mark.asyncio
    async def test_admin_access_granted_message(self, middleware, admin_message):
        """Тест доступа для администратора (сообщение)."""
        handler = AsyncMock()
        handler.return_value = "handler_result"

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = True

            result = await middleware.__call__(handler, admin_message, {})

            assert mock_is_admin.called
            mock_is_admin.assert_called_once_with(admin_message.from_user.id)

            assert handler.called
            handler.assert_called_once_with(admin_message, {})

            assert result == "handler_result"
            # Не должно быть ответного сообщения
            assert not admin_message.answer.called

    @pytest.mark.asyncio
    async def test_admin_access_granted_callback(self, middleware, admin_callback_query):
        """Тест доступа для администратора (callback)."""
        handler = AsyncMock()
        handler.return_value = "handler_result"

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = True

            result = await middleware.__call__(handler, admin_callback_query, {})

            mock_is_admin.assert_called_once_with(admin_callback_query.from_user.id)
            handler.assert_called_once_with(admin_callback_query, {})
            assert result == "handler_result"
            # Не должно быть ответа на callback
            assert not admin_callback_query.answer.called

    @pytest.mark.asyncio
    async def test_admin_access_denied_message(self, middleware, regular_message):
        """Тест отказа в доступе для обычного пользователя (сообщение)."""
        handler = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = False

            # Мокаем клавиатуру
            mock_keyboard = MagicMock()
            with patch('app.middlewares.admin_middleware.main_kb', mock_keyboard):
                result = await middleware.__call__(handler, regular_message, {})

                mock_is_admin.assert_called_once_with(regular_message.from_user.id)

                # Handler не должен быть вызван
                assert not handler.called

                # Должно быть отправлено сообщение с клавиатурой
                assert regular_message.answer.called

                # Проверяем аргументы вызова
                regular_message.answer.assert_called_once_with(
                    "У вас нет прав доступа к админ-панели",
                    reply_markup=mock_keyboard
                )

                # Результат должен быть None
                assert result is None

    @pytest.mark.asyncio
    async def test_admin_access_denied_callback(self, middleware, regular_callback_query):
        """Тест отказа в доступе для обычного пользователя (callback)."""
        handler = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = False

            result = await middleware.__call__(handler, regular_callback_query, {})

            mock_is_admin.assert_called_once_with(regular_callback_query.from_user.id)

            # Handler не должен быть вызван
            assert not handler.called

            # Должен быть ответ на callback
            assert regular_callback_query.answer.called
            regular_callback_query.answer.assert_called_once_with(
                "У вас нет прав доступа",
                show_alert=True
            )

            # Результат должен быть None
            assert result is None

    @pytest.mark.asyncio
    async def test_middleware_with_data(self, middleware, admin_message):
        """Тест middleware с дополнительными данными."""
        handler = AsyncMock()
        data = {
            'state': 'some_state',
            'key': 'value'
        }

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = True

            await middleware.__call__(handler, admin_message, data)

            handler.assert_called_once_with(admin_message, data)
            # Данные не должны быть изменены
            assert data == {'state': 'some_state', 'key': 'value'}

    @pytest.mark.asyncio
    async def test_middleware_error_in_is_user_admin(self, middleware, admin_message):
        """Тест ошибки в функции is_user_admin."""
        handler = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.side_effect = Exception("Unexpected error")

            # Мокаем клавиатуру
            mock_keyboard = MagicMock()
            with patch('app.middlewares.admin_middleware.main_kb', mock_keyboard):
                # Middleware должен ловить исключение
                result = await middleware.__call__(handler, admin_message, {})

                # При ошибке доступ должен быть запрещен
                assert not handler.called
                assert admin_message.answer.called
                assert result is None


# ==================== Параметризованные тесты ====================
@pytest.mark.parametrize("is_admin,expected_handler_called", [
    (True, True),   # Админ - handler вызывается
    (False, False), # Не админ - handler не вызывается
])
@pytest.mark.asyncio
async def test_middleware_admin_check(is_admin, expected_handler_called):
    """Параметризованный тест проверки администратора."""
    # Создаем middleware внутри теста
    middleware = AdminMiddleware()
    handler = AsyncMock()

    # Создаем mock пользователя и сообщения
    user = AsyncMock(spec=User)
    user.id = 123456

    message = AsyncMock(spec=Message)
    message.from_user = user
    message.answer = AsyncMock()

    with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
        mock_is_admin.return_value = is_admin

        # Мокаем клавиатуру
        mock_keyboard = MagicMock()
        with patch('app.middlewares.admin_middleware.main_kb', mock_keyboard):
            result = await middleware.__call__(handler, message, {})

            assert handler.called == expected_handler_called
            mock_is_admin.assert_called_once_with(user.id)


# ==================== Тесты типов событий ====================
class TestEventTypes:
    """Тесты для разных типов событий."""

    @pytest.mark.asyncio
    async def test_message_event(self):
        """Тест обработки события типа Message."""
        middleware = AdminMiddleware()
        handler = AsyncMock()
        user = AsyncMock(spec=User)
        user.id = 123456

        message = AsyncMock(spec=Message)
        message.from_user = user
        message.answer = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = True

            await middleware.__call__(handler, message, {})

            assert isinstance(message, Message)
            mock_is_admin.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_callback_query_event(self):
        """Тест обработки события типа CallbackQuery."""
        middleware = AdminMiddleware()
        handler = AsyncMock()
        user = AsyncMock(spec=User)
        user.id = 123456

        callback = AsyncMock(spec=CallbackQuery)
        callback.from_user = user
        callback.answer = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = True

            await middleware.__call__(handler, callback, {})

            assert isinstance(callback, CallbackQuery)
            mock_is_admin.assert_called_once_with(user.id)


# ==================== Тесты логирования ====================
class TestLogging:
    """Тесты для логирования в middleware."""

    @pytest.fixture
    def regular_user(self):
        user = AsyncMock(spec=User)
        user.id = 654321
        return user

    @pytest.fixture
    def regular_message(self, regular_user):
        message = AsyncMock(spec=Message)
        message.from_user = regular_user
        message.answer = AsyncMock()
        return message

    @pytest.mark.asyncio
    async def test_logging_access_denied(self, regular_message):
        """Тест логирования при отказе в доступе."""
        middleware = AdminMiddleware()
        handler = AsyncMock()

        with patch('app.middlewares.admin_middleware.is_user_admin') as mock_is_admin:
            mock_is_admin.return_value = False

            with patch('app.middlewares.admin_middleware.logger') as mock_logger:
                mock_logger.warning = MagicMock()

                # Мокаем клавиатуру
                mock_keyboard = MagicMock()
                with patch('app.middlewares.admin_middleware.main_kb', mock_keyboard):
                    await middleware.__call__(handler, regular_message, {})

                    # Проверяем, что было залогировано предупреждение
                    assert mock_logger.warning.called
                    warning_call = mock_logger.warning.call_args[0][0]
                    assert "Попытка доступа к админ-панели без прав" in warning_call
                    assert str(regular_message.from_user.id) in warning_call

    @pytest.mark.asyncio
    async def test_logging_in_is_user_admin(self):
        """Тест логирования в функции is_user_admin."""
        telegram_id = 123456

        with patch('app.middlewares.admin_middleware.async_session') as mock_session:
            session_mock = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_mock

            with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
                mock_db = AsyncMock()
                mock_user = AsyncMock()
                mock_user.role = UserRole.admin
                mock_user.full_name = "Admin User"
                mock_db.get_user_by_telegram_id.return_value = mock_user
                MockDBManager.return_value = mock_db

                with patch('app.middlewares.admin_middleware.logger') as mock_logger:
                    mock_logger.debug = MagicMock()
                    mock_logger.error = MagicMock()

                    result = await is_user_admin(telegram_id)

                    # Проверяем debug логи
                    assert mock_logger.debug.called
                    debug_calls = mock_logger.debug.call_args_list

                    # Должно быть минимум 1 debug вызов
                    assert len(debug_calls) >= 1

                    # Первый вызов - начало проверки
                    first_call = debug_calls[0][0][0]
                    assert f"Проверка прав администратора для пользователя {telegram_id}" in first_call


# ==================== Упрощенный тест для is_user_admin ====================
@pytest.mark.asyncio
async def test_is_user_admin_simple():
    """Упрощенный тест для is_user_admin."""
    # Проверяем что функция вообще работает
    telegram_id = 123456

    with patch('app.middlewares.admin_middleware.async_session') as mock_session:
        session_mock = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_mock

        with patch('app.middlewares.admin_middleware.DatabaseManager') as MockDBManager:
            mock_db = AsyncMock()
            mock_user = AsyncMock()
            mock_user.role = UserRole.admin
            mock_db.get_user_by_telegram_id.return_value = mock_user
            MockDBManager.return_value = mock_db

            result = await is_user_admin(telegram_id)

            # Проверяем что функция что-то возвращает
            assert result is not None
            assert result is True
            mock_db.get_user_by_telegram_id.assert_called_once_with(telegram_id)


if __name__ == "__main__":
    """Запуск тестов напрямую."""
    pytest.main([__file__, "-v"])
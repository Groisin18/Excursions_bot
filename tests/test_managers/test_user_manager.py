"""Тесты для UserManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from app.database.managers.user_manager import UserManager
from app.database.models import UserRole, RegistrationType
from app.schemas.user import UserRegistrationData, ChildRegistrationData


class TestUserManager:
    """Тесты для UserManager."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканными зависимостями."""
        with patch("app.database.managers.user_manager.BaseManager.__init__", return_value=None):
            manager = UserManager(mock_session)
            manager.session = mock_session
            manager.logger = MagicMock()
            manager.user_repo = AsyncMock()
            return manager

    # ========== _create_user_internal ==========

    @pytest.mark.asyncio
    async def test_create_user_internal_success(self, manager):
        """Успешное создание пользователя."""
        mock_user = MagicMock()
        mock_user.id = 1
        manager.user_repo.create.return_value = mock_user

        user = await manager._create_user_internal(
            telegram_id=123,
            full_name="Иван Иванов",
            role=UserRole.client,
            phone_number="+71234567890"
        )

        assert user is mock_user
        manager.user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_internal_with_token(self, manager):
        """Создание пользователя с токеном."""
        mock_user = MagicMock()
        manager.user_repo.create.return_value = mock_user

        user = await manager._create_user_internal(
            telegram_id=None,
            full_name="Ребёнок",
            role=UserRole.client,
            verification_token="abc123",
            is_virtual=True,
            registration_type=RegistrationType.PARENT
        )

        call_kwargs = manager.user_repo.create.call_args[1]
        assert call_kwargs['verification_token'] == "abc123"
        assert call_kwargs['is_virtual'] is True
        assert call_kwargs['token_created_at'] is not None

    @pytest.mark.asyncio
    async def test_create_user_internal_error(self, manager):
        """Ошибка при создании пользователя."""
        manager.user_repo.create.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await manager._create_user_internal(
                telegram_id=123,
                full_name="Иван",
                role=UserRole.client
            )

    # ========== create_adult_user ==========

    @pytest.mark.asyncio
    async def test_create_adult_user_success(self, manager):
        """Успешная регистрация взрослого."""
        mock_user = MagicMock()
        mock_user.id = 1
        manager._create_user_internal = AsyncMock(return_value=mock_user)

        user_data = UserRegistrationData(
            name="Иван", surname="Иванов", phone="+71234567890",
            date_of_birth=date(1990, 5, 15), email="ivan@mail.ru",
            address="г. Москва", weight=80, age=35
        )

        user = await manager.create_adult_user(123456, user_data)

        assert user is mock_user
        manager._create_user_internal.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_adult_user_error(self, manager):
        """Ошибка при регистрации."""
        manager._create_user_internal = AsyncMock(side_effect=Exception("Error"))

        user_data = UserRegistrationData(
            name="Иван", surname="Иванов", phone="+71234567890",
            date_of_birth=date(1990, 5, 15), email="ivan@mail.ru",
            address="г. Москва", weight=80, age=35
        )

        with pytest.raises(Exception):
            await manager.create_adult_user(123456, user_data)

    # ========== create_user_by_admin ==========

    @pytest.mark.asyncio
    async def test_create_user_by_admin_phone_exists(self, manager):
        """Телефон уже зарегистрирован."""
        manager.user_repo.get_by_phone.return_value = MagicMock()

        with pytest.raises(ValueError, match="уже зарегистрирован"):
            await manager.create_user_by_admin(
                full_name="Иван", phone_number="+71234567890", admin_id=1
            )

    @pytest.mark.asyncio
    async def test_create_user_by_admin_success(self, manager):
        """Успешное создание админом."""
        manager.user_repo.get_by_phone.return_value = None
        mock_user = MagicMock()
        mock_user.id = 1
        manager._create_virtual_user = AsyncMock(return_value=(mock_user, "token123"))
        manager._refresh = AsyncMock()

        user, token = await manager.create_user_by_admin(
            full_name="Иван", phone_number="+71234567890", admin_id=1,
            address="г. Москва"
        )

        assert user is mock_user
        assert token == "token123"
        manager.user_repo.update.assert_called_once()

    # ========== create_child_user ==========

    @pytest.mark.asyncio
    async def test_create_child_user_parent_not_found(self, manager):
        """Родитель не найден."""
        manager.user_repo.get_by_telegram_id.return_value = None

        child_data = ChildRegistrationData(
            name="Ребёнок", surname="Иванов", date_of_birth=date(2021, 5, 10),
            age=5, weight=20, address="г. Москва", parent_id=1
        )

        with pytest.raises(ValueError, match="не найден"):
            await manager.create_child_user(child_data, 123456)

    @pytest.mark.asyncio
    async def test_create_child_user_too_many_children(self, manager):
        """Лимит детей превышен."""
        parent = MagicMock()
        parent.id = 1
        parent.full_name = "Иван"
        manager.user_repo.get_by_telegram_id.return_value = parent
        manager.user_repo.get_children_users.return_value = [MagicMock() for _ in range(7)]

        child_data = ChildRegistrationData(
            name="Ребёнок", surname="Иванов", date_of_birth=date(2021, 5, 10),
            age=5, weight=20, address="г. Москва", parent_id=1
        )

        with pytest.raises(ValueError, match="лимит"):
            await manager.create_child_user(child_data, 123456)

    @pytest.mark.asyncio
    async def test_create_child_user_success(self, manager):
        """Успешное создание ребёнка."""
        parent = MagicMock()
        parent.id = 1
        parent.full_name = "Иван"
        manager.user_repo.get_by_telegram_id.return_value = parent
        manager.user_repo.get_children_users.return_value = [MagicMock() for _ in range(3)]

        mock_user = MagicMock()
        mock_user.id = 10
        manager._create_virtual_user = AsyncMock(return_value=(mock_user, "child_token"))

        child_data = ChildRegistrationData(
            name="Ребёнок", surname="Иванов", date_of_birth=date(2021, 5, 10),
            age=5, weight=20, address="г. Москва", parent_id=1
        )

        user, token = await manager.create_child_user(child_data, 123456)

        assert user is mock_user
        assert token == "child_token"

    # ========== link_telegram_to_user ==========

    @pytest.mark.asyncio
    async def test_link_telegram_already_used(self, manager):
        """Telegram ID уже используется."""
        manager.user_repo.get_by_telegram_id.return_value = MagicMock()

        with pytest.raises(ValueError, match="уже используется"):
            await manager.link_telegram_to_user("token123", 123456)

    @pytest.mark.asyncio
    async def test_link_telegram_token_not_found(self, manager):
        """Токен не найден."""
        manager.user_repo.get_by_telegram_id.return_value = None
        manager.user_repo.get_by_token.return_value = None

        result = await manager.link_telegram_to_user("invalid_token", 123456)

        assert result is None

    @pytest.mark.asyncio
    async def test_link_telegram_already_linked(self, manager):
        """Пользователь уже привязан к Telegram."""
        manager.user_repo.get_by_telegram_id.return_value = None
        user = MagicMock()
        user.telegram_id = 999999
        manager.user_repo.get_by_token.return_value = user

        with pytest.raises(ValueError, match="уже привязан"):
            await manager.link_telegram_to_user("token123", 123456)

    @pytest.mark.asyncio
    async def test_link_telegram_success(self, manager):
        """Успешная привязка Telegram."""
        manager.user_repo.get_by_telegram_id.return_value = None
        user = MagicMock()
        user.id = 1
        user.telegram_id = None
        manager.user_repo.get_by_token.return_value = user
        manager.user_repo.update.return_value = True
        updated_user = MagicMock()
        updated_user.id = 1
        updated_user.telegram_id = 123456
        manager.user_repo.get_by_id.return_value = updated_user

        result = await manager.link_telegram_to_user("token123", 123456)

        assert result is not None
        assert result.telegram_id == 123456

    # ========== get_user_token ==========

    @pytest.mark.asyncio
    async def test_get_user_token_found(self, manager):
        """Токен найден."""
        user = MagicMock()
        user.verification_token = "token123"
        manager.user_repo.get_by_id.return_value = user

        result = await manager.get_user_token(1)

        assert result == "token123"

    @pytest.mark.asyncio
    async def test_get_user_token_not_found(self, manager):
        """Токен не найден."""
        manager.user_repo.get_by_id.return_value = None

        result = await manager.get_user_token(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_token_no_token(self, manager):
        """У пользователя нет токена."""
        user = MagicMock()
        user.verification_token = None
        manager.user_repo.get_by_id.return_value = user

        result = await manager.get_user_token(1)

        assert result is None

    # ========== get_all_admins ==========

    @pytest.mark.asyncio
    async def test_get_all_admins(self, manager):
        """Получение всех администраторов."""
        admin = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [admin]
        manager.session.execute.return_value = mock_result

        result = await manager.get_all_admins()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all_admins_error(self, manager):
        """Ошибка при получении администраторов."""
        manager.session.execute.side_effect = Exception("DB error")

        result = await manager.get_all_admins()

        assert result == []

    # ========== get_new_clients ==========

    @pytest.mark.asyncio
    async def test_get_new_clients(self, manager):
        """Получение новых клиентов."""
        client = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [client]
        manager.session.execute.return_value = mock_result

        result = await manager.get_new_clients(days_ago=7)

        assert len(result) == 1

    # ========== search_users ==========

    @pytest.mark.asyncio
    async def test_search_users(self, manager):
        """Поиск пользователей."""
        user = MagicMock()
        user.role = UserRole.client
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [user]
        manager.session.execute.return_value = mock_result

        result = await manager.search_users("Иван")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_users_error(self, manager):
        """Ошибка при поиске."""
        manager.session.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            await manager.search_users("Иван")

    # ========== get_child_info_for_display ==========

    @pytest.mark.asyncio
    async def test_get_child_info_for_display_found(self, manager):
        """Информация о ребёнке найдена."""
        child = MagicMock()
        child.id = 1
        child.full_name = "Ребёнок"
        child.age = 5
        child.weight = 20
        manager.user_repo.get_by_id.return_value = child

        result = await manager.get_child_info_for_display(1)

        assert result is not None
        assert result['full_name'] == "Ребёнок"
        assert result['age'] == 5

    @pytest.mark.asyncio
    async def test_get_child_info_for_display_not_found(self, manager):
        """Ребёнок не найден."""
        manager.user_repo.get_by_id.return_value = None

        result = await manager.get_child_info_for_display(999)

        assert result is None
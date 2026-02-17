"""
Тесты для специфических методов UserRepository.
Базовые CRUD операции уже протестированы в test_base_repository.py.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from app.database.models import User, UserRole, Excursion, ExcursionSlot, SlotStatus
from app.database.repositories.user_repository import UserRepository
from app.database.repositories.excursion_repository import ExcursionRepository
from app.database.repositories.slot_repository import SlotRepository


@pytest.mark.asyncio(scope="function")
class TestUserRepository:
    """Тесты для специфических методов UserRepository."""

    async def test_get_by_id(self, db_session, test_data):
        """Тест получения пользователя по ID."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        user = await repo.get_by_id(admin.id)
        assert user is not None
        assert user.id == admin.id
        assert user.telegram_id == admin.telegram_id

        # Несуществующий ID
        user = await repo.get_by_id(999999)
        assert user is None

    async def test_get_by_telegram_id(self, db_session, test_data):
        """Тест получения пользователя по telegram_id."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        user = await repo.get_by_telegram_id(admin.telegram_id)
        assert user is not None
        assert user.id == admin.id
        assert user.full_name == admin.full_name

        # Несуществующий telegram_id
        user = await repo.get_by_telegram_id(999999)
        assert user is None

    async def test_get_by_phone(self, db_session, test_data):
        """Тест получения пользователя по номеру телефона."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Поиск по нормализованному номеру
        user = await repo.get_by_phone(admin.phone_number)
        assert user is not None
        assert user.id == admin.id

        # Поиск по номеру с пробелами/дефисами
        user = await repo.get_by_phone("+7 (900) 111-22-33")
        assert user is not None
        assert user.id == admin.id

        # Поиск по номеру без +
        user = await repo.get_by_phone("89001112233")
        assert user is not None
        assert user.id == admin.id

        # Несуществующий номер
        user = await repo.get_by_phone("+79998887766")
        assert user is None

        # Некорректный формат номера
        user = await repo.get_by_phone("abc")
        assert user is None  # Должен вернуть None без исключения

    async def test_get_by_token(self, db_session):
        """Тест получения пользователя по токену."""
        repo = UserRepository(db_session)

        # Создаем пользователя с токеном
        token_user = await repo._create(
            User,
            telegram_id=None,
            full_name="Token User",
            phone_number="+79990001111",
            role=UserRole.client,
            verification_token="test-token-123",
            is_virtual=True,
            registration_type="PARENT"
        )

        # Поиск по токену
        user = await repo.get_by_token("test-token-123")
        assert user is not None
        assert user.id == token_user.id
        assert user.verification_token == "test-token-123"

        # Несуществующий токен
        user = await repo.get_by_token("invalid-token")
        assert user is None

    async def test_get_users_by_role(self, db_session, test_data):
        """Тест получения пользователей по роли."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]
        captain = test_data["captain"]
        client = test_data["client"]

        # Администраторы
        admins = await repo.get_users_by_role(UserRole.admin)
        assert len(admins) == 1
        assert admins[0].id == admin.id

        # Капитаны
        captains = await repo.get_users_by_role(UserRole.captain)
        assert len(captains) == 1
        assert captains[0].id == captain.id

        # Клиенты
        clients = await repo.get_users_by_role(UserRole.client)
        assert len(clients) >= 1
        assert clients[0].id == client.id

    async def test_get_users_created_by(self, db_session, test_data):
        """Тест получения пользователей, созданных администратором."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Создаем несколько пользователей от имени админа
        user1 = await repo._create(
            User,
            telegram_id=2001,
            full_name="Created User 1",
            phone_number="+79990001111",
            role=UserRole.client,
            created_by_id=admin.id
        )

        user2 = await repo._create(
            User,
            telegram_id=2002,
            full_name="Created User 2",
            phone_number="+79990002222",
            role=UserRole.client,
            created_by_id=admin.id
        )

        # Получаем всех созданных админом
        created_users = await repo.get_users_created_by(admin.id)
        assert len(created_users) >= 2

        created_ids = [u.id for u in created_users]
        assert user1.id in created_ids
        assert user2.id in created_ids

        # Для несуществующего создателя
        created_users = await repo.get_users_created_by(999999)
        assert len(created_users) == 0

    async def test_get_children_users(self, db_session, test_data):
        """Тест получения детей пользователя."""
        repo = UserRepository(db_session)
        parent = test_data["client"]  # Используем клиента как родителя

        # Создаем детей
        child1 = await repo._create(
            User,
            telegram_id=3001,
            full_name="Child One",
            phone_number="+79991111111:token1:child",  # виртуальный номер
            role=UserRole.client,
            is_virtual=True,
            linked_to_parent_id=parent.id
        )

        child2 = await repo._create(
            User,
            telegram_id=3002,
            full_name="Child Two",
            phone_number="+79992222222:token2:child",
            role=UserRole.client,
            is_virtual=True,
            linked_to_parent_id=parent.id
        )

        # Получаем детей
        children = await repo.get_children_users(parent.id)
        assert len(children) == 2

        child_ids = [c.id for c in children]
        assert child1.id in child_ids
        assert child2.id in child_ids

        # У родителя без детей
        children = await repo.get_children_users(999999)
        assert len(children) == 0

    async def test_get_all_captains(self, db_session, test_data):
        """Тест получения всех капитанов."""
        repo = UserRepository(db_session)
        captain = test_data["captain"]

        # Добавляем еще одного капитана
        another_captain = await repo._create(
            User,
            telegram_id=4001,
            full_name="Another Captain",
            phone_number="+79993334444",
            role=UserRole.captain
        )

        captains = await repo.get_all_captains()
        assert len(captains) >= 2

        captain_ids = [c.id for c in captains]
        assert captain.id in captain_ids
        assert another_captain.id in captain_ids

    async def test_check_user_exists(self, db_session, test_data):
        """Тест проверки существования пользователя по telegram_id."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Существует
        exists = await repo.check_user_exists(admin.telegram_id)
        assert exists is True

        # Не существует
        exists = await repo.check_user_exists(999999)
        assert exists is False

    async def test_check_phone_exists(self, db_session, test_data):
        """Тест проверки существования пользователя по телефону."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Существует
        exists = await repo.check_phone_exists(admin.phone_number)
        assert exists is True

        # Существует с разным форматом
        exists = await repo.check_phone_exists("8 900 111-22-33")
        assert exists is True

        # Не существует
        exists = await repo.check_phone_exists("+79998887766")
        assert exists is False

        # Некорректный формат
        exists = await repo.check_phone_exists("invalid")
        assert exists is False  # Должен вернуть False без исключения

    async def test_user_has_children(self, db_session, test_data):
        """Тест проверки наличия детей у пользователя."""
        repo = UserRepository(db_session)
        parent = test_data["client"]

        # Проверяем, что детей еще нет
        has_children = await repo.user_has_children(parent.id)
        assert has_children is False

        # Создаем ребенка
        await repo._create(
            User,
            telegram_id=5001,
            full_name="Test Child",
            phone_number="+79994445555:token:child",
            role=UserRole.client,
            is_virtual=True,
            linked_to_parent_id=parent.id
        )

        # Теперь есть дети
        has_children = await repo.user_has_children(parent.id)
        assert has_children is True

        # Несуществующий пользователь
        has_children = await repo.user_has_children(999999)
        assert has_children is False

    async def test_create_user(self, db_session):
        """Тест создания пользователя."""
        repo = UserRepository(db_session)

        user = await repo.create(
            telegram_id=6001,
            full_name="New User",
            phone_number="+79995556677",
            role=UserRole.client
        )

        assert user.id is not None
        assert user.telegram_id == 6001
        assert user.full_name == "New User"
        assert user.phone_number == "+79995556677"
        assert user.role == UserRole.client
        assert user.is_virtual is False
        assert user.verification_token is None

    async def test_update_user(self, db_session, test_data):
        """Тест обновления данных пользователя."""
        repo = UserRepository(db_session)
        client = test_data["client"]

        # Обновляем имя и телефон
        updated = await repo.update(
            client.id,
            full_name="Updated Name",
            phone_number="+79996668899"
        )
        assert updated is True

        # Проверяем изменения
        await db_session.refresh(client)
        assert client.full_name == "Updated Name"
        assert client.phone_number == "+79996668899"

        # Обновляем с None значениями (должны игнорироваться)
        updated = await repo.update(
            client.id,
            full_name=None,
            phone_number="+79997778811"
        )
        assert updated is True
        await db_session.refresh(client)
        assert client.full_name == "Updated Name"  # не изменилось
        assert client.phone_number == "+79997778811"  # изменилось

        # Пустое обновление
        updated = await repo.update(client.id)
        assert updated is False

        # Несуществующий пользователь
        updated = await repo.update(999999, full_name="No One")
        assert updated is False

    async def test_promote_roles(self, db_session, test_data):
        """Тест изменения ролей пользователя."""
        repo = UserRepository(db_session)
        client = test_data["client"]

        # Повышаем до капитана
        promoted = await repo.promote_to_captain(client.telegram_id)
        assert promoted is True

        await db_session.refresh(client)
        assert client.role == UserRole.captain

        # Повышаем до админа
        promoted = await repo.promote_to_admin(client.telegram_id)
        assert promoted is True

        await db_session.refresh(client)
        assert client.role == UserRole.admin

        # Понижаем до клиента
        promoted = await repo.promote_to_client(client.telegram_id)
        assert promoted is True

        await db_session.refresh(client)
        assert client.role == UserRole.client

        # Несуществующий пользователь
        promoted = await repo.promote_to_admin(999999)
        assert promoted is False

    async def test_get_available_captains(self, db_session, test_data):
        """Тест получения свободных капитанов."""
        user_repo = UserRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию
        excursion = await excursion_repo._create(
            Excursion,
            name="Test Excursion",
            description="For captain availability test",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Создаем капитана
        captain = await user_repo._create(
            User,
            telegram_id=7001,
            full_name="Busy Captain",
            phone_number="+79998887766",
            role=UserRole.captain
        )

        # Создаем слот для капитана (занят)
        now = datetime.now()
        start_time = now + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(hours=2)

        await slot_repo._create(
            ExcursionSlot,
            excursion_id=excursion.id,
            captain_id=captain.id,
            start_datetime=start_time,
            end_datetime=end_time,
            max_people=10,
            max_weight=500,
            status=SlotStatus.scheduled
        )

        # Проверяем доступность в то же время
        available = await user_repo.get_available_captains(
            start_datetime=start_time + timedelta(minutes=30),
            end_datetime=end_time - timedelta(minutes=30)
        )

        # Капитан должен быть занят
        captain_ids = [c.id for c in available]
        assert captain.id not in captain_ids

        # Проверяем доступность в другое время
        available = await user_repo.get_available_captains(
            start_datetime=start_time + timedelta(days=1),
            end_datetime=end_time + timedelta(days=1, hours=2)
        )

        # Капитан должен быть свободен
        captain_ids = [c.id for c in available]
        assert captain.id in captain_ids

    async def test_check_captain_availability(self, db_session, test_data):
        """Тест проверки занятости капитана."""
        user_repo = UserRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию
        excursion = await excursion_repo._create(
            Excursion,
            name="Test Excursion",
            description="For captain availability check",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Создаем капитана
        captain = await user_repo._create(
            User,
            telegram_id=8001,
            full_name="Test Captain",
            phone_number="+79998887766",
            role=UserRole.captain
        )

        # Создаем слот
        now = datetime.now()
        start_time = now + timedelta(days=1, hours=14)
        end_time = start_time + timedelta(hours=2)

        slot = await slot_repo._create(
            ExcursionSlot,
            excursion_id=excursion.id,
            captain_id=captain.id,
            start_datetime=start_time,
            end_datetime=end_time,
            max_people=10,
            max_weight=500,
            status=SlotStatus.scheduled
        )

        # Проверяем занятость в пересекающееся время
        is_busy = await user_repo.check_captain_availability(
            captain_id=captain.id,
            start_datetime=start_time + timedelta(minutes=30),
            end_datetime=end_time - timedelta(minutes=30)
        )
        assert is_busy is True  # Занят

        # Проверяем занятость в непересекающееся время
        is_busy = await user_repo.check_captain_availability(
            captain_id=captain.id,
            start_datetime=end_time + timedelta(hours=1),
            end_datetime=end_time + timedelta(hours=3)
        )
        assert is_busy is False  # Свободен

        # Проверяем с исключением текущего слота
        is_busy = await user_repo.check_captain_availability(
            captain_id=captain.id,
            start_datetime=start_time + timedelta(minutes=30),
            end_datetime=end_time - timedelta(minutes=30),
            exclude_slot_id=slot.id
        )
        assert is_busy is False  # Игнорируем текущий слот

        # Несуществующий капитан
        is_busy = await user_repo.check_captain_availability(
            captain_id=999999,
            start_datetime=start_time,
            end_datetime=end_time
        )
        assert is_busy is False  # Нет слота - свободен


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
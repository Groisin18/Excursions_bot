"""
Тесты для базового репозитория.
Используем UserRepository как реализацию BaseRepository для тестирования.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import User, UserRole
from app.database.repositories.user_repository import UserRepository


@pytest.mark.asyncio(scope="function")
class TestBaseRepository:
    """Тесты для методов BaseRepository на примере UserRepository."""

    async def test_create(self, db_session):
        """Тест создания записи."""
        repo = UserRepository(db_session)

        # Создаем нового пользователя
        new_user = await repo._create(
            User,
            telegram_id=999999,
            full_name="Test User",
            phone_number="+79998887766",
            role=UserRole.client
        )

        assert new_user.id is not None
        assert new_user.telegram_id == 999999
        assert new_user.full_name == "Test User"
        assert new_user.phone_number == "+79998887766"
        assert new_user.role == UserRole.client

        # Проверяем, что пользователь действительно сохранен
        saved = await repo.get_by_telegram_id(999999)
        assert saved is not None
        assert saved.id == new_user.id

    async def test_create_duplicate_telegram_id(self, db_session, test_data):
        """Тест создания дубликата telegram_id."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Пытаемся создать пользователя с существующим telegram_id
        with pytest.raises(IntegrityError):
            await repo._create(
                User,
                telegram_id=admin.telegram_id,
                full_name="Another User",
                phone_number="+79998887755",
                role=UserRole.client
            )
        await db_session.rollback()

    async def test_get_one(self, db_session, test_data):
        """Тест получения одной записи."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Получаем по ID
        user = await repo._get_one(User, User.id == admin.id)
        assert user is not None
        assert user.id == admin.id
        assert user.telegram_id == admin.telegram_id

        # Получаем по telegram_id
        user = await repo._get_one(User, User.telegram_id == admin.telegram_id)
        assert user is not None
        assert user.id == admin.id

        # Получаем несуществующую запись
        user = await repo._get_one(User, User.id == 999999)
        assert user is None

    async def test_get_many(self, db_session, test_data):
        """Тест получения нескольких записей."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]
        captain = test_data["captain"]
        client = test_data["client"]

        # Все пользователи
        users = await repo._get_many(User)
        assert len(users) >= 3

        user_ids = [u.id for u in users]
        assert admin.id in user_ids
        assert captain.id in user_ids
        assert client.id in user_ids

        # Фильтр по роли
        admins = await repo._get_many(User, User.role == UserRole.admin)
        assert len(admins) == 1
        assert admins[0].id == admin.id

        # Фильтр с limit
        limited = await repo._get_many(User, limit=2)
        assert len(limited) == 2

        # Сортировка
        ordered = await repo._get_many(User, order_by=User.telegram_id.desc())
        assert ordered[0].telegram_id > ordered[-1].telegram_id

    async def test_update(self, db_session, test_data):
        """Тест обновления записей."""
        repo = UserRepository(db_session)
        client = test_data["client"]

        # Обновляем одного пользователя
        updated_count = await repo._update(
            User,
            User.id == client.id,
            full_name="Updated Name",
            phone_number="+79998887799"
        )

        assert updated_count == 1

        # Проверяем изменения
        await db_session.refresh(client)
        assert client.full_name == "Updated Name"
        assert client.phone_number == "+79998887799"

        # Обновляем несуществующего пользователя
        updated_count = await repo._update(
            User,
            User.id == 999999,
            full_name="NoOne"
        )
        assert updated_count == 0

        # Обновляем без данных
        updated_count = await repo._update(User, User.id == client.id)
        assert updated_count == 0

    async def test_delete(self, db_session):
        """Тест удаления записей."""
        repo = UserRepository(db_session)

        # Создаем временного пользователя для удаления
        temp_user = await repo._create(
            User,
            telegram_id=888888,
            full_name="Temp User",
            phone_number="+79998887744",
            role=UserRole.client
        )

        temp_id = temp_user.id

        # Удаляем
        deleted_count = await repo._delete(User, User.id == temp_id)
        assert deleted_count == 1

        # Проверяем, что удален
        user = await repo._get_one(User, User.id == temp_id)
        assert user is None

        # Удаляем несуществующего
        deleted_count = await repo._delete(User, User.id == 999999)
        assert deleted_count == 0

    async def test_exists(self, db_session, test_data):
        """Тест проверки существования записи."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        # Существует
        exists = await repo._exists(User, User.id == admin.id)
        assert exists is True

        # Не существует
        exists = await repo._exists(User, User.id == 999999)
        assert exists is False

    async def test_count(self, db_session, test_data):
        """Тест подсчета количества записей."""
        repo = UserRepository(db_session)

        # Все пользователи
        total = await repo._count(User)
        assert total >= 3

        # Фильтр по роли
        admin_count = await repo._count(User, User.role == UserRole.admin)
        assert admin_count == 1

        captain_count = await repo._count(User, User.role == UserRole.captain)
        assert captain_count == 1

        client_count = await repo._count(User, User.role == UserRole.client)
        assert client_count >= 1

        # Несуществующий фильтр
        zero_count = await repo._count(User, User.id == 999999)
        assert zero_count == 0

    async def test_bulk_create(self, db_session):
        """Тест массового создания записей."""
        repo = UserRepository(db_session)

        data_list = [
            {
                "telegram_id": 10001,
                "full_name": "Bulk1 User1",
                "phone_number": "+79990001111",
                "role": UserRole.client
            },
            {
                "telegram_id": 10002,
                "full_name": "Bulk2 User2",
                "phone_number": "+79990002222",
                "role": UserRole.client
            },
            {
                "telegram_id": 10003,
                "full_name": "Bulk3 User3",
                "phone_number": "+79990003333",
                "role": UserRole.client
            }
        ]

        users = await repo._bulk_create(User, data_list)

        assert len(users) == 3
        assert users[0].telegram_id == 10001
        assert users[0].full_name == "Bulk1 User1"
        assert users[0].phone_number == "+79990001111"
        assert users[1].telegram_id == 10002
        assert users[1].full_name == "Bulk2 User2"
        assert users[1].phone_number == "+79990002222"
        assert users[2].telegram_id == 10003
        assert users[2].full_name == "Bulk3 User3"
        assert users[2].phone_number == "+79990003333"
        assert all(u.id is not None for u in users)

    async def test_execute_query(self, db_session, test_data):
        """Тест выполнения произвольного запроса."""
        repo = UserRepository(db_session)
        admin = test_data["admin"]

        from sqlalchemy import select

        # Простой select
        query = select(User).where(User.id == admin.id)
        result = await repo._execute_query(query)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.id == admin.id

        # Запрос с ошибкой
        from sqlalchemy import text
        with pytest.raises(Exception):
            await repo._execute_query(text("SELECT * FROM non_existent_table"))

    async def test_error_handling(self, db_session):
        """Тест обработки ошибок."""
        repo = UserRepository(db_session)

        from sqlalchemy import text

        # _get_one с некорректным условием
        result = await repo._get_one(User, text("invalid sql"))
        assert result is None

        # _get_many с некорректным условием
        results = await repo._get_many(User, text("invalid sql"))
        assert results == []

        # _exists с некорректным условием
        exists = await repo._exists(User, text("invalid sql"))
        assert exists is False

        # _count с некорректным условием
        count = await repo._count(User, text("invalid sql"))
        assert count == 0

        # _update с некорректным условием
        updated = await repo._update(User, text("invalid sql"), full_name="Test")
        assert updated == 0

        # _delete с некорректным условием
        deleted = await repo._delete(User, text("invalid sql"))
        assert deleted == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Тесты для ExcursionRepository.
"""

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio(scope="function")
class TestExcursionRepository:
    """Тесты для ExcursionRepository."""

    async def test_create_excursion(self, db_session):
        """Тест создания экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        excursion = await repo.create(
            name="Морская прогулка",
            description="Прогулка по заливу",
            base_duration_minutes=120,
            base_price=1500,
            is_active=True
        )

        assert excursion.id is not None
        assert excursion.name == "Морская прогулка"
        assert excursion.description == "Прогулка по заливу"
        assert excursion.base_duration_minutes == 120
        assert excursion.base_price == 1500
        assert excursion.is_active is True

        # Проверяем, что сохранилась
        saved = await repo.get_by_id(excursion.id)
        assert saved is not None
        assert saved.name == "Морская прогулка"

    async def test_create_excursion_minimal(self, db_session):
        """Тест создания экскурсии с минимальными данными."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию только с обязательными полями
        excursion = await repo.create(
            name="Минимальная",
            base_duration_minutes=60,
            base_price=1000
        )

        assert excursion.id is not None
        assert excursion.name == "Минимальная"
        assert excursion.description is None
        assert excursion.base_duration_minutes == 60
        assert excursion.base_price == 1000
        assert excursion.is_active is True  # По умолчанию

    async def test_get_by_id(self, db_session):
        """Тест получения экскурсии по ID."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        created = await repo.create(
            name="Тестовая",
            base_duration_minutes=60,
            base_price=1000
        )

        # Получаем по ID
        found = await repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == "Тестовая"

        # Получаем несуществующую
        not_found = await repo.get_by_id(999999)
        assert not_found is None

    async def test_get_by_name(self, db_session):
        """Тест получения экскурсии по названию."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        await repo.create(
            name="Поиск по имени",
            base_duration_minutes=60,
            base_price=1000
        )

        # Получаем по точному названию
        found = await repo.get_by_name("Поиск по имени")
        assert found is not None
        assert found.name == "Поиск по имени"

        # Поиск с неверным регистром (должен быть None, если поиск точный)
        not_found = await repo.get_by_name("поиск по имени")
        assert not_found is None

        # Поиск несуществующего
        not_found = await repo.get_by_name("Не существует")
        assert not_found is None

    async def test_get_all(self, db_session):
        """Тест получения всех экскурсий."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем несколько экскурсий
        await repo.create(
            name="Активная 1",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )
        await repo.create(
            name="Активная 2",
            base_duration_minutes=90,
            base_price=1500,
            is_active=True
        )
        await repo.create(
            name="Неактивная",
            base_duration_minutes=120,
            base_price=2000,
            is_active=False
        )

        # Получаем только активные (по умолчанию)
        active_excursions = await repo.get_all(active_only=True)
        assert len(active_excursions) >= 2
        active_names = [e.name for e in active_excursions]
        assert "Активная 1" in active_names
        assert "Активная 2" in active_names
        assert "Неактивная" not in active_names

        # Получаем все (включая неактивные)
        all_excursions = await repo.get_all(active_only=False)
        assert len(all_excursions) >= 3
        all_names = [e.name for e in all_excursions]
        assert "Активная 1" in all_names
        assert "Активная 2" in all_names
        assert "Неактивная" in all_names

    async def test_update_excursion(self, db_session):
        """Тест обновления экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        excursion = await repo.create(
            name="Для обновления",
            description="Старое описание",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Обновляем все поля
        updated = await repo.update(
            excursion.id,
            name="Обновленное название",
            description="Новое описание",
            base_duration_minutes=90,
            base_price=1500,
            is_active=False
        )
        assert updated is True

        # Проверяем изменения
        await db_session.refresh(excursion)
        assert excursion.name == "Обновленное название"
        assert excursion.description == "Новое описание"
        assert excursion.base_duration_minutes == 90
        assert excursion.base_price == 1500
        assert excursion.is_active is False

    async def test_update_partial(self, db_session):
        """Тест частичного обновления экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        excursion = await repo.create(
            name="Исходное название",
            description="Описание",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Обновляем только название
        updated = await repo.update(excursion.id, name="Новое название")
        assert updated is True

        # Проверяем - изменилось только название
        await db_session.refresh(excursion)
        assert excursion.name == "Новое название"
        assert excursion.description == "Описание"
        assert excursion.base_duration_minutes == 60
        assert excursion.base_price == 1000
        assert excursion.is_active is True

    async def test_update_nonexistent(self, db_session):
        """Тест обновления несуществующей экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        updated = await repo.update(999999, name="Новое название")
        assert updated is False

    async def test_update_no_data(self, db_session):
        """Тест обновления без данных."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем экскурсию
        excursion = await repo.create(
            name="Тест",
            base_duration_minutes=60,
            base_price=1000
        )

        # Пытаемся обновить без данных
        updated = await repo.update(excursion.id)
        assert updated is False

        # Проверяем, что данные не изменились
        await db_session.refresh(excursion)
        assert excursion.name == "Тест"

    async def test_deactivate_excursion(self, db_session):
        """Тест деактивации экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем активную экскурсию
        excursion = await repo.create(
            name="Для деактивации",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Деактивируем
        result = await repo.deactivate(excursion.id)
        assert result is True

        # Проверяем
        await db_session.refresh(excursion)
        assert excursion.is_active is False

        # Деактивируем уже неактивную
        result = await repo.deactivate(excursion.id)
        assert result is True  # Все еще True, т.к. обновление прошло
        assert excursion.is_active is False  # Статус не изменился

    async def test_activate_excursion(self, db_session):
        """Тест активации экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем неактивную экскурсию
        excursion = await repo.create(
            name="Для активации",
            base_duration_minutes=60,
            base_price=1000,
            is_active=False
        )

        # Активируем
        result = await repo.activate(excursion.id)
        assert result is True

        # Проверяем
        await db_session.refresh(excursion)
        assert excursion.is_active is True

    async def test_activate_deactivate_nonexistent(self, db_session):
        """Тест активации/деактивации несуществующей экскурсии."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        result = await repo.activate(999999)
        assert result is False

        result = await repo.deactivate(999999)
        assert result is False

    async def test_get_all_order(self, db_session):
        """Тест порядка получения экскурсий (должны быть отсортированы по ID или имени)."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Создаем несколько экскурсий
        names = ["C Экскурсия", "A Экскурсия", "B Экскурсия"]
        for name in names:
            await repo.create(
                name=name,
                base_duration_minutes=60,
                base_price=1000
            )

        # Получаем все
        excursions = await repo.get_all(active_only=False)

        # Проверяем, что они в порядке добавления (по ID возрастанию)
        # Если в _get_many нет сортировки, они будут по ID
        for i in range(1, len(excursions)):
            assert excursions[i-1].id < excursions[i].id

    async def test_repository_inheritance(self, db_session):
        """Тест, что репозиторий наследует базовые методы."""
        from app.database.repositories import ExcursionRepository
        repo = ExcursionRepository(db_session)

        # Проверяем наличие базовых методов
        assert hasattr(repo, '_get_one')
        assert hasattr(repo, '_get_many')
        assert hasattr(repo, '_create')
        assert hasattr(repo, '_update')
        assert hasattr(repo, '_delete')
        assert hasattr(repo, '_exists')
        assert hasattr(repo, '_count')
        assert hasattr(repo, '_bulk_create')
        assert hasattr(repo, '_execute_query')

        # Проверяем наличие специфичных методов
        assert hasattr(repo, 'get_by_id')
        assert hasattr(repo, 'get_by_name')
        assert hasattr(repo, 'get_all')
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'update')
        assert hasattr(repo, 'deactivate')
        assert hasattr(repo, 'activate')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
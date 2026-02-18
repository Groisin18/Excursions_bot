"""
Тесты для PromoCodeRepository.
"""

import pytest
from datetime import datetime, timedelta

from app.database.models import PromoCode, DiscountType
from app.database.repositories import PromoCodeRepository


@pytest.mark.asyncio(loop_scope="function")
class TestPromoCodeRepository:
    """Тесты для PromoCodeRepository."""

    async def test_create_promocode(self, db_session):
        """Тест создания промокода."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        # Используем уникальный код с timestamp, чтобы избежать конфликтов
        import time
        unique_code = f"TEST{int(time.time())}"

        promocode = await repo.create_promocode(
            code=unique_code,
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        assert promocode.id is not None
        assert promocode.code == unique_code
        assert promocode.discount_type == DiscountType.percent
        assert promocode.discount_value == 10
        assert promocode.valid_from <= now
        assert promocode.valid_until >= now
        assert promocode.usage_limit == 100
        assert promocode.used_count == 0


    async def test_create_promocode_fixed(self, db_session):
        """Тест создания промокода с фиксированной скидкой."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="FIXED500",
            discount_type=DiscountType.fixed,
            discount_value=500,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=50
        )

        assert promocode.id is not None
        assert promocode.code == "FIXED500"
        assert promocode.discount_type == DiscountType.fixed
        assert promocode.discount_value == 500
        assert promocode.usage_limit == 50

    async def test_create_duplicate_code(self, db_session):
        """Тест создания промокода с существующим кодом."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        # Создаем первый промокод
        await repo.create_promocode(
            code="UNIQUE",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        # Пытаемся создать второй с таким же кодом
        with pytest.raises(ValueError, match="Промокод с кодом 'UNIQUE' уже существует"):
            await repo.create_promocode(
                code="UNIQUE",
                discount_type=DiscountType.percent,
                discount_value=20,
                valid_from=now - timedelta(days=1),
                valid_until=now + timedelta(days=30),
                usage_limit=100
            )

    async def test_get_by_id(self, db_session):
        """Тест получения промокода по ID."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        created = await repo.create_promocode(
            code="GETBYID",
            discount_type=DiscountType.percent,
            discount_value=15,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        found = await repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.code == "GETBYID"
        assert found.discount_value == 15

        not_found = await repo.get_by_id(999999)
        assert not_found is None

    async def test_get_by_code(self, db_session):
        """Тест получения промокода по коду."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        await repo.create_promocode(
            code="SEARCHCODE",
            discount_type=DiscountType.percent,
            discount_value=25,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        found = await repo.get_by_code("SEARCHCODE")
        assert found is not None
        assert found.code == "SEARCHCODE"
        assert found.discount_value == 25

        # Поиск с неверным регистром
        not_found = await repo.get_by_code("searchcode")
        assert not_found is None

        # Поиск несуществующего
        not_found = await repo.get_by_code("NONEXISTENT")
        assert not_found is None

    async def test_get_valid_by_code(self, db_session):
        """Тест получения валидного промокода по коду."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()

        # Валидный промокод
        valid = await repo.create_promocode(
            code="VALID",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        # Просроченный промокод
        expired = await repo.create_promocode(
            code="EXPIRED",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=10),
            valid_until=now - timedelta(days=1),
            usage_limit=100
        )

        # Еще не начавший действовать
        future = await repo.create_promocode(
            code="FUTURE",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now + timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        # Исчерпавший лимит
        exhausted = await repo.create_promocode(
            code="EXHAUSTED",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=1
        )
        # Увеличиваем счетчик использований
        await repo.increment_usage(exhausted.id)

        # Проверяем валидный
        found = await repo.get_valid_by_code("VALID")
        assert found is not None
        assert found.code == "VALID"

        # Проверяем просроченный
        found = await repo.get_valid_by_code("EXPIRED")
        assert found is None

        # Проверяем будущий
        found = await repo.get_valid_by_code("FUTURE")
        assert found is None

        # Проверяем исчерпанный
        found = await repo.get_valid_by_code("EXHAUSTED")
        assert found is None

        # Проверяем несуществующий
        found = await repo.get_valid_by_code("NONEXISTENT")
        assert found is None

    async def test_get_all(self, db_session):
        """Тест получения всех промокодов."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()

        # Активные промокоды
        await repo.create_promocode(
            code="ACTIVE1",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=5),
            valid_until=now + timedelta(days=5),
            usage_limit=100
        )

        await repo.create_promocode(
            code="ACTIVE2",
            discount_type=DiscountType.percent,
            discount_value=15,
            valid_from=now - timedelta(days=3),
            valid_until=now + timedelta(days=7),
            usage_limit=100
        )

        # Неактивный (просроченный)
        await repo.create_promocode(
            code="INACTIVE",
            discount_type=DiscountType.percent,
            discount_value=20,
            valid_from=now - timedelta(days=10),
            valid_until=now - timedelta(days=1),
            usage_limit=100
        )

        # Получаем только активные
        active = await repo.get_all(include_inactive=False)
        assert len(active) >= 2
        active_codes = [p.code for p in active]
        assert "ACTIVE1" in active_codes
        assert "ACTIVE2" in active_codes
        assert "INACTIVE" not in active_codes

        # Получаем все (включая неактивные)
        all_promos = await repo.get_all(include_inactive=True)
        assert len(all_promos) >= 3
        all_codes = [p.code for p in all_promos]
        assert "ACTIVE1" in all_codes
        assert "ACTIVE2" in all_codes
        assert "INACTIVE" in all_codes

    async def test_check_code_exists(self, db_session):
        """Тест проверки существования кода."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        await repo.create_promocode(
            code="EXISTS",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        assert await repo.check_code_exists("EXISTS") is True
        assert await repo.check_code_exists("exists") is False  # регистр важен
        assert await repo.check_code_exists("NONEXISTENT") is False

    async def test_update_promocode(self, db_session):
        """Тест обновления промокода."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="UPDATE",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        # Обновляем несколько полей
        new_valid_until = now + timedelta(days=60)
        updated = await repo.update_promocode(
            promocode.id,
            discount_value=15,
            valid_until=new_valid_until,
            usage_limit=200
        )
        assert updated is True

        # Проверяем изменения
        await db_session.refresh(promocode)
        assert promocode.discount_value == 15
        assert promocode.valid_until == new_valid_until
        assert promocode.usage_limit == 200
        assert promocode.code == "UPDATE"  # не изменилось

        # Обновляем без данных
        updated = await repo.update_promocode(promocode.id)
        assert updated is False

        # Обновляем несуществующий
        updated = await repo.update_promocode(999999, discount_value=20)
        assert updated is False

    async def test_increment_usage(self, db_session):
        """Тест увеличения счетчика использований."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="INCREMENT",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=5
        )

        assert promocode.used_count == 0

        # Увеличиваем несколько раз
        for i in range(1, 4):
            result = await repo.increment_usage(promocode.id)
            assert result is True
            await db_session.refresh(promocode)
            assert promocode.used_count == i

        # Увеличиваем у несуществующего
        result = await repo.increment_usage(999999)
        assert result is False

    async def test_deactivate(self, db_session):
        """Тест деактивации промокода."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="DEACTIVATE",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        assert promocode.valid_until > now

        # Деактивируем
        result = await repo.deactivate(promocode.id)
        assert result is True

        await db_session.refresh(promocode)
        # Проверяем, что valid_until изменился на время около now (с допуском в 1 секунду)
        assert abs((promocode.valid_until - now).total_seconds()) < 1

    async def test_get_usage_count(self, db_session):
        """Тест получения количества использований."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="USAGECOUNT",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )

        # Изначально 0
        count = await repo.get_usage_count(promocode.id)
        assert count == 0

        # Увеличиваем
        await repo.increment_usage(promocode.id)
        count = await repo.get_usage_count(promocode.id)
        assert count == 1

        # Для несуществующего
        count = await repo.get_usage_count(999999)
        assert count == 0

    async def test_promocode_properties(self, db_session):
        """Тест свойств модели PromoCode."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()

        # Валидный промокод
        valid = await repo.create_promocode(
            code="PROP_VALID",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=5
        )
        assert valid.is_valid is True
        assert valid.remaining_uses == 5

        # Используем один раз
        await repo.increment_usage(valid.id)
        await db_session.refresh(valid)
        assert valid.remaining_uses == 4

        # Просроченный
        expired = await repo.create_promocode(
            code="PROP_EXPIRED",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=10),
            valid_until=now - timedelta(days=1),
            usage_limit=5
        )
        assert expired.is_valid is False

        # Исчерпанный
        exhausted = await repo.create_promocode(
            code="PROP_EXHAUSTED",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=2
        )
        await repo.increment_usage(exhausted.id)
        await repo.increment_usage(exhausted.id)
        await db_session.refresh(exhausted)
        assert exhausted.is_valid is False
        assert exhausted.remaining_uses == 0

    async def test_apply_discount(self, db_session):
        """Тест применения скидки."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()

        # Процентная скидка
        percent = await repo.create_promocode(
            code="PERCENT",
            discount_type=DiscountType.percent,
            discount_value=20,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )
        assert percent.apply_discount(1000) == 800
        assert percent.apply_discount(500) == 400
        assert percent.apply_discount(0) == 0

        # Фиксированная скидка
        fixed = await repo.create_promocode(
            code="FIXED",
            discount_type=DiscountType.fixed,
            discount_value=300,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=100
        )
        assert fixed.apply_discount(1000) == 700
        assert fixed.apply_discount(500) == 200
        assert fixed.apply_discount(200) == 0  # Не уходим в минус

    async def test_to_dict(self, db_session):
        """Тест преобразования в словарь."""
        repo = PromoCodeRepository(db_session)

        now = datetime.now()
        promocode = await repo.create_promocode(
            code="DICT",
            discount_type=DiscountType.percent,
            discount_value=15,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            usage_limit=10
        )

        data = promocode.to_dict()
        assert data['code'] == "DICT"
        assert data['discount_type'] == "percent"
        assert data['discount_value'] == 15
        assert data['used_count'] == 0
        assert data['usage_limit'] == 10
        assert data['is_valid'] is True
        assert data['remaining_uses'] == 10

    async def test_repository_inheritance(self, db_session):
        """Тест, что репозиторий наследует базовые методы."""
        repo = PromoCodeRepository(db_session)

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
        assert hasattr(repo, 'get_by_code')
        assert hasattr(repo, 'get_valid_by_code')
        assert hasattr(repo, 'get_all')
        assert hasattr(repo, 'check_code_exists')
        assert hasattr(repo, 'create_promocode')
        assert hasattr(repo, 'update_promocode')
        assert hasattr(repo, 'increment_usage')
        assert hasattr(repo, 'deactivate')
        assert hasattr(repo, 'get_usage_count')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
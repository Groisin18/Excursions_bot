"""
Тесты для SlotRepository.
"""

import pytest
from datetime import datetime, timedelta, date
from sqlalchemy.exc import IntegrityError

from app.database.models import (
    Excursion, ExcursionSlot, User, UserRole,
    SlotStatus, Booking, BookingStatus, PaymentStatus
)
from app.database.repositories.slot_repository import SlotRepository
from app.database.repositories.excursion_repository import ExcursionRepository
from app.database.repositories.user_repository import UserRepository
from app.database.repositories.booking_repository import BookingRepository


@pytest.mark.asyncio(scope="function")
class TestSlotRepository:
    """Тесты для SlotRepository."""

    async def test_create_slot(self, db_session, test_data):
        """Тест создания слота."""
        # Создаем экскурсию
        excursion_repo = ExcursionRepository(db_session)
        excursion = await excursion_repo._create(
            Excursion,
            name="Test Excursion",
            description="For slot testing",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        # Создаем слот
        slot_repo = SlotRepository(db_session)
        now = datetime.now()
        start_time = now + timedelta(days=1, hours=10)

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=start_time,
            max_people=10,
            max_weight=500,
            captain_id=test_data["captain"].id,
            status=SlotStatus.scheduled
        )

        assert slot.id is not None
        assert slot.excursion_id == excursion.id
        assert slot.captain_id == test_data["captain"].id
        assert slot.start_datetime == start_time
        assert slot.end_datetime == start_time + timedelta(minutes=excursion.base_duration_minutes)
        assert slot.max_people == 10
        assert slot.max_weight == 500
        assert slot.status == SlotStatus.scheduled

    async def test_create_slot_without_captain(self, db_session):
        """Тест создания слота без капитана."""
        # Создаем экскурсию
        excursion_repo = ExcursionRepository(db_session)
        excursion = await excursion_repo._create(
            Excursion,
            name="Test Excursion",
            description="For slot without captain",
            base_duration_minutes=90,
            base_price=1500,
            is_active=True
        )

        # Создаем слот без капитана
        slot_repo = SlotRepository(db_session)
        now = datetime.now()
        start_time = now + timedelta(days=2, hours=14)

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=start_time,
            max_people=15,
            max_weight=600,
            captain_id=None,
            status=SlotStatus.scheduled
        )

        assert slot.id is not None
        assert slot.captain_id is None
        assert slot.status == SlotStatus.scheduled

    async def test_get_by_id(self, db_session, test_slot):
        """Тест получения слота по ID."""
        slot_repo = SlotRepository(db_session)

        slot = await slot_repo.get_by_id(test_slot.id)
        assert slot is not None
        assert slot.id == test_slot.id
        assert slot.excursion is not None  # Должна быть загружена экскурсия
        assert slot.excursion.name == test_slot.excursion.name

        # Несуществующий ID
        slot = await slot_repo.get_by_id(999999)
        assert slot is None

    async def test_get_for_date(self, db_session, test_slot):
        """Тест получения слотов на дату."""
        slot_repo = SlotRepository(db_session)

        # Дата, на которую есть слот
        target_date = test_slot.start_datetime.date()
        slots = await slot_repo.get_for_date(target_date)
        assert len(slots) >= 1
        assert any(s.id == test_slot.id for s in slots)

        # Проверяем, что экскурсия загружена
        for slot in slots:
            assert slot.excursion is not None

        # Дата без слотов
        tomorrow = target_date + timedelta(days=30)
        slots = await slot_repo.get_for_date(tomorrow)
        assert len(slots) == 0

    async def test_get_for_period(self, db_session, test_slot):
        """Тест получения слотов за период."""
        slot_repo = SlotRepository(db_session)

        # Период, включающий слот
        date_from = test_slot.start_datetime - timedelta(days=1)
        date_to = test_slot.start_datetime + timedelta(days=1)

        slots = await slot_repo.get_for_period(date_from, date_to)
        assert len(slots) >= 1
        assert any(s.id == test_slot.id for s in slots)

        # Период до слота
        slots = await slot_repo.get_for_period(
            date_from - timedelta(days=10),
            date_from - timedelta(days=5)
        )
        assert len(slots) == 0

    async def test_get_schedule(self, db_session, test_slot):
        """Тест получения расписания с фильтрами."""
        slot_repo = SlotRepository(db_session)

        # Без фильтров
        slots = await slot_repo.get_schedule()
        assert len(slots) >= 1

        # Фильтр по дате от
        slots = await slot_repo.get_schedule(
            date_from=test_slot.start_datetime - timedelta(days=1)
        )
        assert len(slots) >= 1

        # Фильтр по дате до
        slots = await slot_repo.get_schedule(
            date_to=test_slot.start_datetime + timedelta(days=1)
        )
        assert len(slots) >= 1

        # Фильтр по экскурсии
        slots = await slot_repo.get_schedule(
            excursion_id=test_slot.excursion_id
        )
        assert len(slots) >= 1

        # Фильтр с отмененными (их пока нет)
        slots = await slot_repo.get_schedule(include_cancelled=True)
        assert len(slots) >= 1

    async def test_get_public_schedule(self, db_session, test_slot):
        """Тест получения публичного расписания."""
        slot_repo = SlotRepository(db_session)

        # Публичное расписание — только слоты с капитаном и статусом scheduled
        date_from = test_slot.start_datetime - timedelta(days=1)
        date_to = test_slot.start_datetime + timedelta(days=1)

        slots = await slot_repo.get_public_schedule(date_from, date_to)
        assert len(slots) >= 1
        assert all(s.status == SlotStatus.scheduled for s in slots)
        assert all(s.captain_id is not None for s in slots)

        # Создаем слот без капитана
        excursion_repo = ExcursionRepository(db_session)
        excursion = await excursion_repo._create(
            Excursion,
            name="Another Excursion",
            description="For public schedule test",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        slot_without_captain = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=test_slot.start_datetime + timedelta(days=2),
            max_people=10,
            max_weight=500,
            captain_id=None
        )

        slots = await slot_repo.get_public_schedule(
            slot_without_captain.start_datetime - timedelta(days=1),
            slot_without_captain.start_datetime + timedelta(days=1)
        )
        assert slot_without_captain.id not in [s.id for s in slots]

    async def test_get_available(self, db_session, test_slot):
        """Тест получения доступных слотов для экскурсии."""
        slot_repo = SlotRepository(db_session)

        # Период, включающий слот
        date_from = test_slot.start_datetime - timedelta(days=1)
        date_to = test_slot.start_datetime + timedelta(days=1)

        slots = await slot_repo.get_available(
            excursion_id=test_slot.excursion_id,
            date_from=date_from,
            date_to=date_to
        )
        assert len(slots) >= 1
        assert any(s.id == test_slot.id for s in slots)

        # Проверяем, что загружены экскурсия и капитан
        for slot in slots:
            assert slot.excursion is not None
            assert slot.captain is not None

    async def test_get_with_bookings(self, db_session, test_slot, test_booking):
        """Тест получения слота с бронированиями."""
        slot_repo = SlotRepository(db_session)

        slot = await slot_repo.get_with_bookings(test_slot.id)
        assert slot is not None
        assert slot.id == test_slot.id
        assert slot.excursion is not None
        assert slot.captain is not None
        assert len(slot.bookings) >= 1

        # Проверяем, что бронирования загружены с клиентами
        for booking in slot.bookings:
            assert booking.adult_user is not None

    async def test_get_captain_slots(self, db_session, test_slot):
        """Тест получения слотов капитана."""
        slot_repo = SlotRepository(db_session)
        user_repo = UserRepository(db_session)

        # Получаем капитана по telegram_id
        captain = await user_repo.get_by_id(test_slot.captain_id)

        # Период, включающий слот
        start_date = test_slot.start_datetime - timedelta(days=1)
        end_date = test_slot.start_datetime + timedelta(days=1)

        slots = await slot_repo.get_captain_slots(
            captain_telegram_id=captain.telegram_id,
            start_date=start_date,
            end_date=end_date
        )
        assert len(slots) >= 1
        assert any(s.id == test_slot.id for s in slots)

        # Проверяем, что загружены экскурсия и бронирования
        for slot in slots:
            assert slot.excursion is not None

    async def test_get_captain_completed_slots_for_period(self, db_session, test_slot):
        """Тест получения завершенных слотов капитана за период."""
        slot_repo = SlotRepository(db_session)

        # Меняем статус слота на completed
        await slot_repo.update_status(test_slot.id, SlotStatus.completed)

        # Период, включающий слот
        start_date = test_slot.start_datetime.date() - timedelta(days=1)
        end_date = test_slot.start_datetime.date() + timedelta(days=1)

        slots = await slot_repo.get_captain_completed_slots_for_period(
            captain_id=test_slot.captain_id,
            start_date=start_date,
            end_date=end_date
        )
        assert len(slots) >= 1
        assert any(s.id == test_slot.id for s in slots)
        assert all(s.status == SlotStatus.completed for s in slots)

        # Период без слотов
        slots = await slot_repo.get_captain_completed_slots_for_period(
            captain_id=test_slot.captain_id,
            start_date=start_date - timedelta(days=30),
            end_date=start_date - timedelta(days=20)
        )
        assert len(slots) == 0

    async def test_get_conflicting(self, db_session, test_slot):
        """Тест проверки конфликтующих слотов."""
        slot_repo = SlotRepository(db_session)

        # Тот же период - должен быть конфликт
        conflicting = await slot_repo.get_conflicting(
            excursion_id=test_slot.excursion_id,
            start_datetime=test_slot.start_datetime + timedelta(minutes=30),
            end_datetime=test_slot.end_datetime - timedelta(minutes=30)
        )
        assert conflicting is not None
        assert conflicting.id == test_slot.id

        # Тот же период, исключая текущий слот - конфликта нет
        conflicting = await slot_repo.get_conflicting(
            excursion_id=test_slot.excursion_id,
            start_datetime=test_slot.start_datetime + timedelta(minutes=30),
            end_datetime=test_slot.end_datetime - timedelta(minutes=30),
            exclude_slot_id=test_slot.id
        )
        assert conflicting is None

        # Другой период - нет конфликта
        conflicting = await slot_repo.get_conflicting(
            excursion_id=test_slot.excursion_id,
            start_datetime=test_slot.start_datetime + timedelta(days=1),
            end_datetime=test_slot.end_datetime + timedelta(days=1)
        )
        assert conflicting is None

        # Другая экскурсия - нет конфликта
        # Создаем другую экскурсию
        excursion_repo = ExcursionRepository(db_session)
        another_excursion = await excursion_repo._create(
            Excursion,
            name="Another Excursion",
            description="For conflict test",
            base_duration_minutes=60,
            base_price=1000,
            is_active=True
        )

        conflicting = await slot_repo.get_conflicting(
            excursion_id=another_excursion.id,
            start_datetime=test_slot.start_datetime,
            end_datetime=test_slot.end_datetime
        )
        assert conflicting is None

    async def test_update_status(self, db_session, test_slot):
        """Тест обновления статуса слота."""
        slot_repo = SlotRepository(db_session)

        # Меняем статус на completed
        updated = await slot_repo.update_status(test_slot.id, SlotStatus.completed)
        assert updated is True

        # Проверяем
        slot = await slot_repo.get_by_id(test_slot.id)
        assert slot.status == SlotStatus.completed

        # Меняем статус на cancelled
        updated = await slot_repo.update_status(test_slot.id, SlotStatus.cancelled)
        assert updated is True

        slot = await slot_repo.get_by_id(test_slot.id)
        assert slot.status == SlotStatus.cancelled

        # Несуществующий слот
        updated = await slot_repo.update_status(999999, SlotStatus.completed)
        assert updated is False

    async def test_assign_captain(self, db_session, test_slot, test_data):
        """Тест назначения капитана на слот."""
        slot_repo = SlotRepository(db_session)

        # Создаем нового капитана
        user_repo = UserRepository(db_session)
        new_captain = await user_repo._create(
            User,
            telegram_id=9001,
            full_name="New Captain",
            phone_number="+79998887766",
            role=UserRole.captain
        )

        # Назначаем капитана
        updated = await slot_repo.assign_captain(test_slot.id, new_captain.id)
        assert updated is True

        # Проверяем
        slot = await slot_repo.get_by_id(test_slot.id)
        assert slot.captain_id == new_captain.id

        # Несуществующий слот
        updated = await slot_repo.assign_captain(999999, new_captain.id)
        assert updated is False

    async def test_update_slot(self, db_session, test_slot):
        """Тест обновления данных слота."""
        slot_repo = SlotRepository(db_session)

        # Обновляем несколько полей
        new_start = test_slot.start_datetime + timedelta(hours=2)
        updated = await slot_repo.update(
            test_slot.id,
            start_datetime=new_start,
            max_people=20,
            max_weight=800
        )
        assert updated is True

        # Проверяем
        slot = await slot_repo.get_by_id(test_slot.id)
        assert slot.start_datetime == new_start
        assert slot.end_datetime == new_start + timedelta(minutes=slot.excursion.base_duration_minutes)
        assert slot.max_people == 20
        assert slot.max_weight == 800

        # Пустое обновление
        updated = await slot_repo.update(test_slot.id)
        assert updated is False

        # Несуществующий слот
        updated = await slot_repo.update(999999, max_people=30)
        assert updated is False


# ========== Фикстуры для тестов SlotRepository ==========

@pytest.fixture
async def test_excursion(db_session):
    """Создает тестовую экскурсию."""
    repo = ExcursionRepository(db_session)
    excursion = await repo._create(
        Excursion,
        name="Test Excursion",
        description="For slot testing",
        base_duration_minutes=60,
        base_price=1000,
        is_active=True
    )
    return excursion


@pytest.fixture
async def test_slot(db_session, test_excursion, test_data):
    """Создает тестовый слот."""
    repo = SlotRepository(db_session)
    now = datetime.now()
    start_time = now + timedelta(days=1, hours=10)

    slot = await repo.create(
        excursion_id=test_excursion.id,
        start_datetime=start_time,
        max_people=10,
        max_weight=500,
        captain_id=test_data["captain"].id,
        status=SlotStatus.scheduled
    )
    return slot


@pytest.fixture
async def test_booking(db_session, test_slot, test_data):
    """Создает тестовое бронирование для слота."""
    from app.database.repositories.booking_repository import BookingRepository

    repo = BookingRepository(db_session)
    booking = await repo._create(
        Booking,
        slot_id=test_slot.id,
        adult_user_id=test_data["client"].id,
        total_price=1000,
        booking_status=BookingStatus.active,
        payment_status=PaymentStatus.not_paid
    )
    return booking


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
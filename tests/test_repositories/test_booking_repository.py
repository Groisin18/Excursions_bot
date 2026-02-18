"""
Тесты для BookingRepository.
"""

import pytest
from datetime import datetime, timedelta

from app.database.models import (
    BookingStatus, ClientStatus, PaymentStatus, SlotStatus,
    BookingChild, DiscountType
)


@pytest.mark.asyncio(loop_scope="function")
class TestBookingRepository:
    """Тесты для BookingRepository."""

    async def test_create_booking(self, db_session, test_data):
        """Тест создания бронирования."""
        from app.database.repositories import BookingRepository, ExcursionRepository, SlotRepository
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000,
            captain_id=None,
            status=SlotStatus.scheduled
        )

        client = test_data["client"]

        # Создаем бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        assert booking.id is not None
        assert booking.slot_id == slot.id
        assert booking.adult_user_id == client.id
        assert booking.total_price == 1000
        assert booking.booking_status == BookingStatus.active
        assert booking.payment_status == PaymentStatus.not_paid
        assert booking.client_status == ClientStatus.not_arrived

    async def test_create_booking_with_admin(self, db_session, test_data):
        """Тест создания бронирования администратором."""
        from app.database.repositories import BookingRepository, ExcursionRepository, SlotRepository
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 2",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]
        admin = test_data["admin"]

        # Создаем бронирование от имени админа
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000,
            admin_creator_id=admin.id
        )

        assert booking.id is not None
        assert booking.admin_creator_id == admin.id

    async def test_create_booking_with_promocode(self, db_session, test_data):
        """Тест создания бронирования с промокодом."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository,
            SlotRepository, PromoCodeRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)
        promocode_repo = PromoCodeRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 3",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        # Создаем промокод
        promocode = await promocode_repo.create_promocode(
            code="TEST10",
            discount_type=DiscountType.percent,  # Исправлено: percent вместо percentage
            discount_value=10,
            valid_from=datetime.now() - timedelta(days=1),
            valid_until=datetime.now() + timedelta(days=30),
            usage_limit=100
        )

        client = test_data["client"]

        # Создаем бронирование с промокодом
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=900,  # Цена со скидкой
            promo_code_id=promocode.id
        )

        assert booking.id is not None
        assert booking.promo_code_id == promocode.id
        assert booking.total_price == 900


    async def test_get_by_id(self, db_session, test_data):
        """Тест получения бронирования по ID с полной загрузкой."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository,
            SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 5",
            description="Описание экскурсии",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000,
            captain_id=test_data["captain"].id
        )

        client = test_data["client"]

        # Создаем бронирование
        created = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Получаем по ID
        found = await booking_repo.get_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.slot is not None
        assert found.slot.excursion is not None
        assert found.slot.excursion.name == "Тестовая экскурсия 5"
        assert found.slot.captain is not None
        assert found.slot.captain.id == test_data["captain"].id
        assert found.adult_user is not None
        assert found.adult_user.id == client.id
        assert hasattr(found, 'payments')
        assert hasattr(found, 'booking_children')

    async def test_get_by_id_nonexistent(self, db_session):
        """Тест получения несуществующего бронирования."""
        from app.database.repositories import BookingRepository
        booking_repo = BookingRepository(db_session)

        found = await booking_repo.get_by_id(999999)
        assert found is None

    async def test_get_user_bookings(self, db_session, test_data):
        """Тест получения бронирований пользователя."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 6",
            base_duration_minutes=60,
            base_price=1000
        )

        client = test_data["client"]

        # Создаем несколько бронирований для пользователя
        created_bookings = []
        for i in range(3):
            slot = await slot_repo.create(
                excursion_id=excursion.id,
                start_datetime=datetime.now() + timedelta(days=i+1),
                max_people=10,
                max_weight=1000
            )

            booking = await booking_repo.create(
                slot_id=slot.id,
                adult_user_id=client.id,
                total_price=1000
            )
            created_bookings.append(booking.id)

        # Получаем бронирования пользователя
        bookings = await booking_repo.get_user_bookings(client.telegram_id)

        # Фильтруем только те, что создали в этом тесте
        user_bookings = [b for b in bookings if b.id in created_bookings]
        assert len(user_bookings) == 3

        # Проверяем сортировку по убыванию created_at
        for i in range(1, len(user_bookings)):
            assert user_bookings[i-1].created_at >= user_bookings[i].created_at

    async def test_get_user_bookings_with_data(self, db_session, test_data):
        """Тест получения бронирований пользователя с загруженными данными."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 7",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000,
            captain_id=test_data["captain"].id
        )

        client = test_data["client"]

        # Создаем бронирование
        await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Получаем бронирования
        bookings = await booking_repo.get_user_bookings(client.telegram_id)
        user_bookings = [b for b in bookings if b.adult_user_id == client.id and b.slot_id == slot.id]

        assert len(user_bookings) == 1
        booking = user_bookings[0]
        assert booking.slot is not None
        assert booking.slot.excursion is not None
        assert booking.slot.excursion.name == "Тестовая экскурсия 7"
        assert booking.slot.captain is not None
        assert booking.slot.captain.id == test_data["captain"].id
        assert hasattr(booking, 'booking_children')

    async def test_get_user_active_for_slot(self, db_session, test_data):
        """Тест получения активной брони пользователя на слот."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 8",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]

        # Создаем активное бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Получаем активную бронь
        found = await booking_repo.get_user_active_for_slot(client.id, slot.id)

        assert found is not None
        assert found.id == booking.id
        assert found.booking_status == BookingStatus.active

        # Проверяем, что неактивная не находится
        found = await booking_repo.get_user_active_for_slot(999999, slot.id)
        assert found is None

    async def test_get_upcoming_bookings_for_reminder(self, db_session, test_data):
        """Тест получения бронирований для напоминаний."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 9",
            base_duration_minutes=60,
            base_price=1000
        )

        client = test_data["client"]

        now = datetime.now()

        # Создаем слоты с разным временем
        slots_data = []
        for hours in [23, 24, 25, -1]:
            slot = await slot_repo.create(
                excursion_id=excursion.id,
                start_datetime=now + timedelta(hours=hours),
                max_people=10,
                max_weight=1000
            )
            slots_data.append(slot)

        # Создаем бронирования для каждого слота
        created_bookings = []
        for slot in slots_data:
            booking = await booking_repo.create(
                slot_id=slot.id,
                adult_user_id=client.id,
                total_price=1000
            )
            created_bookings.append(booking.id)
            # Оплачиваем будущие бронирования
            if slot.start_datetime > now:
                await booking_repo.update_payment_status(booking.id, PaymentStatus.paid)

        # Получаем бронирования для напоминаний (за 24 часа)
        reminders = await booking_repo.get_upcoming_bookings_for_reminder(24)

        # Фильтруем только те, что создали в этом тесте
        test_reminders = [r for r in reminders if r.id in created_bookings]
        assert len(test_reminders) == 2

        # Проверяем, что это правильные слоты
        reminder_times = [r.slot.start_datetime for r in test_reminders]
        assert any(abs((t - (now + timedelta(hours=23))).total_seconds()) < 3600 for t in reminder_times)
        assert any(abs((t - (now + timedelta(hours=24))).total_seconds()) < 3600 for t in reminder_times)

    async def test_get_upcoming_bookings_only_paid(self, db_session, test_data):
        """Тест получения напоминаний только для оплаченных бронирований."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 10",
            base_duration_minutes=60,
            base_price=1000
        )

        client = test_data["client"]
        captain = test_data["captain"]
        now = datetime.now()

        # Создаем слот
        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=now + timedelta(hours=23),
            max_people=10,
            max_weight=1000
        )

        # Создаем оплаченное бронирование
        paid_booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )
        await booking_repo.update_payment_status(paid_booking.id, PaymentStatus.paid)

        # Создаем неоплаченное бронирование на тот же слот (для другого клиента)
        unpaid_booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=captain.id,
            total_price=1000
        )
        # Оставляем payment_status = not_paid

        # Получаем напоминания
        reminders = await booking_repo.get_upcoming_bookings_for_reminder(24)

        # Должно быть только оплаченное бронирование
        # Фильтруем по нашему слоту
        slot_reminders = [r for r in reminders if r.slot_id == slot.id]
        assert len(slot_reminders) == 1
        assert slot_reminders[0].id == paid_booking.id

    async def test_get_booked_people_count(self, db_session, test_data):
        """Тест подсчета забронированных людей в слоте."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 11",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]
        # В модели UserRole нет 'child', используем существующего пользователя как ребенка
        # или создаем обычного пользователя

        # Создаем бронирования
        booking1 = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Добавляем ребенка к бронированию (используем капитана как ребенка для теста)
        booking_child = BookingChild(
            booking_id=booking1.id,
            child_user_id=test_data["captain"].id,  # Используем существующего пользователя
            age_category="8-12 лет",
            calculated_price=500
        )
        db_session.add(booking_child)

        # Создаем второе бронирование (без детей)
        booking2 = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=test_data["captain"].id,
            total_price=1000
        )

        await db_session.flush()

        # Подсчитываем людей
        total_people = await booking_repo.get_booked_people_count(slot.id)

        # booking1: 1 взрослый + 1 ребенок = 2
        # booking2: 1 взрослый = 1
        # Итого: 3
        assert total_people == 3

    async def test_get_booked_people_count_no_bookings(self, db_session):
        """Тест подсчета людей в пустом слоте."""
        from app.database.repositories import BookingRepository
        booking_repo = BookingRepository(db_session)

        count = await booking_repo.get_booked_people_count(999999)
        assert count == 0

    async def test_update_status(self, db_session, test_data):
        """Тест обновления статусов бронирования."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 12",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]

        # Создаем бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Обновляем статусы
        result = await booking_repo.update_status(
            booking.id,
            client_status=ClientStatus.arrived,
            payment_status=PaymentStatus.paid
        )
        assert result is True

        # Проверяем изменения
        await db_session.refresh(booking)
        assert booking.client_status == ClientStatus.arrived
        assert booking.payment_status == PaymentStatus.paid

        # Обновляем только один статус (client_status обратно)
        result = await booking_repo.update_status(
            booking.id,
            client_status=ClientStatus.not_arrived
        )
        assert result is True
        await db_session.refresh(booking)
        assert booking.client_status == ClientStatus.not_arrived
        assert booking.payment_status == PaymentStatus.paid  # Не изменился

        # Обновляем без данных
        result = await booking_repo.update_status(booking.id)
        assert result is False

    async def test_update_payment_status(self, db_session, test_data):
        """Тест обновления статуса оплаты."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 13",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]

        # Создаем бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Обновляем статус оплаты
        result = await booking_repo.update_payment_status(booking.id, PaymentStatus.paid)
        assert result is True

        await db_session.refresh(booking)
        assert booking.payment_status == PaymentStatus.paid

        # Обновляем несуществующее бронирование
        result = await booking_repo.update_payment_status(999999, PaymentStatus.paid)
        assert result is False

    async def test_cancel_booking(self, db_session, test_data):
        """Тест отмены бронирования."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        from app.database.models import Booking

        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 14",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]

        # Создаем бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Отменяем через прямой update
        updated = await booking_repo._update(
            Booking,
            Booking.id == booking.id,
            booking_status=BookingStatus.cancelled
        )
        assert updated > 0

        await db_session.refresh(booking)
        assert booking.booking_status == BookingStatus.cancelled

    async def test_update_booking(self, db_session, test_data):
        """Тест обновления данных бронирования."""
        from app.database.repositories import (
            BookingRepository, ExcursionRepository, SlotRepository
        )
        booking_repo = BookingRepository(db_session)
        excursion_repo = ExcursionRepository(db_session)
        slot_repo = SlotRepository(db_session)

        # Создаем экскурсию и слот
        excursion = await excursion_repo.create(
            name="Тестовая экскурсия 15",
            base_duration_minutes=60,
            base_price=1000
        )

        slot = await slot_repo.create(
            excursion_id=excursion.id,
            start_datetime=datetime.now() + timedelta(days=1),
            max_people=10,
            max_weight=1000
        )

        client = test_data["client"]

        # Создаем бронирование
        booking = await booking_repo.create(
            slot_id=slot.id,
            adult_user_id=client.id,
            total_price=1000
        )

        # Обновляем данные (только существующие поля)
        result = await booking_repo.update(
            booking.id,
            total_price=1200
        )
        assert result is True

        await db_session.refresh(booking)
        assert booking.total_price == 1200

        # Обновляем без данных
        result = await booking_repo.update(booking.id)
        assert result is False

        # Обновляем несуществующее
        result = await booking_repo.update(999999, total_price=1500)
        assert result is False

    async def test_repository_inheritance(self, db_session):
        """Тест, что репозиторий наследует базовые методы."""
        from app.database.repositories import BookingRepository
        repo = BookingRepository(db_session)

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
        assert hasattr(repo, 'get_user_bookings')
        assert hasattr(repo, 'get_user_active_for_slot')
        assert hasattr(repo, 'get_upcoming_bookings_for_reminder')
        assert hasattr(repo, 'get_booked_people_count')
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'create_with_token')
        assert hasattr(repo, 'update_status')
        assert hasattr(repo, 'cancel')
        assert hasattr(repo, 'update')
        assert hasattr(repo, 'update_payment_status')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""Тесты для планировщика задач."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.scheduler.tasks import (
    auto_cancel_unpaid_bookings,
    send_payment_reminder,
    send_excursion_reminder,
    auto_complete_excursions
)
from app.database.models import  SlotStatus


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def setup_mocks(monkeypatch):
    """Настройка общих моков."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("app.services.scheduler.tasks.async_session", lambda: mock_session)
    monkeypatch.setattr("app.services.scheduler.tasks.UnitOfWork", lambda s: mock_uow)

    return mock_session, mock_uow


def mock_redis_for_tasks(mock_redis_client, monkeypatch):
    """Мок для Redis во всех задачах."""
    # Настраиваем acquire_lock как корутину
    mock_acquire_lock = AsyncMock(return_value="mock-token")
    mock_redis_client.acquire_lock = mock_acquire_lock

    # Настраиваем release_lock как корутину
    mock_release_lock = AsyncMock(return_value=True)
    mock_redis_client.release_lock = mock_release_lock

    # Настраиваем client.get и client.setex как корутины
    mock_redis_client.client = AsyncMock()
    mock_redis_client.client.get = AsyncMock()
    mock_redis_client.client.setex = AsyncMock()

    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)
    return mock_redis_client


def mock_bot_for_tasks(monkeypatch):
    """Мок для бота."""
    mock_bot = AsyncMock()
    monkeypatch.setattr("app.services.scheduler.tasks.get_bot_instance", lambda: mock_bot)
    return mock_bot


# ========== ТЕСТЫ ДЛЯ auto_cancel_unpaid_bookings ==========

@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_success(mock_redis_client, monkeypatch):
    """Тест успешной автоотмены бронирований."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456
    mock_booking.slot.excursion.name = "Тестовая экскурсия"
    mock_booking.slot.start_datetime = datetime.now() + timedelta(hours=1)

    mock_booking_manager.get_expired_unpaid_bookings.return_value = [mock_booking]
    mock_booking_manager.cancel_booking.return_value = (True, "Успешно", None)

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await auto_cancel_unpaid_bookings()

    mock_booking_manager.get_expired_unpaid_bookings.assert_called_once()
    mock_booking_manager.cancel_booking.assert_called_once_with(booking_id=1, auto_refund=False)
    mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_no_bookings(mock_redis_client, monkeypatch):
    """Тест когда нет бронирований для отмены."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()
    mock_booking_manager.get_expired_unpaid_bookings.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await auto_cancel_unpaid_bookings()

    mock_booking_manager.get_expired_unpaid_bookings.assert_called_once()
    mock_booking_manager.cancel_booking.assert_not_called()
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_cancel_failed(mock_redis_client, monkeypatch):
    """Тест когда отмена бронирования не удалась."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456

    mock_booking_manager.get_expired_unpaid_bookings.return_value = [mock_booking]
    mock_booking_manager.cancel_booking.return_value = (False, "Ошибка отмены", None)

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await auto_cancel_unpaid_bookings()

    mock_booking_manager.cancel_booking.assert_called_once()
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_no_telegram_id(mock_redis_client, monkeypatch):
    """Тест когда у пользователя нет telegram_id."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = None

    mock_booking_manager.get_expired_unpaid_bookings.return_value = [mock_booking]
    mock_booking_manager.cancel_booking.return_value = (True, "Успешно", None)

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await auto_cancel_unpaid_bookings()

    mock_booking_manager.cancel_booking.assert_called_once()
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_lock_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось получить блокировку."""
    mock_acquire_lock = AsyncMock(return_value=None)
    mock_redis_client.acquire_lock = mock_acquire_lock
    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)

    with patch("app.services.scheduler.tasks.BookingManager") as mock_booking_manager:
        await auto_cancel_unpaid_bookings()
        mock_booking_manager.assert_not_called()


@pytest.mark.asyncio
async def test_auto_cancel_unpaid_bookings_exception(mock_redis_client, monkeypatch):
    """Тест обработки исключения."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    # Заставляем UnitOfWork выбросить исключение
    mock_uow.__aenter__.side_effect = Exception("Ошибка БД")

    # Ожидаем исключение
    with pytest.raises(Exception) as exc_info:
        await auto_cancel_unpaid_bookings()

    assert "Ошибка БД" in str(exc_info.value)

    # В этом случае release_lock НЕ должен вызываться,
    # потому что исключение произошло до входа в try
    mock_redis_client.release_lock.assert_not_called()


# ========== ТЕСТЫ ДЛЯ send_payment_reminder ==========

@pytest.mark.asyncio
async def test_send_payment_reminder_success(mock_redis_client, monkeypatch):
    """Тест успешной отправки напоминания об оплате."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456
    mock_booking.slot.excursion.name = "Тестовая экскурсия"
    mock_booking.slot.start_datetime = datetime.now() + timedelta(hours=2)

    deadline = datetime.now() + timedelta(minutes=60)
    mock_booking_manager.get_bookings_for_payment_reminder.return_value = [(mock_booking, deadline)]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_payment_reminder()

    mock_bot.send_message.assert_called_once()
    mock_redis.client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_send_payment_reminder_duplicate_prevention(mock_redis_client, monkeypatch):
    """Тест предотвращения дублей напоминаний."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456

    deadline = datetime.now() + timedelta(minutes=60)
    mock_booking_manager.get_bookings_for_payment_reminder.return_value = [(mock_booking, deadline)]

    mock_redis.client.get.return_value = "1"

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_payment_reminder()

    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_send_payment_reminder_no_telegram_id(mock_redis_client, monkeypatch):
    """Тест когда у пользователя нет telegram_id."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = None

    deadline = datetime.now() + timedelta(minutes=60)
    mock_booking_manager.get_bookings_for_payment_reminder.return_value = [(mock_booking, deadline)]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_payment_reminder()

    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_send_payment_reminder_no_bookings(mock_redis_client, monkeypatch):
    """Тест когда нет бронирований для напоминания."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()
    mock_booking_manager.get_bookings_for_payment_reminder.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_payment_reminder()

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_payment_reminder_lock_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось получить блокировку."""
    mock_acquire_lock = AsyncMock(return_value=None)
    mock_redis_client.acquire_lock = mock_acquire_lock
    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)

    with patch("app.services.scheduler.tasks.BookingManager") as mock_booking_manager:
        await send_payment_reminder()
        mock_booking_manager.assert_not_called()


# ========== ТЕСТЫ ДЛЯ send_excursion_reminder ==========

@pytest.mark.asyncio
async def test_send_excursion_reminder_success(mock_redis_client, monkeypatch):
    """Тест успешной отправки напоминания об экскурсии."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456
    mock_booking.slot.excursion.name = "Тестовая экскурсия"
    mock_booking.slot.start_datetime = datetime.now() + timedelta(hours=24)

    mock_booking_manager.get_paid_bookings_for_reminder.return_value = [mock_booking]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_excursion_reminder()

    mock_booking_manager.get_paid_bookings_for_reminder.assert_called_once_with(hours_before=24)
    mock_bot.send_message.assert_called_once()
    mock_redis.client.setex.assert_called_once()


@pytest.mark.asyncio
async def test_send_excursion_reminder_duplicate_prevention(mock_redis_client, monkeypatch):
    """Тест предотвращения дублей напоминаний об экскурсии."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = 123456

    mock_booking_manager.get_paid_bookings_for_reminder.return_value = [mock_booking]

    mock_redis.client.get.return_value = "1"

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_excursion_reminder()

    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_send_excursion_reminder_no_telegram_id(mock_redis_client, monkeypatch):
    """Тест когда у пользователя нет telegram_id."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()

    mock_booking = MagicMock()
    mock_booking.id = 1
    mock_booking.adult_user.telegram_id = None

    mock_booking_manager.get_paid_bookings_for_reminder.return_value = [mock_booking]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_excursion_reminder()

    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_send_excursion_reminder_no_bookings(mock_redis_client, monkeypatch):
    """Тест когда нет бронирований для напоминания."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_booking_manager = AsyncMock()
    mock_booking_manager.get_paid_bookings_for_reminder.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.BookingManager", lambda s: mock_booking_manager)

    await send_excursion_reminder()

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_excursion_reminder_lock_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось получить блокировку."""
    mock_acquire_lock = AsyncMock(return_value=None)
    mock_redis_client.acquire_lock = mock_acquire_lock
    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)

    with patch("app.services.scheduler.tasks.BookingManager") as mock_booking_manager:
        await send_excursion_reminder()
        mock_booking_manager.assert_not_called()


# ========== ТЕСТЫ ДЛЯ auto_complete_excursions ==========

@pytest.mark.asyncio
async def test_auto_complete_excursions_success(mock_redis_client, monkeypatch):
    """Тест успешного автозавершения слотов."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    mock_slot_manager = AsyncMock()

    mock_slot_to_start = MagicMock()
    mock_slot_to_start.id = 1
    mock_slot_to_start.status = SlotStatus.scheduled

    mock_slot_to_complete = MagicMock()
    mock_slot_to_complete.id = 2
    mock_slot_to_complete.status = SlotStatus.in_progress

    mock_slot_manager.get_slots_to_start.return_value = [mock_slot_to_start]
    mock_slot_manager.get_slots_to_complete.return_value = [mock_slot_to_complete]

    mock_slot_repo = AsyncMock()
    mock_slot_manager.slot_repo = mock_slot_repo
    mock_slot_repo.update_status = AsyncMock(return_value=True)

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    await auto_complete_excursions()

    assert mock_slot_repo.update_status.call_count == 2
    mock_slot_repo.update_status.assert_any_call(1, SlotStatus.in_progress)
    mock_slot_repo.update_status.assert_any_call(2, SlotStatus.completed)


@pytest.mark.asyncio
async def test_auto_complete_excursions_no_slots(mock_redis_client, monkeypatch):
    """Тест когда нет слотов для обновления."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_slot_manager.get_slots_to_start.return_value = []
    mock_slot_manager.get_slots_to_complete.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    await auto_complete_excursions()

    mock_slot_manager.get_slots_to_start.assert_called_once()
    mock_slot_manager.get_slots_to_complete.assert_called_once()


@pytest.mark.asyncio
async def test_auto_complete_excursions_only_start(mock_redis_client, monkeypatch):
    """Тест когда есть только слоты для старта."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    mock_slot_manager = AsyncMock()

    mock_slot_to_start = MagicMock()
    mock_slot_to_start.id = 1
    mock_slot_to_start.status = SlotStatus.scheduled

    mock_slot_manager.get_slots_to_start.return_value = [mock_slot_to_start]
    mock_slot_manager.get_slots_to_complete.return_value = []

    mock_slot_repo = AsyncMock()
    mock_slot_manager.slot_repo = mock_slot_repo
    mock_slot_repo.update_status = AsyncMock(return_value=True)

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    await auto_complete_excursions()

    mock_slot_repo.update_status.assert_called_once_with(1, SlotStatus.in_progress)


@pytest.mark.asyncio
async def test_auto_complete_excursions_only_complete(mock_redis_client, monkeypatch):
    """Тест когда есть только слоты для завершения."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    mock_slot_manager = AsyncMock()

    mock_slot_to_complete = MagicMock()
    mock_slot_to_complete.id = 2
    mock_slot_to_complete.status = SlotStatus.in_progress

    mock_slot_manager.get_slots_to_start.return_value = []
    mock_slot_manager.get_slots_to_complete.return_value = [mock_slot_to_complete]

    mock_slot_repo = AsyncMock()
    mock_slot_manager.slot_repo = mock_slot_repo
    mock_slot_repo.update_status = AsyncMock(return_value=True)

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    await auto_complete_excursions()

    mock_slot_repo.update_status.assert_called_once_with(2, SlotStatus.completed)


@pytest.mark.asyncio
async def test_auto_complete_excursions_update_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось обновить статус слота."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis_for_tasks(mock_redis_client, monkeypatch)

    mock_slot_manager = AsyncMock()

    mock_slot_to_start = MagicMock()
    mock_slot_to_start.id = 1
    mock_slot_to_start.status = SlotStatus.scheduled

    mock_slot_manager.get_slots_to_start.return_value = [mock_slot_to_start]
    mock_slot_manager.get_slots_to_complete.return_value = []

    mock_slot_repo = AsyncMock()
    mock_slot_manager.slot_repo = mock_slot_repo
    mock_slot_repo.update_status = AsyncMock(return_value=False)

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    # Должно отработать без ошибок
    await auto_complete_excursions()

    mock_slot_repo.update_status.assert_called_once()


@pytest.mark.asyncio
async def test_auto_complete_excursions_lock_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось получить блокировку."""
    mock_acquire_lock = AsyncMock(return_value=None)
    mock_redis_client.acquire_lock = mock_acquire_lock
    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)

    with patch("app.services.scheduler.tasks.SlotManager") as mock_slot_manager:
        await auto_complete_excursions()
        mock_slot_manager.assert_not_called()
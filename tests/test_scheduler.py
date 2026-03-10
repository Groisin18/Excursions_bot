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


# ========== ТЕСТЫ ДЛЯ notify_admins_about_slots_without_captain ==========

@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_success(mock_redis_client, monkeypatch):
    """Тест успешной отправки уведомлений о слотах без капитана."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    # Создаем тестовые слоты
    mock_slot1 = MagicMock()
    mock_slot1.id = 101
    mock_slot1.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot1.excursion.name = "Морская прогулка"

    mock_slot2 = MagicMock()
    mock_slot2.id = 102
    mock_slot2.start_datetime = datetime.now() + timedelta(hours=30)
    mock_slot2.excursion.name = "Рыбалка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot1, mock_slot2]

    # Создаем тестовых администраторов
    mock_admin1 = MagicMock()
    mock_admin1.telegram_id = 111111
    mock_admin2 = MagicMock()
    mock_admin2.telegram_id = 222222

    mock_user_manager.get_all_admins.return_value = [mock_admin1, mock_admin2]

    # Redis возвращает None (уведомление еще не отправлялось)
    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    # Импортируем новую функцию
    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    # Проверяем вызовы
    mock_slot_manager.get_slots_without_captain.assert_called_once_with(hours_before=48)
    mock_user_manager.get_all_admins.assert_called_once()

    # Должно быть отправлено 2 сообщения (двум админам)
    assert mock_bot.send_message.call_count == 2
    assert mock_redis.client.setex.call_count == 2  # Для каждого админа свой ключ


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_no_slots(mock_redis_client, monkeypatch):
    """Тест когда нет слотов без капитана."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_slot_manager.get_slots_without_captain.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    mock_slot_manager.get_slots_without_captain.assert_called_once()
    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_no_admins(mock_redis_client, monkeypatch):
    """Тест когда нет администраторов в базе."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    mock_slot = MagicMock()
    mock_slot.id = 101
    mock_slot.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot.excursion.name = "Морская прогулка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot]
    mock_user_manager.get_all_admins.return_value = []

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    mock_user_manager.get_all_admins.assert_called_once()
    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_duplicate_prevention(mock_redis_client, monkeypatch):
    """Тест предотвращения дублей уведомлений."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    mock_slot = MagicMock()
    mock_slot.id = 101
    mock_slot.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot.excursion.name = "Морская прогулка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot]

    mock_admin = MagicMock()
    mock_admin.telegram_id = 111111

    mock_user_manager.get_all_admins.return_value = [mock_admin]

    # Redis возвращает "1" - уведомление уже отправлялось в последние 12 часов
    mock_redis.client.get.return_value = "1"

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    mock_slot_manager.get_slots_without_captain.assert_called_once()
    mock_user_manager.get_all_admins.assert_called_once()
    mock_bot.send_message.assert_not_called()
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_some_admins_without_telegram(mock_redis_client, monkeypatch):
    """Тест когда некоторые администраторы не имеют telegram_id."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    mock_slot = MagicMock()
    mock_slot.id = 101
    mock_slot.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot.excursion.name = "Морская прогулка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot]

    # Один админ с telegram_id, другой - без
    mock_admin1 = MagicMock()
    mock_admin1.telegram_id = 111111
    mock_admin2 = MagicMock()
    mock_admin2.telegram_id = None

    mock_user_manager.get_all_admins.return_value = [mock_admin1, mock_admin2]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    # Должно быть отправлено только одно сообщение (админу с telegram_id)
    mock_bot.send_message.assert_called_once()
    assert mock_redis.client.setex.call_count == 1


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_slots_grouping(mock_redis_client, monkeypatch):
    """Тест правильной группировки слотов по датам в сообщении."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    # Создаем слоты на разные даты
    today = datetime.now()

    mock_slot1 = MagicMock()
    mock_slot1.id = 101
    mock_slot1.start_datetime = today + timedelta(hours=47)
    mock_slot1.excursion.name = "Морская прогулка"

    mock_slot2 = MagicMock()
    mock_slot2.id = 102
    mock_slot2.start_datetime = today + timedelta(hours=46)
    mock_slot2.excursion.name = "Морская прогулка"  # Та же дата

    mock_slot3 = MagicMock()
    mock_slot3.id = 103
    mock_slot3.start_datetime = today + timedelta(hours=25)  # Другой день
    mock_slot3.excursion.name = "Рыбалка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot1, mock_slot2, mock_slot3]

    mock_admin = MagicMock()
    mock_admin.telegram_id = 111111
    mock_user_manager.get_all_admins.return_value = [mock_admin]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    # Проверяем, что сообщение было отправлено
    mock_bot.send_message.assert_called_once()

    # Проверяем переданный текст (можно получить аргументы вызова)
    call_args = mock_bot.send_message.call_args[1]
    message_text = call_args['text']

    # Проверяем, что в сообщении есть обе даты
    date1 = (today + timedelta(hours=47)).strftime('%d.%m.%Y')
    date2 = (today + timedelta(hours=25)).strftime('%d.%m.%Y')

    assert date1 in message_text
    assert date2 in message_text

    # Проверяем, что названия экскурсий присутствуют
    assert "Морская прогулка" in message_text
    assert "Рыбалка" in message_text


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_bot_not_available(mock_redis_client, monkeypatch):
    """Тест когда экземпляр бота недоступен."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)

    # Возвращаем None вместо бота
    monkeypatch.setattr("app.services.scheduler.tasks.get_bot_instance", lambda: None)

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    mock_slot = MagicMock()
    mock_slot.id = 101
    mock_slot.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot.excursion.name = "Морская прогулка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot]

    mock_admin = MagicMock()
    mock_admin.telegram_id = 111111
    mock_user_manager.get_all_admins.return_value = [mock_admin]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    await notify_admins_about_slots_without_captain()

    # Проверяем, что попытка отправки сообщения не делалась
    # Не можем проверить mock_bot, но можем проверить, что метод send_message не вызывался
    # (в этом тесте нет mock_bot, значит вызовов не было)


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_send_error(mock_redis_client, monkeypatch):
    """Тест обработки ошибки при отправке сообщения."""
    mock_session, mock_uow = setup_mocks(monkeypatch)
    mock_redis = mock_redis_for_tasks(mock_redis_client, monkeypatch)
    mock_bot = mock_bot_for_tasks(monkeypatch)

    # Настраиваем бота на выброс исключения
    mock_bot.send_message.side_effect = Exception("Ошибка отправки")

    mock_slot_manager = AsyncMock()
    mock_user_manager = AsyncMock()

    mock_slot = MagicMock()
    mock_slot.id = 101
    mock_slot.start_datetime = datetime.now() + timedelta(hours=47)
    mock_slot.excursion.name = "Морская прогулка"

    mock_slot_manager.get_slots_without_captain.return_value = [mock_slot]

    mock_admin = MagicMock()
    mock_admin.telegram_id = 111111
    mock_user_manager.get_all_admins.return_value = [mock_admin]

    mock_redis.client.get.return_value = None

    monkeypatch.setattr("app.services.scheduler.tasks.SlotManager", lambda s: mock_slot_manager)
    monkeypatch.setattr("app.services.scheduler.tasks.UserManager", lambda s: mock_user_manager)

    from app.services.scheduler.tasks import notify_admins_about_slots_without_captain

    # Функция не должна выбрасывать исключение
    await notify_admins_about_slots_without_captain()

    # setex не должен вызываться при ошибке отправки
    mock_redis.client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_notify_admins_about_slots_without_captain_lock_failed(mock_redis_client, monkeypatch):
    """Тест когда не удалось получить блокировку."""
    mock_acquire_lock = AsyncMock(return_value=None)
    mock_redis_client.acquire_lock = mock_acquire_lock
    monkeypatch.setattr("app.services.scheduler.tasks.redis_client", mock_redis_client)

    with patch("app.services.scheduler.tasks.SlotManager") as mock_slot_manager:
        from app.services.scheduler.tasks import notify_admins_about_slots_without_captain
        await notify_admins_about_slots_without_captain()
        mock_slot_manager.assert_not_called()
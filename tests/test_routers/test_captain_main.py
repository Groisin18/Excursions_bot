"""
Модульные тесты для роутера captain_main.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.routers.captain import captain_main
from app.database.models import (
    SlotStatus, BookingStatus, ClientStatus, UserRole
)


# ===== ФИКСТУРЫ =====

@pytest.fixture
def mock_captain_user():
    """Мок пользователя-капитана."""
    user = MagicMock()
    user.id = 10
    user.telegram_id = 123456
    user.full_name = "Captain Test"
    user.role = UserRole.captain
    return user


@pytest.fixture
def mock_client_user():
    """Мок пользователя-клиента."""
    user = MagicMock()
    user.id = 20
    user.full_name = "Client Test"
    return user


@pytest.fixture
def mock_slot(mock_captain_user):
    """Мок слота экскурсии."""
    slot = MagicMock()
    slot.id = 1
    slot.captain_id = mock_captain_user.id
    slot.start_datetime = datetime(2026, 5, 1, 14, 0)
    slot.end_datetime = datetime(2026, 5, 1, 16, 0)
    slot.status = SlotStatus.scheduled
    slot.max_people = 10
    slot.max_weight = 800
    slot.excursion = MagicMock()
    slot.excursion.name = "Тестовая экскурсия"
    slot.bookings = []
    return slot


@pytest.fixture
def mock_booking(mock_client_user, mock_slot):
    """Мок бронирования."""
    booking = MagicMock()
    booking.id = 100
    booking.slot_id = mock_slot.id
    booking.adult_user = mock_client_user
    booking.adult_user_id = mock_client_user.id
    booking.booking_status = BookingStatus.active
    booking.client_status = ClientStatus.not_arrived
    booking.booking_children = []
    return booking


# ===== ТЕСТЫ КОМАНДЫ /captain =====

class TestCaptainStart:
    """Тесты для входа в капитан-панель."""

    @pytest.mark.asyncio
    async def test_captain_start_success(self, mock_captain_user):
        """Успешный вход в капитан-панель."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.from_user.username = "captain_test"
        message.answer = AsyncMock()

        await captain_main.captain_start(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Панель капитана" in call_args

    @pytest.mark.asyncio
    async def test_captain_start_exception(self):
        """Ошибка при входе в капитан-панель."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.from_user.username = "captain_test"
        # Первый вызов answer() бросает исключение, второй — для ошибки
        message.answer = AsyncMock(side_effect=[
            Exception("Test error"),    # первый вызов — основной
            None                         # второй вызов — в except
        ])

        await captain_main.captain_start(message)

        # Проверяем что было два вызова answer
        assert message.answer.call_count == 2
        # Последний вызов — сообщение об ошибке
        call_args = message.answer.call_args[0][0]
        assert "Ошибка" in call_args


class TestCaptainExit:
    """Тесты для выхода из капитан-панели."""

    @pytest.mark.asyncio
    async def test_captain_exit_success(self):
        """Успешный выход из капитан-панели."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.answer = AsyncMock()

        await captain_main.captain_exit(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "вышли" in call_args.lower()

    @pytest.mark.asyncio
    async def test_captain_exit_exception(self):
        """Ошибка при выходе из капитан-панели."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.answer = AsyncMock(side_effect=Exception("Test error"))

        await captain_main.captain_exit(message)

        message.answer.assert_called()


class TestBackHandler:
    """Тесты для кнопки Назад."""

    @pytest.mark.asyncio
    async def test_back_handler_success(self, mock_state):
        """Успешный возврат в главное меню."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.answer = AsyncMock()
        mock_state.get_state.return_value = None

        await captain_main.back_handler(message, mock_state)

        mock_state.clear.assert_called_once()
        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Главное меню капитана" in call_args


# ===== ТЕСТЫ МОЕ РАСПИСАНИЕ =====

class TestMySchedule:
    """Тесты для отображения расписания капитана."""

    @pytest.mark.asyncio
    async def test_my_schedule_with_slots(self, mock_captain_user, mock_slot):
        """Расписание с назначенными слотами."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = [mock_slot]

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_schedule(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Ваше расписание" in call_args
        assert "Тестовая экскурсия" in call_args

    @pytest.mark.asyncio
    async def test_my_schedule_no_slots(self, mock_captain_user):
        """Расписание без назначенных слотов."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = []

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_schedule(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "нет назначенных" in call_args.lower()

    @pytest.mark.asyncio
    async def test_my_schedule_user_not_found(self):
        """Пользователь не найден."""
        message = AsyncMock()
        message.from_user.id = 999999
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_schedule(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "не найден" in call_args.lower()

    @pytest.mark.asyncio
    async def test_my_schedule_exception(self):
        """Ошибка при получении расписания."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', side_effect=Exception("DB error")), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_schedule(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Ошибка" in call_args


# ===== ТЕСТЫ МОЯ СТАТИСТИКА =====

class TestMyStatistics:
    """Тесты для отображения статистики капитана."""

    @pytest.mark.asyncio
    async def test_my_statistics_success(self, mock_captain_user, mock_slot):
        """Успешное получение статистики."""
        mock_slot.status = SlotStatus.completed
        mock_slot.bookings = []

        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_completed_slots_for_period.return_value = [mock_slot]

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_statistics(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "статистика" in call_args.lower()
        assert "Проведено экскурсий" in call_args

    @pytest.mark.asyncio
    async def test_my_statistics_user_not_found(self):
        """Пользователь не найден при запросе статистики."""
        message = AsyncMock()
        message.from_user.id = 999999
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_statistics(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "не найден" in call_args.lower()

    @pytest.mark.asyncio
    async def test_my_statistics_exception(self):
        """Ошибка при получении статистики."""
        message = AsyncMock()
        message.from_user.id = 123456
        message.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', side_effect=Exception("DB error")), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.my_statistics(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Ошибка" in call_args


# ===== ТЕСТЫ ЗАВЕРШИТЬ ЭКСКУРСИЮ =====

class TestCompleteExcursion:
    """Тесты для завершения экскурсии."""

    @pytest.mark.asyncio
    async def test_complete_excursion_with_slots(self, mock_captain_user, mock_slot):
        """Показ слотов для завершения."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = [mock_slot]

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.complete_excursion(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Выберите экскурсию для завершения" in call_args

    @pytest.mark.asyncio
    async def test_complete_excursion_no_slots(self, mock_captain_user):
        """Нет слотов для завершения."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = []

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.complete_excursion(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Нет экскурсий" in call_args

    @pytest.mark.asyncio
    async def test_process_complete_slot_success(self, mock_captain_user, mock_slot):
        """Успешное завершение слота."""
        callback = AsyncMock()
        callback.from_user.id = mock_captain_user.telegram_id
        callback.data = f"captain_complete_slot:{mock_slot.id}"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_by_id.return_value = mock_slot
        mock_slot_repo.update_status = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_complete_slot(callback)

        callback.answer.assert_called_once()
        mock_slot_repo.update_status.assert_called_once_with(mock_slot.id, SlotStatus.completed)
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "успешно завершена" in call_args

    @pytest.mark.asyncio
    async def test_process_complete_slot_not_found(self):
        """Слот не найден при завершении."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_complete_slot:999"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_by_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_complete_slot(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "не найден" in call_args.lower()

    @pytest.mark.asyncio
    async def test_process_complete_slot_not_captain(self, mock_slot):
        """Капитан не назначен на этот слот."""
        callback = AsyncMock()
        callback.from_user.id = 999999
        callback.data = f"captain_complete_slot:{mock_slot.id}"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_by_id.return_value = mock_slot

        mock_user_repo = AsyncMock()
        another_user = MagicMock()
        another_user.id = 999
        mock_user_repo.get_by_telegram_id.return_value = another_user

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_complete_slot(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "не назначены" in call_args.lower()

    @pytest.mark.asyncio
    async def test_process_complete_slot_exception(self):
        """Ошибка при завершении слота."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_complete_slot:1"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', side_effect=Exception("DB error")), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_complete_slot(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "Ошибка" in call_args


# ===== ТЕСТЫ ОТМЕТИТЬ ПРИБЫТИЕ КЛИЕНТА =====

class TestMarkArrival:
    """Тесты для отметки прибытия клиента."""

    @pytest.mark.asyncio
    async def test_mark_arrival_start_with_slots(self, mock_captain_user, mock_slot):
        """Показ слотов для отметки прибытия."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = [mock_slot]

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.mark_arrival_start(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "Выберите экскурсию для отметки" in call_args

    @pytest.mark.asyncio
    async def test_mark_arrival_start_no_slots(self, mock_captain_user):
        """Нет слотов на сегодня."""
        message = AsyncMock()
        message.from_user.id = mock_captain_user.telegram_id
        message.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = []

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.mark_arrival_start(message)

        message.answer.assert_called_once()
        call_args = message.answer.call_args[0][0]
        assert "нет назначенных" in call_args.lower()

    @pytest.mark.asyncio
    async def test_show_slot_clients_for_arrival(self, mock_slot, mock_booking):
        """Показ клиентов слота для отметки прибытия."""
        mock_slot.bookings = [mock_booking]

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = f"captain_arrival_slot:{mock_slot.id}"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_with_bookings.return_value = mock_slot

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.show_slot_clients_for_arrival(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "Клиенты на экскурсию" in call_args

    @pytest.mark.asyncio
    async def test_show_slot_clients_slot_not_found(self):
        """Слот не найден при показе клиентов."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_arrival_slot:999"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_with_bookings.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.show_slot_clients_for_arrival(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "не найден" in call_args.lower()

    @pytest.mark.asyncio
    async def test_show_slot_clients_no_bookings(self, mock_slot):
        """Нет бронирований на слоте."""
        mock_slot.bookings = []

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = f"captain_arrival_slot:{mock_slot.id}"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_with_bookings.return_value = mock_slot

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.show_slot_clients_for_arrival(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "нет записанных" in call_args.lower()

    @pytest.mark.asyncio
    async def test_process_mark_arrived_success(self, mock_booking, mock_slot):
        """Успешная отметка прибытия клиента."""
        mock_booking.client_status = ClientStatus.not_arrived
        mock_slot.bookings = [mock_booking]

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = f"captain_mark_arrived:{mock_booking.id}:{mock_slot.id}"
        callback.message = AsyncMock()
        callback.message.edit_reply_markup = AsyncMock()
        callback.answer = AsyncMock()

        mock_booking_repo = AsyncMock()
        mock_booking_repo.get_by_id.return_value = mock_booking
        mock_booking_repo.update_status = AsyncMock()

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_with_bookings.return_value = mock_slot

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.BookingRepository', return_value=mock_booking_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_mark_arrived(callback)

        callback.answer.assert_called_once()
        mock_booking_repo.update_status.assert_called_once_with(
            booking_id=mock_booking.id,
            client_status=ClientStatus.arrived
        )
        callback.message.edit_reply_markup.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_mark_arrived_already_arrived(self, mock_booking):
        """Прибытие уже отмечено."""
        mock_booking.client_status = ClientStatus.arrived

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = f"captain_mark_arrived:{mock_booking.id}:1"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_booking_repo = AsyncMock()
        mock_booking_repo.get_by_id.return_value = mock_booking

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.BookingRepository', return_value=mock_booking_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_mark_arrived(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "уже отмечено" in call_args.lower()

    @pytest.mark.asyncio
    async def test_process_mark_arrived_booking_not_found(self):
        """Бронирование не найдено."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_mark_arrived:999:1"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_booking_repo = AsyncMock()
        mock_booking_repo.get_by_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.BookingRepository', return_value=mock_booking_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_mark_arrived(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "не найдено" in call_args.lower()

    @pytest.mark.asyncio
    async def test_process_mark_arrived_exception(self):
        """Ошибка при отметке прибытия."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_mark_arrived:100:1"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.BookingRepository', side_effect=Exception("DB error")), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.process_mark_arrived(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "Ошибка" in call_args


# ===== ТЕСТЫ ВОЗВРАТА ИЗ CALLBACK =====

class TestCallbackNavigation:
    """Тесты навигации по колбэкам."""

    @pytest.mark.asyncio
    async def test_callback_back_to_menu(self, mock_state):
        """Возврат в главное меню из колбэка."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_back_to_menu"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        await captain_main.callback_back_to_menu(callback, mock_state)

        callback.answer.assert_called_once()
        mock_state.clear.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "Главное меню капитана" in call_args

    @pytest.mark.asyncio
    async def test_back_to_slots_selection(self, mock_captain_user, mock_slot):
        """Возврат к выбору слота."""
        callback = AsyncMock()
        callback.from_user.id = mock_captain_user.telegram_id
        callback.data = "captain_back_to_slots"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = mock_captain_user

        mock_slot_repo = AsyncMock()
        mock_slot_repo.get_captain_slots_by_id.return_value = [mock_slot]

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.SlotRepository', return_value=mock_slot_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.back_to_slots_selection(callback)

        callback.answer.assert_called_once()
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args[0][0]
        assert "Выберите экскурсию для отметки" in call_args

    @pytest.mark.asyncio
    async def test_back_to_slots_user_not_found(self):
        """Пользователь не найден при возврате к слотам."""
        callback = AsyncMock()
        callback.from_user.id = 999999
        callback.data = "captain_back_to_slots"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_telegram_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', return_value=mock_user_repo), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.back_to_slots_selection(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "не найден" in call_args.lower()

    @pytest.mark.asyncio
    async def test_callback_back_to_menu_exception(self, mock_state):
        """Ошибка при возврате в меню."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_back_to_menu"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_state.clear = AsyncMock(side_effect=Exception("State error"))

        await captain_main.callback_back_to_menu(callback, mock_state)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "ошибка" in call_args.lower()

    @pytest.mark.asyncio
    async def test_back_to_slots_exception(self):
        """Ошибка при возврате к выбору слота."""
        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.data = "captain_back_to_slots"
        callback.message = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session

        with patch('app.routers.captain.captain_main.UserRepository', side_effect=Exception("DB error")), \
             patch('app.routers.captain.captain_main.async_session', return_value=mock_session):

            await captain_main.back_to_slots_selection(callback)

        callback.answer.assert_called_once()
        callback.message.answer.assert_called_once()
        call_args = callback.message.answer.call_args[0][0]
        assert "Ошибка" in call_args
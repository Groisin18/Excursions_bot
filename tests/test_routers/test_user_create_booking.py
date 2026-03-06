"""
Модульные тесты для роутера user_create_booking.
Тестирование процесса бронирования с блокировками Redis.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.user import user_create_booking
from app.user_panel.states import UserBookingStates
from app.database.models import Booking


@pytest.mark.asyncio
async def test_start_booking_success(
    mock_callback_query,
    mock_state,
    test_slot,
    test_data,
    test_excursion,
    mock_redis_client,
    mock_user_repository,
    mock_slot_repository,
    mock_booking_repository,
    mock_excursion_repository,
    mock_slot_manager,
    mock_session
):
    """Тест успешного начала бронирования когда слот свободен."""
    # Настройка
    mock_callback_query.data = f"public_book_slot:{test_slot.id}"
    mock_callback_query.message = AsyncMock()

    # Настраиваем Redis - слот свободен
    mock_redis_client.is_locked = AsyncMock(return_value=False)

    # Настраиваем моки репозиториев
    mock_user_repository.get_by_telegram_id.return_value = test_data["client"]
    mock_user_repository.user_has_children.return_value = False
    mock_slot_repository.get_by_id.return_value = test_slot
    mock_booking_repository.get_user_active_for_slot.return_value = None
    mock_excursion_repository.get_by_id.return_value = test_excursion
    mock_slot_manager.get_booked_places.return_value = 3  # 3 места занято из 10
    mock_slot_manager.get_current_weight.return_value = 200  # 200 кг занято

    # Патчим все репозитории
    with patch('app.routers.user.user_create_booking.UserRepository', return_value=mock_user_repository), \
         patch('app.routers.user.user_create_booking.SlotRepository', return_value=mock_slot_repository), \
         patch('app.routers.user.user_create_booking.BookingRepository', return_value=mock_booking_repository), \
         patch('app.routers.user.user_create_booking.ExcursionRepository', return_value=mock_excursion_repository), \
         patch('app.routers.user.user_create_booking.SlotManager', return_value=mock_slot_manager), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        # Вызов
        await user_create_booking.start_booking(mock_callback_query, mock_state)

        # Проверяем, что процесс продолжился
        mock_callback_query.answer.assert_called_once()  # Ответ на callback
        mock_state.update_data.assert_called_once()  # Данные сохранены
        mock_state.set_state.assert_called_once_with(UserBookingStates.checking_weight)  # Состояние изменено


@pytest.mark.asyncio
async def test_start_booking_slot_locked(
    mock_callback_query,
    mock_state,
    test_slot,
    mock_redis_client
):
    """Тест начала бронирования когда слот заблокирован другим пользователем."""
    mock_callback_query.data = f"public_book_slot:{test_slot.id}"

    # Важно! НЕ создаем новый message, а используем существующий
    # просто убеждаемся что у него есть метод answer
    mock_callback_query.message.answer = AsyncMock()

    # Настраиваем Redis - слот заблокирован
    mock_redis_client.is_locked = AsyncMock(return_value=True)

    # Вызов
    await user_create_booking.start_booking(mock_callback_query, mock_state)

    # Проверяем, что callback.answer был вызван
    mock_callback_query.answer.assert_called_once()

    # Проверяем, что message.answer был вызван с предупреждением
    mock_callback_query.message.answer.assert_called_once_with(
        "Этот слот сейчас обрабатывается другим пользователем. Попробуйте через минуту.",
        reply_markup=user_create_booking.kb.public_schedule_options()
    )

    # Проверяем, что состояние не изменилось
    mock_state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_start_booking_slot_not_found(
    mock_callback_query,
    mock_state,
    mock_redis_client,
    mock_slot_repository,
    mock_session
):
    """Тест начала бронирования с несуществующим слотом."""
    mock_callback_query.data = "public_book_slot:99999"
    mock_callback_query.message = AsyncMock()

    # Настраиваем Redis
    mock_redis_client.is_locked = AsyncMock(return_value=False)

    # Мокаем SlotRepository чтобы возвращал None
    mock_slot_repository.get_by_id.return_value = None

    with patch('app.routers.user.user_create_booking.SlotRepository', return_value=mock_slot_repository), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.start_booking(mock_callback_query, mock_state)

    # Проверяем сообщение об ошибке
    mock_callback_query.message.answer.assert_called_once()
    assert "не найден" in mock_callback_query.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_start_booking_user_not_found(
    mock_callback_query,
    mock_state,
    test_slot,
    mock_redis_client,
    mock_user_repository,
    mock_slot_repository,
    mock_session
):
    """Тест начала бронирования когда пользователь не найден."""
    mock_callback_query.data = f"public_book_slot:{test_slot.id}"
    mock_callback_query.message = AsyncMock()

    # Настраиваем Redis
    mock_redis_client.is_locked = AsyncMock(return_value=False)

    # Настраиваем моки
    mock_user_repository.get_by_telegram_id.return_value = None
    mock_slot_repository.get_by_id.return_value = test_slot

    with patch('app.routers.user.user_create_booking.UserRepository', return_value=mock_user_repository), \
         patch('app.routers.user.user_create_booking.SlotRepository', return_value=mock_slot_repository), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.start_booking(mock_callback_query, mock_state)

    # Проверяем сообщение о необходимости регистрации
    mock_callback_query.message.answer.assert_called_once()
    assert "не зарегистрированы" in mock_callback_query.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_start_booking_no_free_places(
    mock_callback_query,
    mock_state,
    test_slot,
    test_data,
    mock_redis_client,
    mock_user_repository,
    mock_slot_repository,
    mock_slot_manager,
    mock_session
):
    """Тест начала бронирования когда нет свободных мест."""
    mock_callback_query.data = f"public_book_slot:{test_slot.id}"
    mock_callback_query.message = AsyncMock()

    # Настраиваем Redis
    mock_redis_client.is_locked = AsyncMock(return_value=False)

    # Настраиваем моки
    mock_user_repository.get_by_telegram_id.return_value = test_data["client"]
    mock_slot_repository.get_by_id.return_value = test_slot
    mock_slot_manager.get_booked_places.return_value = test_slot.max_people  # Все места заняты

    with patch('app.routers.user.user_create_booking.UserRepository', return_value=mock_user_repository), \
         patch('app.routers.user.user_create_booking.SlotRepository', return_value=mock_slot_repository), \
         patch('app.routers.user.user_create_booking.SlotManager', return_value=mock_slot_manager), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.start_booking(mock_callback_query, mock_state)

    # Проверяем сообщение об отсутствии мест
    mock_callback_query.message.answer.assert_called_once()
    assert "нет свободных мест" in mock_callback_query.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_confirm_booking_success(
    mock_callback_query,
    mock_state,
    test_slot,
    test_data,
    mock_redis_client,
    mock_booking_manager,
    mock_session,
    mock_uow
):
    """Тест успешного подтверждения бронирования."""
    mock_callback_query.data = "confirm_booking"
    mock_callback_query.message = AsyncMock()

    # Настройка state
    state_data = {
        "slot_id": test_slot.id,
        "user_id": test_data["client"].id,
        "adult_price": 1000,
        "final_price": 1000,
        "children_prices": [],
        "total_weight": 75,
        "adult_weight": 75,
        "children_weights": {}
    }
    mock_state.get_data.return_value = state_data

    # Настройка мока бронирования
    mock_booking = MagicMock(spec=Booking)
    mock_booking.id = 1
    mock_booking_manager.create_booking.return_value = (mock_booking, "")
    mock_booking_manager.promo_repo = AsyncMock()

    with patch('app.routers.user.user_create_booking.BookingManager', return_value=mock_booking_manager), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session), \
         patch('app.routers.user.user_create_booking.UnitOfWork', return_value=mock_uow):

        await user_create_booking.confirm_booking(mock_callback_query, mock_state)

        # Проверяем, что бронирование создано
        mock_booking_manager.create_booking.assert_called_once()
        mock_callback_query.message.answer.assert_called_once()
        assert "Бронирование №1 создано" in mock_callback_query.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_confirm_booking_lock_timeout(
    mock_callback_query,
    mock_state,
    test_slot,
    monkeypatch
):
    """Тест таймаута при получении блокировки."""
    mock_callback_query.data = "confirm_booking"
    mock_callback_query.message = AsyncMock()

    state_data = {
        "slot_id": test_slot.id,
        "user_id": 1,
        "final_price": 1000
    }
    mock_state.get_data.return_value = state_data

    # Создаем контекстный менеджер, который выбрасывает TimeoutError
    class TimeoutLock:
        async def __aenter__(self):
            raise TimeoutError()
        async def __aexit__(self, *args):
            pass

    # Мокаем redis_client.lock чтобы он возвращал наш контекстный менеджер
    mock_redis = MagicMock()
    mock_redis.lock = MagicMock(return_value=TimeoutLock())
    monkeypatch.setattr("app.routers.user.user_create_booking.redis_client", mock_redis)

    await user_create_booking.confirm_booking(mock_callback_query, mock_state)

    # Проверяем сообщение о таймауте
    mock_callback_query.message.answer.assert_called_once()
    args, kwargs = mock_callback_query.message.answer.call_args
    assert "много желающих" in args[0]
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_booking_no_slot_id(
    mock_callback_query,
    mock_state
):
    """Тест подтверждения без slot_id в state."""
    mock_callback_query.data = "confirm_booking"
    mock_callback_query.message = AsyncMock()

    mock_state.get_data.return_value = {}  # пустой state

    await user_create_booking.confirm_booking(mock_callback_query, mock_state)

    # Проверяем сообщение об ошибке
    mock_callback_query.message.answer.assert_called_once_with(
        "Ошибка: данные слотов устарели. Начните бронирование заново.",
        reply_markup=user_create_booking.kb.main
    )
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_booking_creation_failed(
    mock_callback_query,
    mock_state,
    test_slot,
    test_data,
    mock_booking_manager,
    mock_session,
    mock_uow,
    monkeypatch
):
    """Тест ошибки при создании бронирования."""
    mock_callback_query.data = "confirm_booking"
    mock_callback_query.message = AsyncMock()

    state_data = {
        "slot_id": test_slot.id,
        "user_id": test_data["client"].id,
        "adult_price": 1000,
        "final_price": 1000,
        "children_prices": [],
        "total_weight": 75,
        "adult_weight": 75,
        "children_weights": {}
    }
    mock_state.get_data.return_value = state_data

    # Мокаем успешную блокировку
    class SuccessLock:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    mock_redis = MagicMock()
    mock_redis.lock = MagicMock(return_value=SuccessLock())
    monkeypatch.setattr("app.routers.user.user_create_booking.redis_client", mock_redis)

    # Мокаем ошибку создания бронирования
    mock_booking_manager.create_booking.return_value = (None, "Мест нет")

    with patch('app.routers.user.user_create_booking.BookingManager', return_value=mock_booking_manager), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session), \
         patch('app.routers.user.user_create_booking.UnitOfWork', return_value=mock_uow):

        await user_create_booking.confirm_booking(mock_callback_query, mock_state)

        # Проверяем сообщение об ошибке
        mock_callback_query.message.answer.assert_called_once_with(
            "Ошибка при создании бронирования: Мест нет",
            reply_markup=user_create_booking.kb.main
        )
        mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_check_adult_weight_with_existing_weight(
    mock_callback_query,
    mock_state,
    test_slot,
    mock_user_repository,
    mock_slot_manager,
    mock_session
):
    """Тест проверки веса когда вес уже есть в профиле."""
    mock_callback_query.data = "confirm_start_booking"
    mock_callback_query.message = AsyncMock()
    mock_callback_query.message.edit_text = AsyncMock()

    state_data = {
        "slot_id": test_slot.id,
        "user_id": 1,
        "adult_weight": 75,
        "available_weight": 800,
        "max_weight": 800,
        "user_has_children": False
    }
    mock_state.get_data.return_value = state_data

    # Мокаем user_repo.get_children_users
    mock_user_repository.get_children_users.return_value = []

    with patch('app.routers.user.user_create_booking.SlotManager', return_value=mock_slot_manager), \
         patch('app.routers.user.user_create_booking.UserRepository', return_value=mock_user_repository), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.check_adult_weight(mock_callback_query, mock_state)

        # Проверяем обновление доступного веса
        mock_state.update_data.assert_called_with({
            "available_weight": 800 - 75,
            "total_weight": 75,
            "adults_count": 1
        })
        mock_state.set_state.assert_called_with(UserBookingStates.selecting_participants)


@pytest.mark.asyncio
async def test_check_adult_weight_exceeds_limit(
    mock_callback_query,
    mock_state,
    test_slot,
    mock_slot_manager,
    mock_session
):
    """Тест превышения допустимого веса."""
    mock_callback_query.data = "confirm_start_booking"
    mock_callback_query.message = AsyncMock()

    state_data = {
        "slot_id": test_slot.id,
        "user_id": 1,
        "adult_weight": 800,
        "available_weight": 700,
        "max_weight": 800
    }
    mock_state.get_data.return_value = state_data

    # Мокаем slot_manager.get_current_weight
    mock_slot_manager.get_current_weight.return_value = 100

    with patch('app.routers.user.user_create_booking.SlotManager', return_value=mock_slot_manager), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.check_adult_weight(mock_callback_query, mock_state)

        # Проверяем сообщение о превышении веса
        mock_callback_query.message.answer.assert_called_once()
        assert "Превышение" in mock_callback_query.message.answer.call_args[0][0]
        mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_booking_during_process(
    mock_callback_query,
    mock_state
):
    """Тест отмены бронирования пользователем."""
    mock_callback_query.data = "cancel_booking"
    mock_callback_query.message = AsyncMock()

    await user_create_booking.cancel_booking(mock_callback_query, mock_state)

    mock_state.clear.assert_called_once()
    mock_callback_query.message.answer.assert_called_once_with(
        "Бронирование отменено.",
        reply_markup=user_create_booking.kb.main
    )


@pytest.mark.asyncio
async def test_handle_booking_alone(
    mock_callback_query,
    mock_state
):
    """Тест выбора 'Записываюсь только я'."""
    mock_callback_query.data = "booking_just_me"
    mock_callback_query.message = AsyncMock()

    await user_create_booking.handle_booking_alone(mock_callback_query, mock_state)

    mock_state.update_data.assert_called_with({
        "children_ids": [],
        "children_weights": {},
        "total_children": 0,
        "selected_participants": "alone"
    })
    mock_state.set_state.assert_called_with(UserBookingStates.applying_promo_code)
    mock_callback_query.message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_skip_promo_code(
    mock_callback_query,
    mock_state
):
    """Тест пропуска ввода промокода."""
    mock_callback_query.data = "skip_promo_code"
    mock_callback_query.message = AsyncMock()

    mock_state.get_data.return_value = {"adult_price": 1000}

    # Мокаем calculate_total_from_callback так как это внутренняя функция
    with patch.object(user_create_booking, 'calculate_total_from_callback', AsyncMock()) as mock_calc:
        await user_create_booking.skip_promo_code(mock_callback_query, mock_state)

        mock_state.update_data.assert_called_with({"promo_code": None, "promo_discount": 0})
        mock_state.set_state.assert_called_with(UserBookingStates.calculating_total)
        mock_calc.assert_called_once_with(mock_callback_query, mock_state)


@pytest.mark.asyncio
async def test_process_promo_code_valid(
    mock_state,
    mock_session,
    mock_promo_repository,
    monkeypatch
):
    """Тест обработки валидного промокода."""
    mock_message = AsyncMock()
    mock_message.text = "TEST123"
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_state.get_data.return_value = {}

    # Важно: промокод должен быть валидным
    mock_promo = MagicMock()
    mock_promo.code = "TEST123"
    mock_promo.discount_type = MagicMock()  # Убедитесь, что .value работает
    mock_promo.discount_type.value = "percent"
    mock_promo.discount_value = 10
    mock_promo.id = 1
    mock_promo_repository.get_valid_by_code.return_value = mock_promo

    with patch('app.routers.user.user_create_booking.PromoCodeRepository', return_value=mock_promo_repository), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session), \
         patch.object(user_create_booking, 'calculate_total_from_message', AsyncMock()) as mock_calc:

        await user_create_booking.process_promo_code(mock_message, mock_state)

        # Проверяем, что update_data был вызван
        mock_state.update_data.assert_called_once()
        mock_state.set_state.assert_called_with(UserBookingStates.calculating_total)
        mock_calc.assert_called_once_with(mock_message, mock_state)


@pytest.mark.asyncio
async def test_process_promo_code_invalid(
    mock_state,
    mock_session,
    mock_promo_repository
):
    """Тест обработки невалидного промокода."""
    mock_message = AsyncMock()
    mock_message.text = "INVALID"
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_state.get_data.return_value = {}

    # Настраиваем мок - промокод не найден
    mock_promo_repository.get_valid_by_code.return_value = None

    with patch('app.routers.user.user_create_booking.PromoCodeRepository', return_value=mock_promo_repository), \
         patch('app.routers.user.user_create_booking.async_session', return_value=mock_session):

        await user_create_booking.process_promo_code(mock_message, mock_state)

        # Проверяем сообщение о недействительном промокоде
        mock_message.answer.assert_called_once()
        assert "недействителен" in mock_message.answer.call_args[0][0]
"""Фикстуры для моков репозиториев и менеджеров."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_user_repository():
    """Мок для UserRepository."""
    mock = AsyncMock()
    mock.get_by_telegram_id = AsyncMock()
    mock.get_children_users = AsyncMock(return_value=[])
    mock.user_has_children = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_slot_repository():
    """Мок для SlotRepository."""
    mock = AsyncMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def mock_booking_repository():
    """Мок для BookingRepository."""
    mock = AsyncMock()
    mock.get_user_active_for_slot = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_excursion_repository():
    """Мок для ExcursionRepository."""
    mock = AsyncMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def mock_slot_manager():
    """Мок для SlotManager."""
    mock = AsyncMock()
    mock.get_booked_places = AsyncMock(return_value=0)
    mock.get_current_weight = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def mock_booking_manager():
    """Мок для BookingManager."""
    mock = AsyncMock()
    mock.create_booking = AsyncMock()
    mock.promo_repo = AsyncMock()
    return mock


@pytest.fixture
def mock_promo_repository():
    """Мок для PromoCodeRepository."""
    mock = AsyncMock()
    mock.get_valid_by_code = AsyncMock()
    return mock


@pytest.fixture
def mock_session():
    """Мок для сессии БД."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock()
    return mock


@pytest.fixture
def mock_uow():
    """Мок для UnitOfWork."""
    mock = AsyncMock()
    return mock
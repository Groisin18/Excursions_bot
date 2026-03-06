"""Фикстуры с тестовыми данными."""

import pytest
import sys
from datetime import datetime, timedelta
from sqlalchemy import text
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import User, UserRole, Excursion, ExcursionSlot, SlotStatus


@pytest.fixture
async def test_data(db_session):
    """Создает тестовых пользователей."""
    print("\n=== ЗАПОЛНЯЕМ ТЕСТОВЫМИ ДАННЫМИ ===")

    await db_session.execute(text("DELETE FROM users"))
    await db_session.commit()

    admin = User(
        telegram_id=1001,
        full_name="Admin Test",
        phone_number="+79001112233",
        role=UserRole.admin
    )

    captain = User(
        telegram_id=1002,
        full_name="Captain Test",
        phone_number="+79002223344",
        role=UserRole.captain
    )

    client = User(
        telegram_id=1003,
        full_name="Client Test",
        phone_number="+79003334455",
        role=UserRole.client,
        weight=75
    )

    db_session.add_all([admin, captain, client])
    await db_session.flush()

    return {
        "admin": admin,
        "captain": captain,
        "client": client
    }


@pytest.fixture
async def test_excursion(db_session):
    """Создает тестовую экскурсию."""
    excursion = Excursion(
        name="Тестовая экскурсия",
        description="Описание",
        base_price=1000,
        base_duration_minutes=120,
        is_active=True
    )
    db_session.add(excursion)
    await db_session.flush()
    return excursion


@pytest.fixture
async def test_slot(db_session, test_excursion, test_data):
    """Создает тестовый слот."""
    start = datetime.now() + timedelta(days=1)
    slot = ExcursionSlot(
        excursion_id=test_excursion.id,
        captain_id=test_data["captain"].id,
        start_datetime=start,
        end_datetime=start + timedelta(minutes=test_excursion.base_duration_minutes),
        max_people=10,
        max_weight=800,
        status=SlotStatus.scheduled
    )
    db_session.add(slot)
    await db_session.flush()
    return slot
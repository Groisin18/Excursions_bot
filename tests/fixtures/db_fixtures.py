"""Фикстуры для работы с базой данных."""

import pytest
import asyncio
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import Base


@pytest.fixture(scope="session")
def event_loop_policy():
    """Устанавливаем политику event loop для Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    print(f"\n=== СОЗДАЕМ ТЕСТОВУЮ БД: {db_path} ===")
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        poolclass=NullPool
    )

    async with engine.begin() as conn:
        print("--- Создаем таблицы ---")
        await conn.run_sync(Base.metadata.create_all)
        print("--- Таблицы созданы ---")

    yield engine

    await engine.dispose()
    try:
        os.unlink(db_path)
        print(f"--- Тестовая БД удалена: {db_path} ---")
    except:
        pass


@pytest.fixture
async def db_session(async_engine):
    """Фикстура для тестовой сессии БД."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
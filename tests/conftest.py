import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Добавляем корень проекта в PYTHONPATH для импортов
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.models import Base, DatabaseConfig


# ========== Фикстуры для базы данных ==========
@pytest.fixture(scope="session")
def event_loop():
    """Создаем event loop для всей сессии тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    """
    Создает асинхронный движок для тестовой БД.
    Используем SQLite в памяти для скорости.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=DatabaseConfig.POOL_CLASS
    )

    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """
    Фикстура для тестовой сессии БД.
    Каждый тест получает чистую сессию с откатом транзакции.
    """
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        try:
            yield session
        finally:
            # Откатываем транзакцию, чтобы не сохранять изменения
            await session.rollback()
            await session.close()


# ========== Фикстуры для AIOGram ==========
@pytest.fixture
def mock_bot():
    """Мок для объекта бота."""
    bot = AsyncMock()
    bot.token = "test:token"
    bot.default = MagicMock()
    return bot


@pytest.fixture
def mock_dp():
    """Мок для диспетчера."""
    dp = AsyncMock()
    dp.storage = AsyncMock()
    return dp


@pytest.fixture
def mock_message():
    """Мок для сообщения Telegram."""
    message = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 123456
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.from_user.username = "test_user"
    message.chat = MagicMock()
    message.chat.id = 123456
    message.text = "test message"
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query():
    """Мок для callback-запроса."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = 123456
    callback.message = mock_message()
    callback.data = "test_callback"
    callback.answer = AsyncMock()
    return callback


# ========== Фикстура для DatabaseManager ==========
@pytest.fixture
async def db_manager(db_session):
    """Создает экземпляр DatabaseManager с тестовой сессией."""
    from app.database.requests import DatabaseManager
    return DatabaseManager(db_session)


# ========== Настройки pytest ==========
def pytest_sessionfinish(session, exitstatus):
    """Действия после завершения всех тестов."""
    # Можно добавить логирование или очистку
    pass


def pytest_configure(config):
    """Конфигурация pytest перед запуском тестов."""
    # Добавляем маркеры для удобной категоризации тестов
    config.addinivalue_line(
        "markers",
        "integration: тесты, требующие реальной БД или внешних сервисов"
    )
    config.addinivalue_line(
        "markers",
        "slow: медленные тесты (например, с сетевыми запросами)"
    )
    config.addinivalue_line(
        "markers",
        "database: тесты, работающие с базой данных"
    )

def pytest_collection_modifyitems(items):
    """Изменяем имена тестов для лучшего отображения."""
    for item in items:
        # Убираем префиксы классов в именах тестов
        if hasattr(item, 'cls') and item.cls:
            item._nodeid = item.nodeid.replace(f"{item.cls.__name__}.", "")
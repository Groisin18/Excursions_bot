import asyncio
import sys
import warnings
import pytest

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ========== НАСТРОЙКА ПУТЕЙ ИМПОРТА ==========
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.database.models import Base, DatabaseConfig, User, UserRole
    from app.database.unit_of_work import UnitOfWork
    from app.database.repositories.user_repository import UserRepository
    from app.database.managers.user_manager import UserManager

    from app.middlewares.admin_middleware import AdminMiddleware
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path}")
    raise



# ========== ГЛОБАЛЬНЫЕ ПРОВЕРКИ БЕЗОПАСНОСТИ ==========

def pytest_configure(config):
    """Конфигурация pytest перед запуском тестов."""

    # Проверка безопасности: предупреждение о production БД
    import os
    if os.path.exists("database.db"):
        warnings.warn(
            "Обнаружен файл database.db. Убедитесь, что тесты используют :memory: БД, а не production.",
            RuntimeWarning
        )

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


# ========== Фикстуры для базы данных ==========

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
    """
    Создает асинхронный движок для тестовой БД.
    Используем SQLite в памяти для скорости и изоляции.
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
def mock_state():
    """Мок для FSMContext."""
    state = AsyncMock()
    state.set_state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    return state


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


# ========== Фикстура для Database ==========

@pytest.fixture
async def repos(db_session):
    """Создает все репозитории и менеджеры с тестовой сессией."""
    class DatabaseFixtures:
        def __init__(self, session):
            from app.database.repositories import (
                UserRepository, ExcursionRepository, SlotRepository,
                BookingRepository, PromoCodeRepository, PaymentRepository,
                NotificationRepository
            )
            from app.database.managers import (
                UserManager, SlotManager, BookingManager,
                SalaryManager, StatisticsManager
            )
            from app.database.unit_of_work import UnitOfWork

            # Репозитории
            self.users = UserRepository(session)
            self.excursions = ExcursionRepository(session)
            self.slots = SlotRepository(session)
            self.bookings = BookingRepository(session)
            self.promocodes = PromoCodeRepository(session)
            self.payments = PaymentRepository(session)
            self.notifications = NotificationRepository(session)

            # Менеджеры
            self.user_manager = UserManager(session)
            self.slot_manager = SlotManager(session)
            self.booking_manager = BookingManager(session)
            self.salary_manager = SalaryManager(session)
            self.statistics_manager = StatisticsManager(session)

            # Unit of Work
            self.uow = UnitOfWork(session)

    return DatabaseFixtures(db_session)


# Фикстура для заполнения тестовыми данными
@pytest.fixture
async def test_data(db_session):
    """
    Создает тестовые данные в БД.
    Использует flush() вместо commit() для изоляции тестов.
    """
    # Создаем тестовых пользователей
    admin = User(
        telegram_id=1001,
        name="Admin",
        surname="Test",
        phone="+79001112233",
        role=UserRole.admin
    )

    captain = User(
        telegram_id=1002,
        name="Captain",
        surname="Test",
        phone="+79002223344",
        role=UserRole.captain
    )

    client = User(
        telegram_id=1003,
        name="Client",
        surname="Test",
        phone="+79003334455",
        role=UserRole.client
    )

    db_session.add_all([admin, captain, client])
    await db_session.flush()  # Используем flush вместо commit для изоляции

    return {
        "admin": admin,
        "captain": captain,
        "client": client
    }


# Фикстура для middleware
@pytest.fixture
def admin_middleware():
    """Создает экземпляр AdminMiddleware для тестов."""
    return AdminMiddleware()


# ========== Настройки pytest ==========

def pytest_sessionfinish(session, exitstatus):
    """Действия после завершения всех тестов."""
    pass


def pytest_collection_modifyitems(items):
    """Изменяем имена тестов для лучшего отображения."""
    for item in items:
        if hasattr(item, 'cls') and item.cls:
            item._nodeid = item.nodeid.replace(f"{item.cls.__name__}.", "")
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """Конфигурация базы данных для телеграм-бота"""

    DB_URL = 'sqlite+aiosqlite:///database.db'
    CONNECT_ARGS = {
        'check_same_thread': False,
        'timeout': 15,
    }


engine = create_async_engine(
    url=DatabaseConfig.DB_URL,
    echo=False,  # True только для отладки SQL
    poolclass=NullPool,
    connect_args=DatabaseConfig.CONNECT_ARGS,
    execution_options={
        "timeout": 15
    }
)


async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

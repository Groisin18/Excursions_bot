"""
Проверка целостности базы данных
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

async def check_database_integrity():
    """Проверить целостность базы данных"""
    DATABASE_URL = "sqlite+aiosqlite:///database.db"

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    try:
        async with engine.connect() as conn:
            # 1. Проверка целостности SQLite
            logger.info("Проверка целостности базы данных...")

            result = await conn.execute(text("PRAGMA integrity_check"))
            integrity = result.scalar()
            logger.info(f"Результат проверки целостности: {integrity}")

            # 2. Проверка внешних ключей
            result = await conn.execute(text("PRAGMA foreign_key_check"))
            foreign_keys = result.fetchall()

            if foreign_keys:
                logger.warning(f"Найдены проблемы с внешними ключами: {foreign_keys}")
            else:
                logger.info("Внешние ключи в порядке")

            # 3. Статистика таблиц
            logger.info("Статистика таблиц:")

            tables_result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))
            tables = tables_result.fetchall()

            for table in tables:
                table_name = table[0]
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = count_result.scalar()

                # Получаем информацию о колонках
                columns_result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = len(columns_result.fetchall())

                logger.info(f"  {table_name}: {count} записей, {columns} колонок")

            # 4. Проверка пользователей по ролям
            logger.info("Статистика пользователей по ролям:")

            roles_result = await conn.execute(text(
                "SELECT role, COUNT(*) FROM users GROUP BY role"
            ))
            roles = roles_result.fetchall()

            for role, count in roles:
                logger.info(f"  {role}: {count} пользователей")

            # 5. Проверка активных бронирований
            logger.info("Активные бронирования:")

            bookings_result = await conn.execute(text(
                "SELECT COUNT(*) FROM bookings WHERE booking_status = 'active'"
            ))
            active_bookings = bookings_result.scalar()
            logger.info(f"  Активных бронирований: {active_bookings}")

    except Exception as e:
        logger.error(f"Ошибка при проверке целостности: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_database_integrity())
import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.routers import setup_routers
from app.database.models import init_models
from app.database.migrations.check_integrity import check_database_integrity
from app.utils.logging_config import setup_logging

load_dotenv()

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL').upper()
ENABLE_CONSOLE_LOGGING = os.getenv('ENABLE_CONSOLE_LOGGING').lower() == 'true'
ENABLE_FILE_LOGGING = os.getenv('ENABLE_FILE_LOGGING').lower() == 'true'
LOG_DIR = os.getenv('LOG_DIR')
ROTATION_MAX_SIZE_MB = int(os.getenv('ROTATION_MAX_SIZE_MB'))
ROTATION_BACKUP_COUNT = int(os.getenv('ROTATION_BACKUP_COUNT'))

logger = setup_logging(
    level=LOG_LEVEL,
    console=ENABLE_CONSOLE_LOGGING,
    file_logging=ENABLE_FILE_LOGGING,
    log_dir=LOG_DIR,
    max_size_mb=ROTATION_MAX_SIZE_MB,
    backup_count=ROTATION_BACKUP_COUNT
)

# Создание бота
bot = Bot(
    token=os.getenv('TG_TOKEN'),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

async def main():
    logger.info("Запуск бота...")

    logger.debug("Настройка роутеров...")
    setup_routers(dp)

    dp.startup.register(startup)
    dp.shutdown.register(shutdown)

    logger.debug("Запуск polling...")
    await dp.start_polling(bot)

async def startup(dispatcher: Dispatcher):
    """Обработчик запуска бота"""
    logger.info("Инициализация базы данных...")
    try:
        await init_models()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}", exc_info=True)
        raise

    try:
        logger.info("Проверка целостности базы данных...")
        await check_database_integrity()
        logger.info("Проверка целостности завершена")
    except Exception as e:
        logger.warning(f"Проверка целостности пропущена: {e}")

    logger.info('Бот запущен!')
    print('Бот запущен!')

async def shutdown(dispatcher: Dispatcher):
    """Обработчик остановки бота"""
    logger.info('Бот останавливается...')
    logger.info("Закрытие соединений...")
    logger.info('Бот остановлен.')
    print('Бот остановлен.')

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Приложение завершило работу")
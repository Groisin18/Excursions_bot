"""
Настройки логирования
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(
    level: str = "INFO",
    console: bool = False,
    file_logging: bool = True,
    log_dir: str = "logs",
    max_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка логирования

    Args:
        level: уровень логирования
        console: включить вывод в консоль
        file_logging: включить запись в файл
        log_dir: директория для логов
        max_size_mb: максимальный размер файла в МБ
        backup_count: количество бэкапов

    Returns:
        Логгер приложения
    """

    # Уровень логирования
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Форматтер
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Очищаем обработчики у корневого логгера
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.propagate = False

    # Создаем основной логгер приложения
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)
    app_logger.propagate = False
    app_logger.handlers.clear()

    # Создаем директорию для логов
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Консольный обработчик
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    # Файловые обработчики
    if file_logging:
        # Основной файл логов
        main_file = log_path / "app.log"
        main_handler = RotatingFileHandler(
            filename=main_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        main_handler.setLevel(log_level)
        main_handler.setFormatter(formatter)
        app_logger.addHandler(main_handler)

        # Файл ошибок (только ERROR и выше)
        error_file = log_path / "errors.log"
        error_handler = RotatingFileHandler(
            filename=error_file,
            maxBytes=5 * 1024 * 1024,  # 5 МБ для ошибок
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        app_logger.addHandler(error_handler)

    # Заглушаем шумные логгеры
    noisy_loggers = {
        'aiosqlite': logging.WARNING,
        'sqlalchemy': logging.WARNING,
        'asyncio': logging.WARNING,
        'httpx': logging.WARNING,
        'aiohttp': logging.WARNING,
        'aiogram': logging.INFO,
    }

    for logger_name, logger_level in noisy_loggers.items():
        logging.getLogger(logger_name).setLevel(logger_level)

    # Логируем информацию о настройке
    app_logger.info("=" * 50)
    app_logger.info(f"Логирование настроено. Уровень: {level}")
    app_logger.info(f"Консоль: {'ВКЛ' if console else 'ВЫКЛ'}")
    app_logger.info(f"Файлы: {'ВКЛ' if file_logging else 'ВЫКЛ'}")
    app_logger.info("=" * 50)

    return app_logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Получить логгер для модуля

    Args:
        name: имя модуля (обычно __name__)

    Returns:
        Настроенный логгер
    """
    if not name:
        return logging.getLogger("app")

    # Для модулей приложения используем propagate
    if name.startswith('app.'):
        logger = logging.getLogger(name)
        logger.propagate = True  # Логи идут в основной логгер
        return logger

    return logging.getLogger(name)
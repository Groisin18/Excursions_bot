"""
Настройки логирования с разделением по файлам
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(
    level: str = "INFO",
    console: bool = True,
    file_logging: bool = True,
    log_dir: str = "logs",
    max_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка логирования с разделением по файлам

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

    # 1. Отключаем ВСЕ обработчики у корневого логгера
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)
    root_logger.propagate = False

    # 2. Создаем ОДИН главный логгер приложения
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)
    app_logger.propagate = False

    # Очищаем все старые обработчики
    app_logger.handlers.clear()

    # 3. Создаем директории для логов
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 4. Функция для создания файлового обработчика
    def create_file_handler(filename, level=log_level, max_mb=max_size_mb):
        """Создать ротируемый файловый обработчик"""
        file_path = log_path / filename
        handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=max_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        handler.name = f"file_{filename.split('.')[0]}"
        return handler

    # 5. Создаем специализированные фильтры
    class ModuleFilter(logging.Filter):
        """Фильтр по имени модуля"""
        def __init__(self, module_prefix):
            super().__init__()
            self.module_prefix = module_prefix

        def filter(self, record):
            return record.name.startswith(self.module_prefix)

    class LevelFilter(logging.Filter):
        """Фильтр по уровню логирования"""
        def __init__(self, min_level, max_level=None):
            super().__init__()
            self.min_level = min_level
            self.max_level = max_level

        def filter(self, record):
            if self.max_level:
                return self.min_level <= record.levelno <= self.max_level
            return record.levelno >= self.min_level

    # 6. Добавляем обработчики к главному логгеру

    # Консольный обработчик
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        console_handler.name = "console"
        app_logger.addHandler(console_handler)

    # Файловые обработчики (если включено файловое логирование)
    if file_logging:
        # Основной файл логов
        main_handler = create_file_handler("bot.log", log_level, 50)
        app_logger.addHandler(main_handler)

        # Файл ошибок (только ERROR и CRITICAL)
        error_handler = create_file_handler("errors.log", logging.ERROR, 20)
        error_handler.addFilter(LevelFilter(logging.ERROR))
        app_logger.addHandler(error_handler)

        # Файл отладочных логов (только при DEBUG уровне)
        if log_level == logging.DEBUG:
            debug_handler = create_file_handler("debug.log", logging.DEBUG, 100)
            debug_handler.addFilter(LevelFilter(logging.DEBUG))
            app_logger.addHandler(debug_handler)

    # 7. Настраиваем логгеры модулей с собственными файлами
    module_configs = [
        {
            'name': 'app.database',
            'log_file': 'database.log',
            'max_size_mb': 30,
            'description': 'Логи базы данных'
        },
        {
            'name': 'app.routers.payment_router',
            'log_file': 'payments.log',
            'max_size_mb': 30,
            'description': 'Логи платежей'
        },
        {
            'name': 'app.admin_panel',
            'log_file': 'admin.log',
            'max_size_mb': 20,
            'description': 'Логи администрирования'
        },
        {
            'name': 'app.routers.user_router',
            'log_file': 'user_actions.log',
            'max_size_mb': 20,
            'description': 'Логи действий пользователей'
        }
    ]

    for config in module_configs:
        module_logger = logging.getLogger(config['name'])
        module_logger.setLevel(log_level)
        module_logger.propagate = False  # Не пропагируем, так как у нас свой обработчик

        # Очищаем старые обработчики
        module_logger.handlers.clear()

        # Добавляем файловый обработчик для модуля
        if file_logging:
            module_handler = create_file_handler(
                config['log_file'],
                log_level,
                config['max_size_mb']
            )
            module_handler.addFilter(ModuleFilter(config['name']))
            module_logger.addHandler(module_handler)

        # Также пропагируем в основной логгер для консоли
        module_logger.parent = app_logger

    # 8. Настраиваем остальные логгеры модулей приложения (пропагируют)
    other_modules = [
        'app.routers',
        'app.utils',
        'app.middlewares',
        'app.migrations',
        'app.states',
        'app.keyboards'
    ]

    for module_name in other_modules:
        # Проверяем, не настроили ли мы уже этот логгер отдельно
        if module_name not in [m['name'] for m in module_configs]:
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(log_level)
            module_logger.propagate = True  # Пропагируют в родителя
            module_logger.handlers.clear()

            # Устанавливаем родителя
            if not module_logger.parent:
                module_logger.parent = app_logger

    # 9. Заглушаем шумные логгеры
    noisy_loggers = {
        'aiosqlite': logging.WARNING,
        'sqlalchemy': logging.WARNING,
        'sqlalchemy.engine': logging.WARNING,
        'sqlalchemy.pool': logging.WARNING,
        'asyncio': logging.WARNING,
        'httpx': logging.WARNING,
        'aiohttp': logging.WARNING,
        'aiogram': logging.INFO,
        'aiogram.event': logging.WARNING,
        'aiogram.middlewares': logging.WARNING,
    }

    for logger_name, logger_level in noisy_loggers.items():
        noisy_logger = logging.getLogger(logger_name)
        noisy_logger.setLevel(logger_level)
        noisy_logger.propagate = False
        noisy_logger.handlers.clear()

    # 10. Логируем информацию о настройке
    app_logger.info("=" * 60)
    app_logger.info("НАСТРОЙКА ЛОГИРОВАНИЯ ЗАВЕРШЕНА")
    app_logger.info(f"Уровень логирования: {level}")
    app_logger.info(f"Консольный вывод: {'ВКЛ' if console else 'ВЫКЛ'}")
    app_logger.info(f"Файловое логирование: {'ВКЛ' if file_logging else 'ВЫКЛ'}")

    if file_logging:
        app_logger.info("Файлы логов:")
        for config in module_configs:
            app_logger.info(f"  - {config['log_file']}: {config['description']}")
        app_logger.info(f"  - bot.log: Основные логи приложения")
        app_logger.info(f"  - errors.log: Критические ошибки")
        if log_level == logging.DEBUG:
            app_logger.info(f"  - debug.log: Отладочные логи")

    app_logger.info("=" * 60)

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

    # Получаем логгер
    logger = logging.getLogger(name)

    # Убеждаемся, что он настроен правильно
    if name.startswith('app.'):
        # Проверяем, не является ли это специальным логгером с файлом
        special_loggers = [
            'app.database',
            'app.routers.payment_router',
            'app.admin_panel',
            'app.routers.user_router'
        ]

        if name in special_loggers:
            # У специальных логгеров propagate = False
            if logger.propagate:
                logger.propagate = False
        else:
            # У обычных модулей propagate = True
            if not logger.propagate:
                logger.propagate = True
                logger.handlers.clear()

    return logger


def cleanup_old_logs(log_dir: str = "logs", days_to_keep: int = 30):
    """
    Очистка старых логов

    Args:
        log_dir: директория с логами
        days_to_keep: сколько дней хранить логи
    """
    from datetime import datetime, timedelta

    log_path = Path(log_dir)
    if not log_path.exists():
        return

    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    for log_file in log_path.glob("*.log.*"):  # Ищем ротированные файлы
        try:
            # Пытаемся получить дату из имени файла
            file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_date < cutoff_date:
                log_file.unlink()
                logging.getLogger("app").info(f"Удален старый лог: {log_file.name}")
        except Exception as e:
            logging.getLogger("app").warning(f"Ошибка при удалении {log_file}: {e}")


# Дополнительные функции для удобства
def get_database_logger() -> logging.Logger:
    """Получить логгер для базы данных"""
    return logging.getLogger("app.database")


def get_payment_logger() -> logging.Logger:
    """Получить логгер для платежей"""
    return logging.getLogger("app.routers.payment_router")


def get_admin_logger() -> logging.Logger:
    """Получить логгер для администрирования"""
    return logging.getLogger("app.admin_panel")


def get_user_actions_logger() -> logging.Logger:
    """Получить логгер для действий пользователей"""
    return logging.getLogger("app.routers.user_router")
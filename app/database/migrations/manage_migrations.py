#!/usr/bin/env python3
"""
Скрипт для управления миграциями базы данных
"""

import asyncio
import click
import logging
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path

from app.migrations.check_integrity import check_database_integrity

# Настройка логгера с правильной кодировкой
def setup_logger():
    """Настройка логгера с UTF-8 кодировкой"""
    logger = logging.getLogger()

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        # Простой формат без эмодзи
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger

logger = setup_logger()

@click.group()
def cli():
    """Управление миграциями базы данных"""
    pass

@cli.command()
def backup():
    """Создать резервную копию базы данных"""
    import shutil
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"database_backup_{timestamp}.db"

    if Path("database.db").exists():
        shutil.copy2("database.db", backup_name)
        logger.info(f"Создана резервная копия: {backup_name}")
    else:
        logger.error("Файл database.db не найден")

@cli.command()
@click.option('--backup-file', help='Файл для восстановления')
def restore(backup_file):
    """Восстановить базу данных из резервной копии"""
    import shutil

    if not backup_file:
        # Ищем последнюю резервную копию
        backup_files = list(Path(".").glob("database_backup_*.db"))
        if not backup_files:
            logger.error("Резервные копии не найдены")
            return

        backup_file = max(backup_files, key=lambda p: p.stat().st_mtime)

    if Path(backup_file).exists():
        shutil.copy2(backup_file, "database.db")
        logger.info(f"База данных восстановлена из: {backup_file}")
    else:
        logger.error(f"Файл {backup_file} не найден")

@cli.command()
def check():
    """Проверить целостность базы данных"""
    async def run_check():
        try:

            await check_database_integrity()
        except ImportError as e:
            logger.error(f"Не удалось импортировать модуль: {e}")

    asyncio.run(run_check())

@cli.command()
def list_backups():
    """Показать список резервных копий"""
    import glob
    from datetime import datetime

    backups = glob.glob("database_backup_*.db")

    if not backups:
        print("Резервные копии не найдены")
        return

    print("Список резервных копий:")
    for backup in sorted(backups):
        size = Path(backup).stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(Path(backup).stat().st_mtime)
        print(f"  {backup} ({size:.2f} MB, {mtime.strftime('%d.%m.%Y %H:%M')})")

@cli.command()
def cleanup():
    """Очистить старые резервные копии (оставить 5 последних)"""
    import glob
    from datetime import datetime
    backups = glob.glob("database_backup_*.db")

    if len(backups) <= 5:
        print(f"Всего {len(backups)} резервных копий, очистка не требуется")
        return

    # Сортируем по времени изменения (новые в начале)
    backups_with_time = [(b, Path(b).stat().st_mtime) for b in backups]
    backups_with_time.sort(key=lambda x: x[1], reverse=True)

    to_delete = backups_with_time[5:]  # Оставляем 5 последних

    for backup, _ in to_delete:
        Path(backup).unlink()
        print(f"Удалена: {backup}")

    print(f"Удалено {len(to_delete)} старых резервных копий")

if __name__ == "__main__":
    cli()
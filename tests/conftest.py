"""Глобальная конфигурация pytest."""

import pytest
import sys
import warnings
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Импортируем фикстуры из подпапок
pytest_plugins = [
    'tests.fixtures.db_fixtures',
    'tests.fixtures.telegram_fixtures',
    'tests.fixtures.redis_fixtures',
    'tests.fixtures.data_fixtures',
    'tests.fixtures.repository_fixtures',  # Добавляем новую фикстуру
]


def pytest_configure(config):
    """Конфигурация pytest перед запуском тестов."""
    import os
    if os.path.exists("database.db"):
        warnings.warn(
            "Обнаружен файл database.db. Убедитесь, что тесты используют :memory: БД, а не production.",
            RuntimeWarning
        )

    config.addinivalue_line(
        "markers",
        "integration: тесты, требующие реальной БД или внешних сервисов"
    )
    config.addinivalue_line(
        "markers",
        "slow: медленные тесты"
    )
    config.addinivalue_line(
        "markers",
        "database: тесты, работающие с базой данных"
    )
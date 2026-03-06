import redis.asyncio as aioredis
from redis.asyncio import Lock
from typing import Optional, Union
from contextlib import asynccontextmanager
from app.utils.logging_config import get_logger
import os

logger = get_logger(__name__)


class RedisClient:
    """Клиент для работы с Redis"""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def initialize(self):
        """Инициализация подключения к Redis"""
        try:
            # Получаем настройки из .env
            host = os.getenv('REDIS_HOST', 'localhost')
            port = os.getenv('REDIS_PORT', 6379)
            db = os.getenv('REDIS_DB', 0)
            password = os.getenv('REDIS_PASSWORD')

            # Формируем URL
            if password and password.strip():
                redis_url = f"redis://:{password}@{host}:{port}/{db}"
            else:
                redis_url = f"redis://{host}:{port}/{db}"

            logger.info(f"Подключение к Redis: {host}:{port}/{db} (пароль: {'есть' if password else 'нет'})")

            self._redis = aioredis.from_url(
                redis_url,
                decode_responses=True
            )

            # Проверяем подключение
            await self._redis.ping()
            logger.info("Redis подключен успешно")

        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {e}")
            self._redis = None
            raise

    async def close(self):
        """Закрытие подключения"""
        if self._redis:
            await self._redis.close()
            logger.info("Redis соединение закрыто")

    @property
    def client(self) -> aioredis.Redis:
        if not self._redis:
            raise RuntimeError("Redis не инициализирован. Вызовите initialize()")
        return self._redis

    # ========== МЕТОДЫ ДЛЯ БЛОКИРОВОК ==========

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 30, blocking_timeout: Union[int, float, None] = None):
        """
        Контекстный менеджер для блокировки.

        Args:
            key: Ключ блокировки (например, "lock:slot:123")
            timeout: Время жизни блокировки в секундах (автоматически снимится через это время)
            blocking_timeout: Максимальное время ожидания блокировки в секундах.
                            Если None - ждать бесконечно.

        Пример:
            async with redis_client.lock("lock:slot:123", timeout=30):
                # критическая секция
                await create_booking(...)
        """
        lock = self.get_lock(key, timeout=timeout)

        try:
            # Пытаемся получить блокировку
            acquired = await lock.acquire(blocking_timeout=blocking_timeout)
            if not acquired:
                raise TimeoutError(f"Не удалось получить блокировку {key} за {blocking_timeout} сек")

            logger.debug(f"Блокировка получена: {key}")
            yield
        finally:
            # Всегда освобождаем блокировку
            await lock.release()
            logger.debug(f"Блокировка освобождена: {key}")

    def get_lock(self, key: str, timeout: int = 30) -> Lock:
        """
        Получить объект блокировки для ключа.

        Args:
            key: Ключ блокировки
            timeout: Время жизни блокировки в секундах

        Returns:
            Lock: Объект блокировки из redis-py
        """
        if not self._redis:
            raise RuntimeError("Redis не инициализирован")

        return Lock(
            self._redis,
            name=key,
            timeout=timeout,
            lock_class=None  # используем класс по умолчанию
        )

    async def acquire_lock(self, key: str, timeout: int = 30, blocking: bool = True) -> bool:
        """
        Ручное получение блокировки (без контекстного менеджера).

        Args:
            key: Ключ блокировки
            timeout: Время жизни блокировки в секундах
            blocking: Ждать ли освобождения блокировки

        Returns:
            bool: True если блокировка получена
        """
        lock = self.get_lock(key, timeout=timeout)
        return await lock.acquire(blocking=blocking)

    async def release_lock(self, key: str):
        """
        Ручное освобождение блокировки.

        Args:
            key: Ключ блокировки
        """
        lock = self.get_lock(key)
        await lock.release()

    async def extend_lock(self, key: str, extra_time: int = 30) -> bool:
        """
        Продлить время жизни блокировки.

        Args:
            key: Ключ блокировки
            extra_time: Дополнительное время в секундах

        Returns:
            bool: True если удалось продлить
        """
        if not self._redis:
            return False

        # Используем команду PEXPIRE для продления
        result = await self._redis.pexpire(key, extra_time * 1000)
        return bool(result)

    async def is_locked(self, key: str) -> bool:
        """
        Проверить, существует ли блокировка.

        Args:
            key: Ключ блокировки

        Returns:
            bool: True если блокировка активна
        """
        if not self._redis:
            return False

        exists = await self._redis.exists(key)
        return bool(exists)


# Создаем глобальный экземпляр
redis_client = RedisClient()
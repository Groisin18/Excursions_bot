import redis.asyncio as aioredis
from typing import Optional, Union
from contextlib import asynccontextmanager
import uuid
import asyncio
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

    async def acquire_lock(self, key: str, timeout: int = 30, token: Optional[str] = None) -> Optional[str]:
        """
        Попытка получить блокировку.

        Args:
            key: Ключ блокировки
            timeout: Время жизни блокировки в секундах
            token: Уникальный идентификатор блокировки (если не указан, генерируется)

        Returns:
            str: Токен блокировки если удалось получить, иначе None
        """
        if not self._redis:
            raise RuntimeError("Redis не инициализирован")

        token = token or str(uuid.uuid4())

        # SET key value NX PX milliseconds
        # NX - установить только если ключ не существует
        # PX - время жизни в миллисекундах
        result = await self._redis.set(
            key,
            token,
            nx=True,
            px=timeout * 1000  # конвертируем в миллисекунды
        )

        if result:
            logger.debug(f"Блокировка получена: {key}, токен: {token}")
            return token
        else:
            logger.debug(f"Не удалось получить блокировку: {key}")
            return None

    async def release_lock(self, key: str, token: str) -> bool:
        """
        Освободить блокировку только если принадлежит нам.

        Args:
            key: Ключ блокировки
            token: Токен блокировки (для проверки владельца)

        Returns:
            bool: True если блокировка освобождена
        """
        if not self._redis:
            return False

        # Lua скрипт для атомарного удаления только если значение совпадает
        # Это защищает от освобождения чужой блокировки
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        result = await self._redis.eval(lua_script, 1, key, token)
        success = bool(result)

        if success:
            logger.debug(f"Блокировка освобождена: {key}")
        else:
            logger.debug(f"Не удалось освободить блокировку (чужая или истекла): {key}")

        return success

    async def extend_lock(self, key: str, token: str, extra_time: int = 30) -> bool:
        """
        Продлить время жизни блокировки.

        Args:
            key: Ключ блокировки
            token: Токен блокировки (для проверки владельца)
            extra_time: Дополнительное время в секундах

        Returns:
            bool: True если удалось продлить
        """
        if not self._redis:
            return False

        # Lua скрипт для продления только если блокировка наша
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("pexpire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """

        result = await self._redis.eval(lua_script, 1, key, token, extra_time * 1000)
        return bool(result)

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 30, blocking_timeout: Union[int, float, None] = None):
        """
        Контекстный менеджер для блокировки.

        Args:
            key: Ключ блокировки
            timeout: Время жизни блокировки в секундах
            blocking_timeout: Максимальное время ожидания блокировки в секундах.
                            Если None - ждать бесконечно.

        Raises:
            TimeoutError: Если не удалось получить блокировку за blocking_timeout

        Пример:
            async with redis_client.lock("lock:slot:123", timeout=30):
                # критическая секция
                await create_booking(...)
        """
        token = str(uuid.uuid4())
        start_time = asyncio.get_event_loop().time()

        try:
            # Пытаемся получить блокировку
            acquired = False
            while not acquired:
                token = await self.acquire_lock(key, timeout, token)

                if token:
                    acquired = True
                    break

                if blocking_timeout is not None:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= blocking_timeout:
                        raise TimeoutError(f"Не удалось получить блокировку {key} за {blocking_timeout} сек")

                # Ждем немного перед следующей попыткой
                await asyncio.sleep(0.1)

            logger.debug(f"Блокировка получена: {key}")
            yield

        finally:
            # Всегда пытаемся освободить блокировку
            await self.release_lock(key, token)
            logger.debug(f"Блокировка освобождена: {key}")

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

    async def get_lock_owner(self, key: str) -> Optional[str]:
        """
        Получить токен владельца блокировки.

        Args:
            key: Ключ блокировки

        Returns:
            Optional[str]: Токен владельца или None
        """
        if not self._redis:
            return None

        return await self._redis.get(key)


# Создаем глобальный экземпляр
redis_client = RedisClient()
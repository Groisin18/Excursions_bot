import redis.asyncio as aioredis
from typing import Optional
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

# Создаем глобальный экземпляр
redis_client = RedisClient()
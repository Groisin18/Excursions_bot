# app/services/scheduler.py
"""
Сервис для планирования фоновых задач с использованием APScheduler и Redis.
Задачи:
- Автоотмена неоплаченных бронирований (каждые 15 минут)
- Напоминания о предстоящих экскурсиях (за 24 часа и 2 часа)
- Автозавершение прошедших экскурсий (каждый час)
"""

import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logging_config import get_logger

from .tasks import (
    auto_cancel_unpaid_bookings, auto_complete_excursions,
    send_excursion_reminder, send_payment_reminder,
    notify_admins_about_slots_without_captain
)
from .bot_instance import set_bot_instance

logger = get_logger(__name__)

class SchedulerService:
    """Сервис для управления планировщиком задач"""

    def __init__(self):
        self.scheduler = None
        self.bot = None
        self._setup_scheduler()

    def _setup_scheduler(self):
        """Настройка планировщика с Redis хранилищем"""
        try:
            # Получаем настройки из .env
            host = os.getenv('REDIS_HOST', 'localhost')
            port = int(os.getenv('REDIS_PORT', 6379))
            db = int(os.getenv('REDIS_DB', 0))

            logger.info(f"Настройка Redis JobStore: {host}:{port}/{db} (без аутентификации)")
            # Создаем хранилище задач в Redis
            jobstores = {
                'default': RedisJobStore(
                    jobs_key='scheduler:jobs',
                    run_times_key='scheduler:run_times',
                    host=host,
                    port=port,
                    db=db
                )
            }

            # Исполнитель задач (asyncio)
            executors = {
                'default': AsyncIOExecutor()
            }

            # Настройки планировщика
            job_defaults = {
                'coalesce': True,      # Объединять пропущенные запуски
                'max_instances': 3,    # До 3 параллельных экземпляров (защита через Redis)
                'misfire_grace_time': 30  # 30 секунд на запуск после пропуска
            }

            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='Asia/Irkutsk'
            )

            logger.info("Планировщик настроен с Redis хранилищем")

        except Exception as e:
            logger.error(f"Ошибка настройки планировщика с Redis: {e}")
            logger.info("Планировщик будет работать с хранилищем в памяти")

            # Fallback на хранилище в памяти
            self.scheduler = AsyncIOScheduler(
                executors={'default': AsyncIOExecutor()},
                job_defaults={'coalesce': True, 'max_instances': 1},
                timezone='Europe/Moscow'
            )

    async def start(self, bot=None):
        """Запуск планировщика и регистрация задач"""
        if bot:
            self.bot = bot
            await set_bot_instance(bot)  # сохраняем в глобальной переменной
            logger.info("Экземпляр bot передан планировщику")

        if not self.scheduler:
            self._setup_scheduler()

        # 1. Автоотмена неоплаченных броней - каждые 15 минут
        self.scheduler.add_job(
            auto_cancel_unpaid_bookings,
            trigger=IntervalTrigger(minutes=15),
            id='cancel_unpaid_bookings',
            replace_existing=True,
            next_run_time=datetime.now()
        )

        # Напоминания об оплате - каждые 10 минут
        self.scheduler.add_job(
            send_payment_reminder,
            trigger=IntervalTrigger(minutes=10),
            id='send_payment_reminder',
            replace_existing=True,
            next_run_time=datetime.now()
        )

        # Напоминания об экскурсиях - каждый час
        self.scheduler.add_job(
            send_excursion_reminder,
            trigger=IntervalTrigger(hours=1),
            id='send_excursion_reminder',
            replace_existing=True,
            next_run_time=datetime.now()
        )

        # Автозавершение прошедших экскурсий - каждые 5 минут
        self.scheduler.add_job(
            auto_complete_excursions,
            trigger=IntervalTrigger(minutes=5),
            id='auto_complete_excursions',
            replace_existing=True,
            next_run_time=datetime.now()
        )

        # Проверка слотов без капитана - каждые 3 часа
        self.scheduler.add_job(
            notify_admins_about_slots_without_captain,
            'interval',
            hours=3,
            id='notify_admins_about_slots_without_captain',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Планировщик запущен")


    async def shutdown(self):
        """Остановка планировщика"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()

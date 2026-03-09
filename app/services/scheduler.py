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

from app.services.redis import redis_client
from app.database.unit_of_work import UnitOfWork
from app.database.managers import BookingManager
from app.database.session import async_session
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_bot_instance = None

async def set_bot_instance(bot):
    global _bot_instance
    _bot_instance = bot

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
            password = os.getenv('REDIS_PASSWORD')

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
                'max_instances': 1,    # Не запускать параллельно
                'misfire_grace_time': 60  # 60 секунд на запуск после пропуска
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
            auto_cancel_unpaid_bookings,  # <-- отдельная функция
            trigger=IntervalTrigger(minutes=15),
            id='cancel_unpaid_bookings',
            replace_existing=True,
            next_run_time=datetime.now()
        )
        logger.debug("Задача 'cancel_unpaid_bookings' зарегистрирована")

        # 2. Напоминания за 24 часа
        self.scheduler.add_job(
            send_24h_reminders,  # <-- отдельная функция
            trigger=IntervalTrigger(hours=1),
            id='send_24h_reminders',
            replace_existing=True
        )
        logger.debug("Задача 'send_24h_reminders' зарегистрирована")

        # 3. Напоминания за 2 часа
        self.scheduler.add_job(
            send_2h_reminders,  # <-- отдельная функция
            trigger=IntervalTrigger(minutes=30),
            id='send_2h_reminders',
            replace_existing=True
        )
        logger.debug("Задача 'send_2h_reminders' зарегистрирована")

        # 4. Автозавершение экскурсий
        self.scheduler.add_job(
            auto_complete_excursions,  # <-- отдельная функция
            trigger=IntervalTrigger(hours=1),
            id='auto_complete_excursions',
            replace_existing=True
        )
        logger.debug("Задача 'auto_complete_excursions' зарегистрирована")

        self.scheduler.start()
        logger.info("Планировщик запущен")


    async def shutdown(self):
        """Остановка планировщика"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()

# ========== ОТДЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЗАДАЧ ==========

async def auto_cancel_unpaid_bookings():
    """Автоотмена неоплаченных бронирований"""
    logger.info("Запуск автоотмены неоплаченных бронирований")

    lock_key = "scheduler:lock:cancel_unpaid"
    token = await redis_client.acquire_lock(lock_key, timeout=300)

    if not token:
        logger.warning("Не удалось получить блокировку для автоотмены")
        return

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            try:
                booking_manager = BookingManager(session)
                bookings = await booking_manager.get_expired_unpaid_bookings()

                if not bookings:
                    logger.debug("Нет просроченных неоплаченных бронирований")
                    return

                logger.info(f"Найдено бронирований для отмены: {len(bookings)}")

                for booking in bookings:
                    success, message, refund_data = await booking_manager.cancel_booking(
                        booking_id=booking.id,
                        auto_refund=False
                    )

                    if success:
                        logger.info(f"Отменено бронирование #{booking.id}")

                        if booking.adult_user.telegram_id and _bot_instance:
                            try:
                                await _bot_instance.send_message(
                                    chat_id=booking.adult_user.telegram_id,
                                    text=(
                                        f"Бронирование отменено\n\n"
                                        f"Ваше бронирование на экскурсию "
                                        f"{booking.slot.excursion.name} "
                                        f"{booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')} "
                                        f"было автоматически отменено, так как не было оплачено "
                                        f"в течение 24 часов."
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления: {e}")
                        else:
                            logger.info(f"Ошибка отправки уведомления:"
                                        f"Клиент с номером телефона {booking.adult_user.phone_number} "
                                        f"не имеет TelegramID в базе данных")
                    else:
                        logger.error(f"Не удалось отменить бронирование #{booking.id}: {message}")

                logger.info(f"Автоотмена неоплаченных бронирований завершена, обработано: {len(bookings)}")

            except Exception as e:
                logger.error(f"Ошибка при автоотмене: {e}", exc_info=True)
                raise
            finally:
                await redis_client.release_lock(lock_key, token)


async def send_24h_reminders():
    """Напоминания за 24 часа"""
    logger.info("Запуск напоминаний за 24 часа")
    # TODO: реализовать


async def send_2h_reminders():
    """Напоминания за 2 часа"""
    logger.info("Запуск напоминаний за 2 часа")
    # TODO: реализовать


async def auto_complete_excursions():
    """Автозавершение экскурсий"""
    logger.info("Запуск автозавершения экскурсий")
    # TODO: реализовать
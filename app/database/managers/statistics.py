"""
Менеджер для бизнес-логики статистики.
Использует репозитории для получения данных.
"""

from datetime import datetime
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from ..repositories.statistic_repository import StatisticsRepository
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


class StatisticsManager(BaseManager):
    """Менеджер для бизнес-логики статистики"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.stats_repo = StatisticsRepository(session)

    async def get_daily_stats(self, date_val: datetime) -> Dict:
        """Статистика за день"""
        self._log_operation_start("get_daily_stats", date=date_val.date())

        try:
            bookings_count = await self.stats_repo.get_daily_bookings_count(date_val.date())
            revenue = await self.stats_repo.get_daily_revenue(date_val.date())
            new_users = await self.stats_repo.get_daily_new_users(date_val.date())

            stats = {
                'total_bookings': bookings_count,
                'total_revenue': revenue,
                'new_users': new_users
            }

            self._log_operation_end("get_daily_stats", success=True, stats=stats)
            return stats

        except Exception as e:
            self._log_operation_end("get_daily_stats", success=False)
            logger.error(f"Ошибка получения дневной статистики: {e}", exc_info=True)
            return {
                'total_bookings': 0,
                'total_revenue': 0,
                'new_users': 0
            }

    async def get_period_stats(self, start_date: datetime, end_date: datetime) -> Dict:
        """Статистика за период"""
        self._log_operation_start("get_period_stats",
                                 start_date=start_date.date(),
                                 end_date=end_date.date())

        try:
            total_bookings = await self.stats_repo.get_period_bookings_count(start_date, end_date)
            total_revenue = await self.stats_repo.get_period_revenue(start_date, end_date)
            new_users = await self.stats_repo.get_period_new_users(start_date, end_date)
            completed_excursions = await self.stats_repo.get_period_completed_excursions(start_date, end_date)

            popular_excursion, booking_count = await self.stats_repo.get_popular_excursion(start_date, end_date)

            # Бизнес-логика: расчет среднего чека
            avg_check = total_revenue / total_bookings if total_bookings > 0 else 0

            # Бизнес-логика: расчет конверсии
            conversion_rate = (total_bookings / new_users * 100) if new_users > 0 else 0

            stats = {
                'total_bookings': total_bookings,
                'total_revenue': total_revenue,
                'new_users': new_users,
                'completed_excursions': completed_excursions,
                'popular_excursion': popular_excursion,
                'popular_excursion_bookings': booking_count,
                'avg_check': round(avg_check, 2),
                'conversion_rate': round(conversion_rate, 2)
            }

            self._log_operation_end("get_period_stats", success=True)
            return stats

        except Exception as e:
            self._log_operation_end("get_period_stats", success=False)
            logger.error(f"Ошибка получения статистики за период: {e}", exc_info=True)
            return {
                'total_bookings': 0,
                'total_revenue': 0,
                'new_users': 0,
                'completed_excursions': 0,
                'popular_excursion': 'Нет данных',
                'popular_excursion_bookings': 0,
                'avg_check': 0,
                'conversion_rate': 0
            }

    async def generate_period_report(self, start_date: datetime, end_date: datetime) -> str:
        """Генерация текстового отчета"""
        self._log_operation_start("generate_period_report",
                                 start_date=start_date.date(),
                                 end_date=end_date.date())

        try:
            stats = await self.get_period_stats(start_date, end_date)

            report = f"""
ОТЧЕТ за период {start_date.date()} - {end_date.date()}

Статистика:
• Всего бронирований: {stats.get('total_bookings', 0)}
• Выручка: {stats.get('total_revenue', 0)} руб.
• Новых пользователей: {stats.get('new_users', 0)}
• Проведено экскурсий: {stats.get('completed_excursions', 0)}

Активность:
• Самый популярный маршрут: {stats.get('popular_excursion', 'Нет данных')} ({stats.get('popular_excursion_bookings', 0)} бронирований)
• Средний чек: {stats.get('avg_check', 0)} руб.
• Конверсия: {stats.get('conversion_rate', 0)}%
            """

            self._log_operation_end("generate_period_report", success=True)
            return report.strip()

        except Exception as e:
            self._log_operation_end("generate_period_report", success=False)
            logger.error(f"Ошибка генерации отчета: {e}", exc_info=True)
            return f"Ошибка генерации отчета за период {start_date.date()} - {end_date.date()}"
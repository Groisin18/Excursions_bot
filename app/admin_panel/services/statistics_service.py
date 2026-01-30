from datetime import datetime
from typing import Dict
from sqlalchemy import func, and_, select

from app.database.models import async_session, Booking, Payment, User, Excursion, ExcursionSlot
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

class StatisticsService:
    async def get_daily_stats(self, date: datetime) -> Dict:
        """Статистика за день"""
        async with async_session() as session:
            # Подсчет бронирований за день
            bookings_query = select(func.count(Booking.id)).where(
                and_(
                    func.date(Booking.created_at) == date.date(),
                    Booking.booking_status.in_(['active', 'confirmed', 'completed'])
                )
            )
            bookings_count = await session.scalar(bookings_query) or 0

            # Подсчет выручки за день
            revenue_query = select(func.sum(Payment.amount)).where(
                and_(
                    func.date(Payment.created_at) == date.date(),
                    Payment.status == 'completed'
                )
            )
            revenue = await session.scalar(revenue_query) or 0

            # Новые пользователи за день
            new_users_query = select(func.count(User.id)).where(
                func.date(User.created_at) == date.date()
            )
            new_users = await session.scalar(new_users_query) or 0

            # Активные экскурсии
            active_excursions_query = select(func.count(Excursion.id)).where(
                Excursion.is_active == True
            )
            active_excursions = await session.scalar(active_excursions_query) or 0

            return {
                'total_bookings': bookings_count,
                'total_revenue': revenue,
                'new_users': new_users,
                'active_excursions': active_excursions
            }

    async def get_period_stats(self, start_date: datetime, end_date: datetime) -> Dict:
        """Статистика за период"""
        async with async_session() as session:
            # Бронирования за период
            bookings_query = select(func.count(Booking.id)).where(
                and_(
                    Booking.created_at >= start_date,
                    Booking.created_at <= end_date,
                    Booking.booking_status.in_(['active', 'confirmed', 'completed'])
                )
            )
            total_bookings = await session.scalar(bookings_query) or 0

            # Выручка за период
            revenue_query = select(func.sum(Payment.amount)).where(
                and_(
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date,
                    Payment.status == 'completed'
                )
            )
            total_revenue = await session.scalar(revenue_query) or 0

            # Новые пользователи за период
            new_users_query = select(func.count(User.id)).where(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            )
            new_users = await session.scalar(new_users_query) or 0

            # Завершенные экскурсии за период
            completed_excursions_query = select(func.count(ExcursionSlot.id)).where(
                and_(
                    ExcursionSlot.start_datetime >= start_date,
                    ExcursionSlot.start_datetime <= end_date,
                    ExcursionSlot.status == 'completed'
                )
            )
            completed_excursions = await session.scalar(completed_excursions_query) or 0

            # Самая популярная экскурсия
            popular_excursion_query = select(
                Excursion.name,
                func.count(Booking.id).label('booking_count')
            ).select_from(Booking).join(
                ExcursionSlot, Booking.slot_id == ExcursionSlot.id
            ).join(
                Excursion, ExcursionSlot.excursion_id == Excursion.id
            ).where(
                and_(
                    Booking.created_at >= start_date,
                    Booking.created_at <= end_date
                )
            ).group_by(Excursion.name).order_by(func.count(Booking.id).desc()).limit(1)

            popular_result = await session.execute(popular_excursion_query)
            popular_row = popular_result.first()
            popular_excursion = popular_row[0] if popular_row else 'Нет данных'

            # Средний чек
            avg_check = total_revenue / total_bookings if total_bookings > 0 else 0

            # Конверсия (бронирования на пользователя)
            conversion_rate = (total_bookings / new_users * 100) if new_users > 0 else 0

            return {
                'total_bookings': total_bookings,
                'total_revenue': total_revenue,
                'new_users': new_users,
                'completed_excursions': completed_excursions,
                'popular_excursion': popular_excursion,
                'avg_check': round(avg_check, 2),
                'conversion_rate': round(conversion_rate, 2)
            }

    async def generate_period_report(self, start_date: datetime, end_date: datetime) -> str:
        """Генерация текстового отчета"""
        stats = await self.get_period_stats(start_date, end_date)

        report = f"""
ОТЧЕТ за период {start_date.date()} - {end_date.date()}

Статистика:
• Всего бронирований: {stats.get('total_bookings', 0)}
• Выручка: {stats.get('total_revenue', 0)} руб.
• Новых пользователей: {stats.get('new_users', 0)}
• Проведено экскурсий: {stats.get('completed_excursions', 0)}

Активность:
• Самый популярный маршрут: {stats.get('popular_excursion', 'Нет данных')}
• Средний чек: {stats.get('avg_check', 0)} руб.
• Конверсия: {stats.get('conversion_rate', 0)}%
        """
        return report
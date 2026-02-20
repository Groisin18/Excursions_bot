"""
Менеджер для бизнес-логики расчета зарплат.
"""

from datetime import date, timedelta
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from app.database.repositories import (
    SalaryRepository, SlotRepository
)
from app.database.models import BookingStatus, Salary


class SalaryManager(BaseManager):
    """Менеджер для бизнес-логики расчета зарплат"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.slot_repo = SlotRepository(session)
        self.salary_repo = SalaryRepository(session)

    async def calculate_captain_salary(
        self,
        captain_id: int,
        period_start: date,
        period_end: date = None
    ) -> Dict:
        """Рассчитать зарплату капитана за период

        Args:
            captain_id: ID капитана
            period_start: Начало периода
            period_end: Конец периода (по умолчанию - последний день месяца period_start)

        Returns:
            Dict: Словарь со статистикой
        """
        if period_end is None:
            # Последний день месяца period_start
            next_month = period_start.replace(day=28) + timedelta(days=4)
            period_end = next_month - timedelta(days=next_month.day)

        self._log_operation_start(
            "calculate_captain_salary",
            captain_id=captain_id,
            period_start=period_start,
            period_end=period_end
        )

        try:
            # Получаем завершенные слоты капитана за период
            slots = await self.slot_repo.get_captain_completed_slots_for_period(
                captain_id,
                period_start,
                period_end
            )

            total_bookings = 0
            total_people = 0
            total_revenue = 0

            # Бизнес-логика: подсчет метрик
            for slot in slots:
                for booking in slot.bookings:
                    if booking.booking_status == BookingStatus.completed:
                        total_bookings += 1
                        total_people += booking.people_count
                        total_revenue += booking.total_price

            # Бизнес-логика: расчет зарплаты
            base_salary = total_bookings * 500  # Базовая ставка
            bonus = total_people * 100  # Бонус за количество людей
            total_amount = base_salary + bonus

            result = {
                'captain_id': captain_id,
                'period_start': period_start,
                'period_end': period_end,
                'base_salary': base_salary,
                'bonus': bonus,
                'total_amount': total_amount,
                'total_bookings': total_bookings,
                'total_people': total_people,
                'total_revenue': total_revenue
            }

            self._log_operation_end("calculate_captain_salary", success=True, result=result)
            return result

        except Exception as e:
            self._log_operation_end("calculate_captain_salary", success=False)
            self.logger.error(f"Ошибка расчета зарплаты капитана {captain_id}: {e}", exc_info=True)
            raise

    async def create_salary_record(
        self,
        user_id: int,
        period: date,
        base_salary: int,
        bonus: int,
        total_amount: int
    ) -> Optional[Salary]:
        """Создать запись о зарплате"""
        self._log_operation_start("create_salary_record",
                                 user_id=user_id,
                                 period=period,
                                 base_salary=base_salary,
                                 bonus=bonus)

        try:
            # Бизнес-логика: проверка на дублирование (зарплата за период уже начислена)
            existing = await self.salary_repo.get_salary_for_period(user_id, period)
            if existing:
                self.logger.warning(f"Зарплата для пользователя {user_id} за период {period} уже существует")
                raise ValueError(f"Зарплата за период {period} уже начислена")

            # Создаем запись через репозиторий
            salary = await self.salary_repo.create_salary_record(
                user_id=user_id,
                period=period,
                base_salary=base_salary,
                bonus=bonus,
                total_amount=total_amount
            )

            self._log_operation_end("create_salary_record", success=True, salary_id=salary.id)
            return salary

        except ValueError as e:
            self._log_operation_end("create_salary_record", success=False)
            raise
        except Exception as e:
            self._log_operation_end("create_salary_record", success=False)
            self.logger.error(f"Ошибка создания записи о зарплате: {e}", exc_info=True)
            raise
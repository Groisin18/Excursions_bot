"""Репозиторий для работы с зарплатами (CRUD операции)"""

from datetime import date
from typing import Optional, List

from .base import BaseRepository
from app.database.models import Salary


class SalaryRepository(BaseRepository):
    """Репозиторий для CRUD операций с зарплатами"""

    def __init__(self, session):
        super().__init__(session)

    async def create_salary_record(
        self,
        user_id: int,
        period: date,
        base_salary: int,
        bonus: int,
        total_amount: int
    ) -> Salary:
        """Создать запись о зарплате (CRUD)"""
        salary = Salary(
            user_id=user_id,
            period=period,
            base_salary=base_salary,
            bonus=bonus,
            total_amount=total_amount
        )

        return await self._create(salary)

    async def get_salary_for_period(self, user_id: int, period: date) -> Optional[Salary]:
        """Получить зарплату пользователя за период"""
        return await self._get_one(
            Salary,
            Salary.user_id == user_id,
            Salary.period == period
        )

    async def get_captain_salaries(self, captain_id: int, limit: int = 12) -> List[Salary]:
        """Получить историю зарплат капитана"""
        return await self._get_many(
            Salary,
            Salary.user_id == captain_id,
            order_by=Salary.period.desc(),
            limit=limit
        )

    async def get_period_salaries(self, period: date) -> List[Salary]:
        """Получить все зарплаты за период"""
        return await self._get_many(
            Salary,
            Salary.period == period,
            order_by=Salary.user_id
        )
"""Репозиторий для работы с расходами (CRUD операции)"""

from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from app.database.models import Expense


class ExpenseRepository(BaseRepository):
    """Репозиторий для CRUD операций с расходами"""

    def __init__(self, session):
        super().__init__(session)

    async def create_expense(
        self,
        category: str,
        amount: int,
        description: str,
        expense_date: date,
        created_by_id: int
    ) -> Expense:
        """Создать запись о расходе"""
        try:
            expense = Expense(
                category=category,
                amount=amount,
                description=description,
                expense_date=expense_date,
                created_by_id=created_by_id
            )

            return await self._create(expense)

        except Exception as e:
            self.logger.error(f"Ошибка создания записи о расходе: {e}", exc_info=True)
            raise

    async def get_expenses(self, start_date: date, end_date: date) -> List[Expense]:
        """Получить расходы за период"""
        try:
            query = (
                select(Expense)
                .options(selectinload(Expense.created_by))
                .where(
                    and_(
                        Expense.expense_date >= start_date,
                        Expense.expense_date <= end_date
                    )
                )
                .order_by(Expense.expense_date.desc())
            )

            result = await self._execute_query(query)
            return list(result.scalars().all())

        except Exception as e:
            self.logger.error(f"Ошибка получения расходов: {e}", exc_info=True)
            return []

    async def get_expense_by_id(self, expense_id: int) -> Optional[Expense]:
        """Получить расход по ID"""
        return await self._get_one(Expense, Expense.id == expense_id)

    async def get_expenses_by_category(
        self,
        category: str,
        start_date: date = None,
        end_date: date = None
    ) -> List[Expense]:
        """Получить расходы по категории"""
        try:
            conditions = [Expense.category == category]

            if start_date:
                conditions.append(Expense.expense_date >= start_date)
            if end_date:
                conditions.append(Expense.expense_date <= end_date)

            return await self._get_many(
                Expense,
                *conditions,
                order_by=Expense.expense_date.desc()
            )

        except Exception as e:
            self.logger.error(f"Ошибка получения расходов по категории {category}: {e}")
            return []

    async def get_total_expenses(self, start_date: date, end_date: date) -> int:
        """Получить общую сумму расходов за период"""
        try:
            query = select(Expense).where(
                and_(
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )

            result = await self._execute_query(query)
            expenses = result.scalars().all()

            return sum(expense.amount for expense in expenses)

        except Exception as e:
            self.logger.error(f"Ошибка получения общей суммы расходов: {e}")
            return 0
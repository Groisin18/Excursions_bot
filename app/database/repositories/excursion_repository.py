"""Репозиторий для работы с экскурсиями (CRUD операции)"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.database.models import Excursion


class ExcursionRepository(BaseRepository):
    """Репозиторий для CRUD операций с экскурсиями"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)


    async def get_by_id(self, excursion_id: int) -> Optional[Excursion]:
        """Получить экскурсию по ID"""
        return await self._get_one(Excursion, Excursion.id == excursion_id)

    async def get_by_name(self, name: str) -> Optional[Excursion]:
        """Получить экскурсию по точному названию"""
        return await self._get_one(Excursion, Excursion.name == name)


    async def get_all(self, active_only: bool = True) -> List[Excursion]:
        """Получить все экскурсии"""
        conditions = []
        if active_only:
            conditions.append(Excursion.is_active == True)
        return await self._get_many(Excursion, *conditions)


    async def create(self, name: str, base_duration_minutes: int,
                    base_price: int, description: str = None,
                    is_active: bool = True) -> Excursion:
        """Создать новую экскурсию"""
        excursion_data = {
            'name': name,
            'description': description,
            'base_duration_minutes': base_duration_minutes,
            'base_price': base_price,
            'is_active': is_active
        }
        return await self._create(Excursion, **excursion_data)


    async def update(self, excursion_id: int, **update_data) -> bool:
        """Обновить данные экскурсии"""
        clean_data = {k: v for k, v in update_data.items() if v is not None}
        if not clean_data:
            self.logger.warning("Нет данных для обновления экскурсии")
            return False

        updated_count = await self._update(Excursion, Excursion.id == excursion_id, **clean_data)
        return updated_count > 0


    async def deactivate(self, excursion_id: int) -> bool:
        """Деактивировать экскурсию"""
        return await self.update(excursion_id, is_active=False)

    async def activate(self, excursion_id: int) -> bool:
        """Активировать экскурсию"""
        return await self.update(excursion_id, is_active=True)
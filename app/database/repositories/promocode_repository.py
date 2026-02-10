"""Репозиторий для работы с промокодами (CRUD операции)"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, and_

from .base import BaseRepository
from app.database.models import PromoCode, DiscountType


class PromoCodeRepository(BaseRepository):
    """Репозиторий для CRUD операций с промокодами"""

    def __init__(self, session):
        super().__init__(session)

    async def get_by_id(self, promocode_id: int) -> Optional[PromoCode]:
        """Получить промокод по ID"""
        return await self._get_one(PromoCode, PromoCode.id == promocode_id)

    async def get_by_code(self, code: str) -> Optional[PromoCode]:
        """Получить промокод по коду"""
        return await self._get_one(PromoCode, PromoCode.code == code)

    async def get_valid_by_code(self, code: str) -> Optional[PromoCode]:
        """Получить валидный промокод по коду"""
        try:
            result = await self.session.execute(
                select(PromoCode).where(
                    and_(
                        PromoCode.code == code,
                        PromoCode.valid_from <= datetime.now(),
                        PromoCode.valid_until >= datetime.now(),
                        PromoCode.used_count < PromoCode.usage_limit
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Ошибка поиска валидного промокода '{code}': {e}", exc_info=True)
            return None

    async def get_all(self, include_inactive: bool = False) -> List[PromoCode]:
        """Получить все промокоды"""
        try:
            query = select(PromoCode).order_by(PromoCode.valid_until.desc())

            if not include_inactive:
                query = query.where(PromoCode.valid_until >= datetime.now())

            result = await self._execute_query(query)
            return list(result.scalars().all())
        except Exception as e:
            self.logger.error(f"Ошибка получения промокодов: {e}", exc_info=True)
            return []

    async def check_code_exists(self, code: str) -> bool:
        """Проверить существование промокода с таким кодом"""
        return await self._exists(PromoCode, PromoCode.code == code)

    async def create_promocode(
        self,
        code: str,
        discount_type: DiscountType,
        discount_value: int,
        valid_from: datetime,
        valid_until: datetime,
        usage_limit: int = 1
    ) -> PromoCode:
        """Создать промокод с проверкой уникальности кода"""
        try:
            # Проверяем, нет ли уже промокода с таким кодом
            existing_promo = await self.get_by_code(code)
            if existing_promo:
                self.logger.warning(f"Промокод с кодом '{code}' уже существует")
                raise ValueError(f"Промокод с кодом '{code}' уже существует")

            # Создаем промокод
            promocode = PromoCode(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                valid_from=valid_from,
                valid_until=valid_until,
                usage_limit=usage_limit,
                used_count=0
            )

            self.session.add(promocode)
            await self.session.commit()
            await self.session.refresh(promocode)

            self.logger.info(f"Промокод создан: ID={promocode.id}, code='{promocode.code}'")
            return promocode

        except ValueError as e:
            self.logger.warning(f"Ошибка валидации при создании промокода: {e}")
            await self.session.rollback()
            raise

        except Exception as e:
            self.logger.error(f"Ошибка создания промокода: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def update_promocode(self, promocode_id: int, **update_data) -> bool:
        """Обновить данные промокода"""
        clean_data = {k: v for k, v in update_data.items() if v is not None}
        if not clean_data:
            return False

        updated_count = await self._update(PromoCode, PromoCode.id == promocode_id, **clean_data)
        return updated_count > 0

    async def increment_usage(self, promocode_id: int) -> bool:
        """Увеличить счетчик использований промокода"""
        return await self._update(
            PromoCode,
            PromoCode.id == promocode_id,
            used_count=PromoCode.used_count + 1
        ) > 0

    async def deactivate(self, promocode_id: int) -> bool:
        """Деактивировать промокод"""
        return await self._update(
            PromoCode,
            PromoCode.id == promocode_id,
            valid_until=datetime.now()
        ) > 0

    async def get_usage_count(self, promocode_id: int) -> int:
        """Получить количество использований промокода"""
        promocode = await self.get_by_id(promocode_id)
        return promocode.used_count if promocode else 0
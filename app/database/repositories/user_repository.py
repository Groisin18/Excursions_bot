"""Репозиторий для работы с пользователями (CRUD операции)"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.database.models import User, UserRole, ExcursionSlot, SlotStatus
from app.utils.validation import validate_phone
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class UserRepository(BaseRepository):
    """Репозиторий для CRUD операций с пользователями"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)


# ===== Простые поиски =====


    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        return await self._get_one(User, User.id == user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        return await self._get_one(User, User.telegram_id == telegram_id)

    async def get_by_phone(self, phone_number: str) -> Optional[User]:
        """Получить пользователя по номеру телефона"""
        try:
            original_phone = phone_number
            self.logger.debug(f"Поиск пользователя по телефону: {original_phone}")

            # Нормализация номера
            normalized_phone = validate_phone(phone_number)
            self.logger.debug(f"Нормализованный номер: {normalized_phone}")

            user = await self._get_one(User, User.phone_number == normalized_phone)

            if user:
                self.logger.debug(f"Пользователь найден по телефону: {user.id}")
            else:
                self.logger.debug(f"Пользователь с телефоном {original_phone} не найден")

            return user
        except Exception as e:
            self.logger.error(f"Ошибка при поиске пользователя по телефону: {e}", exc_info=True)
            return None

    async def get_by_token(self, token: str) -> Optional[User]:
        """Получить пользователя по токену"""
        return await self._get_one(User, User.verification_token == token)


# ===== Поиск нескольких записей =====


    async def get_users_by_role(self, role: UserRole) -> List[User]:
        """Получить пользователей по роли"""

        query = select(User).where(User.role == role)
        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def get_users_created_by(self, creator_id: int) -> List[User]:
        """Получить всех пользователей, созданных указанным пользователем"""
        return await self._get_many(User, User.created_by_id == creator_id)

    async def get_children_users(self, parent_id: int) -> List[User]:
        """Получить всех детей пользователя"""
        return await self._get_many(User, User.linked_to_parent_id == parent_id)

    async def get_all_captains(self) -> List[User]:
        """Получить всех капитанов"""
        return await self._get_many(User, User.role == UserRole.captain)


# ===== Проверки существования =====


    async def check_user_exists(self, telegram_id: int) -> bool:
        """Проверить, существует ли пользователь с таким Telegram ID"""
        return await self._exists(User, User.telegram_id == telegram_id)

    async def check_phone_exists(self, phone_number: str) -> bool:
        """Проверить, существует ли пользователь с таким номером телефона"""
        try:
            # Нормализуем телефон
            normalized_phone = validate_phone(phone_number)
            return await self._exists(User, User.phone_number == normalized_phone)
        except Exception as e:
            self.logger.error(f"Ошибка проверки существования телефона: {e}", exc_info=True)
            return False

    async def user_has_children(self, user_id: int) -> bool:
        """Проверить есть ли у пользователя дети"""
        return await self._exists(User, User.linked_to_parent_id == user_id)


# ===== Создание записей =====


    async def create(self, **user_data) -> User:
        """Создать пользователя (базовая версия, без токенов)"""
        return await self._create(User, **user_data)


# ===== Обновление записей =====


    async def update(self, user_id: int, **update_data) -> bool:
        """Обновить данные пользователя"""
        # Удаляем None значения
        clean_data = {k: v for k, v in update_data.items() if v is not None}
        if not clean_data:
            self.logger.warning("Нет данных для обновления")
            return False

        updated_count = await self._update(User, User.id == user_id, **clean_data)
        return updated_count > 0


# ===== Изменение ролей =====


    async def promote_to_admin(self, telegram_id: int) -> bool:
        """Повысить пользователя до администратора"""
        updated_count = await self._update(User, User.telegram_id == telegram_id,
                                          role=UserRole.admin)
        return updated_count > 0

    async def promote_to_captain(self, telegram_id: int) -> bool:
        """Повысить пользователя до капитана"""
        updated_count = await self._update(User, User.telegram_id == telegram_id,
                                          role=UserRole.captain)
        return updated_count > 0

    async def promote_to_client(self, telegram_id: int) -> bool:
        """Понизить пользователя до клиента"""
        updated_count = await self._update(User, User.telegram_id == telegram_id,
                                          role=UserRole.client)
        return updated_count > 0


# ===== Особые методы =====


    async def get_available_captains(self, start_datetime: datetime,
                                   end_datetime: datetime) -> List[User]:
        """Получить капитанов, свободных в указанный период времени"""
        query = (
            select(User)
            .where(User.role == UserRole.captain)
            .where(
                ~exists().where(
                    and_(
                        ExcursionSlot.captain_id == User.id,
                        ExcursionSlot.status.in_([SlotStatus.scheduled, SlotStatus.in_progress]),
                        ExcursionSlot.start_datetime < end_datetime,
                        ExcursionSlot.end_datetime > start_datetime
                    )
                )
            )
            .order_by(User.full_name)
        )

        result = await self._execute_query(query)
        return list(result.scalars().all())

    async def check_captain_availability(
        self,
        captain_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_slot_id: int = None
    ) -> bool:
        """Проверить, занят ли капитан в указанное время

        Returns:
            bool: True если капитан занят, False если свободен
        """
        try:
            conditions = [
                ExcursionSlot.captain_id == captain_id,
                ExcursionSlot.status.in_([SlotStatus.scheduled, SlotStatus.in_progress]),
                ExcursionSlot.start_datetime < end_datetime,
                ExcursionSlot.end_datetime > start_datetime
            ]

            if exclude_slot_id:
                conditions.append(ExcursionSlot.id != exclude_slot_id)

            query = select(ExcursionSlot).where(and_(*conditions))
            result = await self._execute_query(query)
            conflicting_slots = result.scalars().all()

            return len(conflicting_slots) > 0

        except Exception as e:
            self.logger.error(f"Ошибка проверки доступности капитана: {e}", exc_info=True)
            return True  # В случае ошибки считаем, что капитан занят
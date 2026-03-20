"""Репозиторий для работы с системными настройками"""

from typing import Optional, Dict
from sqlalchemy import select

from .base import BaseRepository
from app.database.models import SystemSetting


class SettingsRepository(BaseRepository):
    """Репозиторий для CRUD операций с системными настройками"""

    def __init__(self, session):
        super().__init__(session)

    async def get_by_key(self, key: str) -> Optional[SystemSetting]:
        """Получить настройку по ключу"""
        return await self._get_one(SystemSetting, SystemSetting.key == key)

    async def get_value(self, key: str, default: str = None) -> Optional[str]:
        """Получить значение настройки по ключу"""
        setting = await self.get_by_key(key)
        return setting.value if setting else default

    async def get_all(self) -> Dict[str, str]:
        """Получить все настройки в виде словаря"""
        try:
            query = select(SystemSetting)
            result = await self._execute_query(query)
            settings = result.scalars().all()
            return {s.key: s.value for s in settings}
        except Exception as e:
            self.logger.error(f"Ошибка получения всех настроек: {e}", exc_info=True)
            return {}

    async def set(self, key: str, value: str, description: str = None, updated_by: int = None) -> bool:
        """Установить значение настройки (создать или обновить)"""
        try:
            existing = await self.get_by_key(key)

            if existing:
                update_data = {'value': value}
                if description:
                    update_data['description'] = description
                if updated_by:
                    update_data['updated_by'] = updated_by

                updated = await self._update(
                    SystemSetting,
                    SystemSetting.key == key,
                    **update_data
                )
                return updated > 0
            else:
                setting_data = {
                    'key': key,
                    'value': value,
                    'description': description,
                    'updated_by': updated_by
                }
                await self._create(SystemSetting, **setting_data)
                return True

        except Exception as e:
            self.logger.error(f"Ошибка установки настройки {key}: {e}", exc_info=True)
            return False

    async def get_int(self, key: str, default: int = 0) -> int:
        """Получить целочисленное значение настройки"""
        value = await self.get_value(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            self.logger.warning(f"Не удалось преобразовать настройку {key}={value} в int")
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Получить булево значение настройки"""
        value = await self.get_value(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
"""Репозиторий для работы с файлами Telegram (CRUD операции)"""

from typing import Optional, List
from sqlalchemy import select, delete, exists

from .base import BaseRepository
from app.database.models import TelegramFile, FileType


class FileRepository(BaseRepository):
    """Репозиторий для CRUD операций с файлами Telegram"""

    def __init__(self, session):
        super().__init__(session)

    async def save_file_id(
        self,
        file_type: FileType,
        file_telegram_id: str,
        file_name: str,
        file_size: int,
        uploaded_by: int
    ) -> TelegramFile:
        """
        Сохранить file_id, удалив старый того же типа
        """
        try:
            # Удаляем старый файл того же типа
            deleted_count = await self._delete(
                TelegramFile,
                TelegramFile.file_type == file_type
            )

            if deleted_count > 0:
                self.logger.info(f"Удален старый файл типа {file_type.value}")

            # Создаем новый файл
            file = TelegramFile(
                file_type=file_type,
                file_telegram_id=file_telegram_id,
                file_name=file_name,
                file_size=file_size,
                uploaded_by=uploaded_by
            )

            saved_file = await self._create(file)
            self.logger.info(f"Сохранен новый файл типа {file_type.value}, ID={saved_file.id}")

            return saved_file

        except Exception as e:
            self.logger.error(f"Ошибка сохранения файла: {e}", exc_info=True)
            raise

    async def get_file_id(self, file_type: FileType) -> Optional[str]:
        """Получить последний file_id по типу"""
        try:
            file = await self._get_one(
                TelegramFile,
                TelegramFile.file_type == file_type
            )
            return file.file_telegram_id if file else None
        except Exception as e:
            self.logger.error(f"Ошибка получения file_id для типа {file_type.value}: {e}")
            return None

    async def get_file_record(self, file_type: FileType) -> Optional[TelegramFile]:
        """Получить последнюю запись о файле по типу"""
        try:
            files = await self._get_many(
                TelegramFile,
                TelegramFile.file_type == file_type,
                order_by=TelegramFile.uploaded_at.desc(),
                limit=1
            )
            return files[0] if files else None
        except Exception as e:
            self.logger.error(f"Ошибка получения записи файла для типа {file_type.value}: {e}")
            return None

    async def file_exists(self, file_type: FileType) -> bool:
        """Проверить существование файла по типу"""
        return await self._exists(TelegramFile, TelegramFile.file_type == file_type)

    async def get_all_file_records(self) -> List[TelegramFile]:
        """Получить все записи о файлах"""
        return await self._get_many(
            TelegramFile,
            order_by=TelegramFile.uploaded_at.desc()
        )

    async def get_files_by_uploader(self, uploaded_by: int) -> List[TelegramFile]:
        """Получить файлы, загруженные пользователем"""
        return await self._get_many(
            TelegramFile,
            TelegramFile.uploaded_by == uploaded_by,
            order_by=TelegramFile.uploaded_at.desc()
        )
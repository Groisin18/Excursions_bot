"""
Базовый репозиторий для всех репозиториев БД.
Содержит общие CRUD операции с обработкой ошибок и логированием.
"""

from typing import Type, TypeVar, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import SQLAlchemyError

from app.utils.logging_config import get_logger

# Тип для моделей SQLAlchemy
Model = TypeVar('Model')


class BaseRepository:
    """Базовый класс репозитория для операций с БД"""

    def __init__(self, session: AsyncSession):
        """
        Инициализация репозитория

        Args:
            session: Асинхронная сессия SQLAlchemy
        """
        self.session = session
        self.logger = get_logger(f"{self.__class__.__name__}")

    async def _get_one(
        self,
        model_class: Type[Model],
        *conditions: Any
    ) -> Optional[Model]:
        """
        Получить одну запись по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации (например, User.id == 123)

        Returns:
            Объект модели или None если не найден
        """
        try:
            query = select(model_class)
            if conditions:
                query = query.where(*conditions)

            self.logger.debug(f"Поиск одной записи {model_class.__name__}: {conditions}")
            result = await self.session.execute(query)
            entity = result.scalar_one_or_none()

            if entity:
                self.logger.debug(f"Запись {model_class.__name__} найдена: ID={entity.id}")
            else:
                self.logger.debug(f"Запись {model_class.__name__} не найдена по условиям: {conditions}")

            return entity

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка при поиске записи {model_class.__name__}: {e}",
                exc_info=True
            )
            return None

    async def _get_many(
        self,
        model_class: Type[Model],
        *conditions: Any,
        order_by: Optional[Any] = None,
        limit: Optional[int] = None
    ) -> List[Model]:
        """
        Получить несколько записей по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации
            order_by: Поле для сортировки
            limit: Максимальное количество записей

        Returns:
            Список объектов модели
        """
        try:
            query = select(model_class)
            if conditions:
                query = query.where(*conditions)
            if order_by:
                query = query.order_by(order_by)
            if limit:
                query = query.limit(limit)

            self.logger.debug(
                f"Поиск записей {model_class.__name__}: "
                f"conditions={conditions}, limit={limit}"
            )

            result = await self.session.execute(query)
            entities = result.scalars().all()

            self.logger.info(f"Найдено записей {model_class.__name__}: {len(entities)}")
            return list(entities)

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка при поиске записей {model_class.__name__}: {e}",
                exc_info=True
            )
            return []

    async def _execute_query(self, query: Any) -> Any:
        """
        Выполнить произвольный запрос

        Args:
            query: SQLAlchemy запрос (select, update, delete)

        Returns:
            Результат выполнения запроса
        """
        try:
            self.logger.debug(f"Выполнение запроса: {str(query)[:100]}...")
            result = await self.session.execute(query)
            return result

        except SQLAlchemyError as e:
            self.logger.error(f"Ошибка выполнения запроса: {e}", exc_info=True)
            raise

    async def _create(self, model_class: Type[Model], **data: Any) -> Model:
        """
        Создать новую запись

        Args:
            model_class: Класс модели SQLAlchemy
            **data: Данные для создания записи

        Returns:
            Созданный объект модели

        Raises:
            SQLAlchemyError: При ошибке создания
        """
        try:
            self.logger.info(
                f"Создание записи {model_class.__name__}: "
                f"{list(data.keys())}"
            )

            entity = model_class(**data)
            self.session.add(entity)
            await self.session.commit()
            await self.session.refresh(entity)

            self.logger.info(f"Запись {model_class.__name__} создана: ID={entity.id}")
            return entity

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка создания записи {model_class.__name__}: {e}",
                exc_info=True
            )
            await self.session.rollback()
            raise

    async def _update(
        self,
        model_class: Type[Model],
        *conditions: Any,
        **data: Any
    ) -> int:
        """
        Обновить записи по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации
            **data: Данные для обновления

        Returns:
            Количество обновленных записей
        """
        try:
            if not data:
                self.logger.warning("Нет данных для обновления")
                return 0

            stmt = (
                update(model_class)
                .where(*conditions)
                .values(**data)
            )

            self.logger.info(
                f"Обновление {model_class.__name__}: "
                f"conditions={conditions}, fields={list(data.keys())}"
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            updated_count = result.rowcount
            self.logger.info(
                f"Обновлено записей {model_class.__name__}: {updated_count}"
            )

            return updated_count

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка обновления {model_class.__name__}: {e}",
                exc_info=True
            )
            await self.session.rollback()
            return 0

    async def _delete(self, model_class: Type[Model], *conditions: Any) -> int:
        """
        Удалить записи по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации

        Returns:
            Количество удаленных записей
        """
        try:
            stmt = delete(model_class).where(*conditions)

            self.logger.info(f"Удаление {model_class.__name__}: conditions={conditions}")

            result = await self.session.execute(stmt)
            await self.session.commit()

            deleted_count = result.rowcount
            self.logger.info(f"Удалено записей {model_class.__name__}: {deleted_count}")

            return deleted_count

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка удаления {model_class.__name__}: {e}",
                exc_info=True
            )
            await self.session.rollback()
            return 0

    async def _exists(self, model_class: Type[Model], *conditions: Any) -> bool:
        """
        Проверить существование записи по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации

        Returns:
            True если запись существует, иначе False
        """
        try:
            query = select(1).select_from(model_class).where(*conditions).limit(1)

            self.logger.debug(f"Проверка существования {model_class.__name__}: {conditions}")

            result = await self.session.execute(query)
            exists = result.first() is not None

            self.logger.debug(f"Запись {model_class.__name__} существует: {exists}")
            return exists

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка проверки существования {model_class.__name__}: {e}",
                exc_info=True
            )
            return False

    async def _count(self, model_class: Type[Model], *conditions: Any) -> int:
        """
        Подсчитать количество записей по условиям

        Args:
            model_class: Класс модели SQLAlchemy
            *conditions: Условия фильтрации

        Returns:
            Количество записей
        """
        try:
            query = select(func.count()).select_from(model_class)
            if conditions:
                query = query.where(*conditions)

            self.logger.debug(f"Подсчет {model_class.__name__}: {conditions}")

            result = await self.session.execute(query)
            count = result.scalar() or 0

            self.logger.debug(f"Количество {model_class.__name__}: {count}")
            return count

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка подсчета {model_class.__name__}: {e}",
                exc_info=True
            )
            return 0

    async def _bulk_create(self, model_class: Type[Model], data_list: List[dict]) -> List[Model]:
        """
        Массовое создание записей

        Args:
            model_class: Класс модели SQLAlchemy
            data_list: Список словарей с данными

        Returns:
            Список созданных объектов
        """
        try:
            self.logger.info(
                f"Массовое создание {model_class.__name__}: "
                f"{len(data_list)} записей"
            )

            entities = [model_class(**data) for data in data_list]
            self.session.add_all(entities)
            await self.session.commit()

            # Обновляем объекты чтобы получить ID
            for entity in entities:
                await self.session.refresh(entity)

            self.logger.info(
                f"Массовое создание завершено: {len(entities)} записей"
            )
            return entities

        except SQLAlchemyError as e:
            self.logger.error(
                f"Ошибка массового создания {model_class.__name__}: {e}",
                exc_info=True
            )
            await self.session.rollback()
            raise
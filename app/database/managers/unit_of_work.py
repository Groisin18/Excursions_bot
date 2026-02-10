"""
Паттерн Unit of Work (Единица работы) для управления транзакциями.
Обеспечивает атомарность операций: либо все изменения сохраняются, либо ни одного.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """
    Unit of Work для управления транзакциями БД.

    Использование:
        async with UnitOfWork(session) as uow:
            # Работа с БД
            user_repo = UserRepository(uow.session)
            await user_repo.create(...)
            # Автоматический commit при успехе или rollback при ошибке
    """

    def __init__(self, session: AsyncSession):
        """
        Инициализация Unit of Work

        Args:
            session: Асинхронная сессия SQLAlchemy
        """
        self.session = session
        self._is_committed = False
        self._is_rolled_back = False

    @property
    def is_active(self) -> bool:
        """Проверить, активна ли транзакция"""
        return not (self._is_committed or self._is_rolled_back)

    async def commit(self) -> None:
        """Зафиксировать все изменения в БД"""
        if self._is_committed:
            raise RuntimeError("Транзакция уже зафиксирована")
        if self._is_rolled_back:
            raise RuntimeError("Транзакция уже откачена")

        await self.session.commit()
        self._is_committed = True

    async def rollback(self) -> None:
        """Откатить все изменения"""
        if self._is_committed:
            raise RuntimeError("Транзакция уже зафиксирована, нельзя откатить")
        if self._is_rolled_back:
            return  # Уже откачено

        await self.session.rollback()
        self._is_rolled_back = True

    async def __aenter__(self) -> 'UnitOfWork':
        """
        Вход в контекстный менеджер.
        Возвращает сам объект UnitOfWork для использования в блоке with.
        """
        # Начинаем транзакцию (сессия уже должна быть открыта)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Выход из контекстного менеджера.
        Автоматически выполняет commit или rollback в зависимости от исключения.
        """
        try:
            if exc_type is None and not self._is_committed:
                # Нет исключения → коммитим
                await self.commit()
            elif not self._is_rolled_back:
                # Есть исключение → откатываем
                await self.rollback()
        finally:
            # Закрываем сессию
            await self.session.close()

    def __repr__(self) -> str:
        """Строковое представление для отладки"""
        status = "active"
        if self._is_committed:
            status = "committed"
        elif self._is_rolled_back:
            status = "rolled back"

        return f"UnitOfWork(session_id={id(self.session)}, status={status})"
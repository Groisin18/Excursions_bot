"""
Базовый класс для всех менеджеров бизнес-логики.
Содержит только инфраструктурные методы (сессия, логирование, транзакции).
Бизнес-логика реализуется в конкретных менеджерах.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logging_config import get_logger


class BaseManager:
    """Базовый класс менеджера"""

    def __init__(self, session: AsyncSession):
        """
        Инициализация менеджера

        Args:
            session: Асинхронная сессия SQLAlchemy
        """
        self.session = session
        self.logger = get_logger(f"{self.__class__.__name__}")

    async def _commit(self) -> None:
        """Зафиксировать изменения в БД"""
        try:
            await self.session.commit()
            self.logger.debug("Изменения зафиксированы в БД")
        except Exception as e:
            self.logger.error(f"Ошибка при коммите: {e}", exc_info=True)
            await self._rollback()
            raise

    async def _rollback(self) -> None:
        """Откатить изменения в БД"""
        try:
            await self.session.rollback()
            self.logger.debug("Изменения откачены в БД")
        except Exception as e:
            self.logger.error(f"Ошибка при откате: {e}", exc_info=True)
            # Пробрасываем дальше, так как это критическая ошибка
            raise

    async def _refresh(self, entity: Any) -> None:
        """Обновить состояние объекта из БД"""
        try:
            await self.session.refresh(entity)
            self.logger.debug(f"Объект обновлен: {type(entity).__name__}")
        except Exception as e:
            self.logger.error(f"Ошибка обновления объекта: {e}", exc_info=True)
            # Не пробрасываем, так как это не критично для бизнес-логики

    async def _execute_in_transaction(self, operation, *args, **kwargs):
        """
        Выполнить операцию в транзакции с автоматическим rollback при ошибке

        Args:
            operation: Функция для выполнения
            *args, **kwargs: Аргументы для функции

        Returns:
            Результат выполнения операции
        """
        try:
            result = await operation(*args, **kwargs)
            await self._commit()
            return result
        except Exception as e:
            await self._rollback()
            self.logger.error(
                f"Ошибка в транзакции {operation.__name__}: {e}",
                exc_info=True
            )
            raise

    def _log_operation_start(self, operation_name: str, **context) -> None:
        """Залогировать начало операции"""
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        self.logger.info(f"Начало операции '{operation_name}': {context_str}")

    def _log_operation_end(self, operation_name: str, success: bool = True, **result) -> None:
        """Залогировать завершение операции"""
        status = "успешно" if success else "с ошибкой"
        result_str = f", результат: {result}" if result else ""
        self.logger.info(f"Операция '{operation_name}' завершена {status}{result_str}")

    def _log_business_event(self, event_type: str, **details) -> None:
        """Залогировать бизнес-событие"""
        details_str = ", ".join(f"{k}={v}" for k, v in details.items())
        self.logger.info(f"Бизнес-событие '{event_type}': {details_str}")
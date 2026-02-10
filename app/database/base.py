from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.logging_config import get_logger

class BaseRepository:
    """Базовый репозиторий для CRUD операций"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(f"{self.__class__.__name__}")

class BaseManager:
    """Базовый менеджер для бизнес-логики"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(f"{self.__class__.__name__}")
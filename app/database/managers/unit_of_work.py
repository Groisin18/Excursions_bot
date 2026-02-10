from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories import (
    UserRepository, BookingRepository,
    SlotRepository, PaymentRepository
)
from . import (
    UserManager, BookingManager,
    SlotManager, PaymentManager
)

class UnitOfWork:
    """Паттерн Unit of Work для управления транзакциями"""

    def __init__(self, session: AsyncSession):
        self.session = session

        # Репозитории
        self.users = UserRepository(session)
        self.bookings = BookingRepository(session)
        self.slots = SlotRepository(session)
        self.payments = PaymentRepository(session)

        # Менеджеры
        self.user_manager = UserManager(session)
        self.booking_manager = BookingManager(session)
        self.slot_manager = SlotManager(session)
        self.payment_manager = PaymentManager(session)

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.session.close()
import enum
from typing import Optional, List
from datetime import datetime, date

from sqlalchemy import BigInteger, String, Integer, Boolean, Text, Date, DateTime, Enum, ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import func

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """Конфигурация базы данных для телеграм-бота"""

    DB_URL = 'sqlite+aiosqlite:///database.db'
    CONNECT_ARGS = {
        'check_same_thread': False,
        'timeout': 15,
    }

    # WAL настройки
    WAL_SETTINGS = [
        ("PRAGMA journal_mode=WAL", "WAL режим"),
        ("PRAGMA synchronous=NORMAL", "Баланс скорость/безопасность"),
        ("PRAGMA wal_autocheckpoint=15", "Авто checkpoint"),
        ("PRAGMA cache_size=-2000", "Кэш 2MB"),
        ("PRAGMA mmap_size=268435456", "MMAP 256MB"),
        ("PRAGMA foreign_keys=ON", "Внешние ключи"),
        ("PRAGMA busy_timeout=5000", "Таймаут блокировки"),
    ]


engine = create_async_engine(
    url=DatabaseConfig.DB_URL,
    echo=False,  # True только для отладки SQL
    poolclass=NullPool,
    connect_args=DatabaseConfig.CONNECT_ARGS,
    execution_options={
        "timeout": 15
    }
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy"""
    pass

class UserRole(enum.Enum):
    """Роли пользователей в системе"""
    client = "client"
    captain = "captain"
    admin = "admin"

class SlotStatus(enum.Enum):
    """Статусы слотов экскурсий"""
    scheduled = "scheduled"
    cancelled = "cancelled"
    completed = "completed"
    in_progress = "in_progress"

class BookingStatus(enum.Enum):
    """Статусы бронирований"""
    active = "active"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"

class ClientStatus(enum.Enum):
    """Статусы присутствия клиентов"""
    not_arrived = "not_arrived"
    arrived = "arrived"

class PaymentStatus(enum.Enum):
    """Статусы оплаты"""
    not_paid = "not_paid"
    pending = "pending"
    paid = "paid"
    refunded = "refunded"

class PaymentMethod(enum.Enum):
    """Методы оплаты"""
    cash = "cash"
    online = "online"

class YooKassaStatus(enum.Enum):
    """Статусы платежей YooKassa"""
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    waiting_for_capture = "waiting_for_capture"

class DiscountType(enum.Enum):
    """Типы скидок"""
    percent = "percent"
    fixed = "fixed"

class SalaryStatus(enum.Enum):
    """Статусы выплат зарплат"""
    calculated = "calculated"
    paid = "paid"

class NotificationType(enum.Enum):
    """Типы уведомлений"""
    new_booking = "new_booking"
    cancellation = "cancellation"
    reminder = "reminder"

class RegistrationType(enum.Enum):
    """Типы регистрации пользователей"""
    SELF = "self"
    ADMIN = "admin"
    PARENT = "parent"

# Логирование создания enum классов
logger.debug("Созданы enum классы для статусов и типов")

# Таблицы

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=True)
    email: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=True)
    consent_to_pd: Mapped[bool] = mapped_column(Boolean, default=True)
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=True, index=True)
    registration_type: Mapped[RegistrationType] = mapped_column(Enum(RegistrationType), default=RegistrationType.SELF, nullable=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_to_parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    token_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    bookings_as_client: Mapped[List["Booking"]] = relationship(
        "Booking",
        foreign_keys="Booking.client_id",
        back_populates="client",
        cascade="all, delete-orphan"
    )
    bookings_as_admin: Mapped[List["Booking"]] = relationship(
        "Booking",
        foreign_keys="Booking.admin_creator_id",
        back_populates="admin_creator"
    )
    slots_as_captain: Mapped[List["ExcursionSlot"]] = relationship(
        "ExcursionSlot",
        back_populates="captain",
        cascade="all, delete-orphan"
    )
    salaries: Mapped[List["Salary"]] = relationship(
        "Salary",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    expenses: Mapped[List["Expense"]] = relationship(
        "Expense",
        back_populates="created_by",
        cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        remote_side=[id],
        back_populates="created_users"
    )
    created_users: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[linked_to_parent_id],
        remote_side=[id],
        back_populates="children"
    )
    children: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys=[linked_to_parent_id],
        back_populates="parent",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Строковое представление пользователя для отладки"""
        return f"User(id={self.id}, telegram_id={self.telegram_id}, name='{self.full_name}', role={self.role.value})"

    def __str__(self) -> str:
        """Человекочитаемое представление пользователя"""
        return f"{self.full_name} ({self.role.value})"

    @property
    def has_active_token(self) -> bool:
        """Есть ли активный токен"""
        return self.verification_token is not None and self.telegram_id is None

    @property
    def is_self_registered(self) -> bool:
        """Зарегистрирован ли самостоятельно"""
        return self.registration_type == RegistrationType.SELF

    @property
    def is_virtual_phone(self) -> bool:
        """Имеет ли виртуальный телефон"""
        return self.phone_number and ":child" in self.phone_number

    @property
    def age(self) -> Optional[int]:
        """Возраст пользователя"""
        if not self.date_of_birth:
            return None

        today = date.today()
        age = today.year - self.date_of_birth.year

        # Проверяем, был ли уже день рождения в этом году
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1

        return age

    def to_dict(self) -> dict:
        """Преобразование пользователя в словарь (для логирования)"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'role': self.role.value,
            'full_name': self.full_name,
            'phone_number': self.phone_number[:3] + '***' + self.phone_number[-3:] if self.phone_number else None,
            'is_virtual': self.is_virtual,
            'registration_type': self.registration_type.value,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Excursion(Base):
    """Модель экскурсии"""
    __tablename__ = 'excursions'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    base_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)
    child_discount: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Relationships
    slots: Mapped[List["ExcursionSlot"]] = relationship(
        "ExcursionSlot",
        back_populates="excursion",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Строковое представление экскурсии для отладки"""
        return f"Excursion(id={self.id}, name='{self.name}', price={self.base_price}, active={self.is_active})"

    def __str__(self) -> str:
        """Человекочитаемое представление экскурсии"""
        return f"{self.name} ({self.base_price} руб, {self.base_duration_minutes} мин)"

    @property
    def child_price(self) -> int:
        """Цена для детей с учетом скидки"""
        if self.child_discount <= 0:
            return self.base_price

        discount_amount = int(self.base_price * self.child_discount / 100)
        return max(0, self.base_price - discount_amount)

    def to_dict(self) -> dict:
        """Преобразование экскурсии в словарь (для логирования)"""
        return {
            'id': self.id,
            'name': self.name,
            'base_price': self.base_price,
            'child_price': self.child_price,
            'duration_minutes': self.base_duration_minutes,
            'is_active': self.is_active
        }

class ExcursionSlot(Base):
    """Модель слота экскурсии (конкретное время проведения)"""
    __tablename__ = 'excursion_slots'

    id: Mapped[int] = mapped_column(primary_key=True)
    excursion_id: Mapped[int] = mapped_column(ForeignKey("excursions.id"), nullable=False, index=True)
    captain_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    max_people: Mapped[int] = mapped_column(Integer, nullable=False)
    max_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SlotStatus] = mapped_column(Enum(SlotStatus), default=SlotStatus.scheduled, index=True)

    # Relationships
    excursion: Mapped["Excursion"] = relationship("Excursion", back_populates="slots")
    captain: Mapped["User"] = relationship("User", back_populates="slots_as_captain")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="slot", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """Строковое представление слота для отладки"""
        return f"ExcursionSlot(id={self.id}, excursion={self.excursion_id}, start={self.start_datetime}, status={self.status.value})"

    def __str__(self) -> str:
        """Человекочитаемое представление слота"""
        return f"{self.excursion.name} в {self.start_datetime.strftime('%H:%M')} ({self.status.value})"

    @property
    def is_available(self) -> bool:
        """Доступен ли слот для бронирования"""
        return self.status == SlotStatus.scheduled and self.start_datetime > datetime.now()

    def to_dict(self) -> dict:
        """Преобразование слота в словарь (для логирования)"""
        return {
            'id': self.id,
            'excursion_id': self.excursion_id,
            'start_datetime': self.start_datetime.isoformat() if self.start_datetime else None,
            'end_datetime': self.end_datetime.isoformat() if self.end_datetime else None,
            'max_people': self.max_people,
            'status': self.status.value
        }

class Booking(Base):
    """Модель бронирования"""
    __tablename__ = 'bookings'

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("excursion_slots.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    admin_creator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    people_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    children_count: Mapped[int] = mapped_column(Integer, default=0)
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.active, index=True)
    client_status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus), default=ClientStatus.not_arrived)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.not_paid, index=True)
    promo_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("promo_codes.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # Relationships
    slot: Mapped["ExcursionSlot"] = relationship("ExcursionSlot", back_populates="bookings")
    client: Mapped["User"] = relationship("User", foreign_keys=[client_id], back_populates="bookings_as_client")
    admin_creator: Mapped["User"] = relationship("User", foreign_keys=[admin_creator_id], back_populates="bookings_as_admin")
    promo_code: Mapped["PromoCode"] = relationship("PromoCode", back_populates="bookings")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """Строковое представление бронирования для отладки"""
        return f"Booking(id={self.id}, slot={self.slot_id}, client={self.client_id}, status={self.booking_status.value})"

    def __str__(self) -> str:
        """Человекочитаемое представление бронирования"""
        return f"Бронирование #{self.id} ({self.people_count} чел., {self.total_price} руб.)"

    @property
    def adults_count(self) -> int:
        """Количество взрослых"""
        return self.people_count - self.children_count

    @property
    def is_active(self) -> bool:
        """Активно ли бронирование"""
        return self.booking_status == BookingStatus.active

    @property
    def is_paid(self) -> bool:
        """Оплачено ли бронирование"""
        return self.payment_status == PaymentStatus.paid

    def to_dict(self) -> dict:
        """Преобразование бронирования в словарь (для логирования)"""
        return {
            'id': self.id,
            'slot_id': self.slot_id,
            'client_id': self.client_id,
            'people_count': self.people_count,
            'children_count': self.children_count,
            'total_price': self.total_price,
            'booking_status': self.booking_status.value,
            'payment_status': self.payment_status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Payment(Base):
    """Модель платежа"""
    __tablename__ = 'payments'

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    yookassa_payment_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[YooKassaStatus] = mapped_column(Enum(YooKassaStatus), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")

    def __repr__(self) -> str:
        """Строковое представление платежа для отладки"""
        return f"Payment(id={self.id}, booking={self.booking_id}, amount={self.amount}, method={self.payment_method.value})"

    def __str__(self) -> str:
        """Человекочитаемое представление платежа"""
        method = "онлайн" if self.payment_method == PaymentMethod.online else "наличные"
        return f"Платеж #{self.id} ({self.amount} руб., {method})"

    @property
    def is_online(self) -> bool:
        """Онлайн ли платеж"""
        return self.payment_method == PaymentMethod.online

    @property
    def is_successful(self) -> bool:
        """Успешен ли платеж"""
        return self.status == YooKassaStatus.succeeded

    def to_dict(self) -> dict:
        """Преобразование платежа в словарь (для логирования)"""
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'amount': self.amount,
            'payment_method': self.payment_method.value,
            'status': self.status.value if self.status else None,
            'is_online': self.is_online,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PromoCode(Base):
    """Модель промокода"""
    __tablename__ = 'promo_codes'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType), nullable=False)
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    usage_limit: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="promo_code")

    def __repr__(self) -> str:
        """Строковое представление промокода для отладки"""
        return f"PromoCode(id={self.id}, code='{self.code}', type={self.discount_type.value}, value={self.discount_value})"

    def __str__(self) -> str:
        """Человекочитаемое представление промокода"""
        if self.discount_type == DiscountType.percent:
            discount_str = f"{self.discount_value}%"
        else:
            discount_str = f"{self.discount_value} руб."

        return f"Промокод {self.code} ({discount_str})"

    @property
    def is_valid(self) -> bool:
        """Действителен ли промокод"""
        now = datetime.now()
        return (
            self.valid_from <= now <= self.valid_until and
            self.used_count < self.usage_limit
        )

    @property
    def remaining_uses(self) -> int:
        """Оставшееся количество использований"""
        return max(0, self.usage_limit - self.used_count)

    def apply_discount(self, original_price: int) -> int:
        """Применить скидку к цене"""
        if self.discount_type == DiscountType.percent:
            discount = int(original_price * self.discount_value / 100)
        else:  # fixed
            discount = self.discount_value

        return max(0, original_price - discount)

    def to_dict(self) -> dict:
        """Преобразование промокода в словарь (для логирования)"""
        return {
            'id': self.id,
            'code': self.code,
            'discount_type': self.discount_type.value,
            'discount_value': self.discount_value,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'used_count': self.used_count,
            'usage_limit': self.usage_limit,
            'is_valid': self.is_valid,
            'remaining_uses': self.remaining_uses
        }

class Salary(Base):
    """Модель зарплаты"""
    __tablename__ = 'salaries'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    period: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    base_salary: Mapped[int] = mapped_column(Integer, default=0)
    bonus: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SalaryStatus] = mapped_column(Enum(SalaryStatus), default=SalaryStatus.calculated, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="salaries")

    def __repr__(self) -> str:
        """Строковое представление зарплаты для отладки"""
        return f"Salary(id={self.id}, user={self.user_id}, period={self.period}, amount={self.total_amount})"

    def __str__(self) -> str:
        """Человекочитаемое представление зарплаты"""
        return f"Зарплата за {self.period.strftime('%B %Y')}: {self.total_amount} руб."

    @property
    def is_paid(self) -> bool:
        """Выплачена ли зарплата"""
        return self.status == SalaryStatus.paid

    def to_dict(self) -> dict:
        """Преобразование зарплаты в словарь (для логирования)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'period': self.period.isoformat() if self.period else None,
            'base_salary': self.base_salary,
            'bonus': self.bonus,
            'total_amount': self.total_amount,
            'status': self.status.value,
            'is_paid': self.is_paid
        }

class Expense(Base):
    """Модель расхода"""
    __tablename__ = 'expenses'

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Relationships
    created_by: Mapped["User"] = relationship("User", back_populates="expenses")

    def __repr__(self) -> str:
        """Строковое представление расхода для отладки"""
        return f"Expense(id={self.id}, category='{self.category}', amount={self.amount}, date={self.expense_date})"

    def __str__(self) -> str:
        """Человекочитаемое представление расхода"""
        return f"Расход: {self.category} ({self.amount} руб.)"

    def to_dict(self) -> dict:
        """Преобразование расхода в словарь (для логирования)"""
        return {
            'id': self.id,
            'category': self.category,
            'amount': self.amount,
            'description': self.description,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'created_by_id': self.created_by_id
        }

class Notification(Base):
    """Модель уведомления"""
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        """Строковое представление уведомления для отладки"""
        return f"Notification(id={self.id}, user={self.user_id}, type={self.type.value}, delivered={self.is_delivered})"

    def __str__(self) -> str:
        """Человекочитаемое представление уведомления"""
        return f"Уведомление #{self.id} ({self.type.value})"

    @property
    def short_message(self) -> str:
        """Краткое содержание сообщения"""
        if len(self.message) <= 50:
            return self.message
        return self.message[:47] + "..."

    def to_dict(self) -> dict:
        """Преобразование уведомления в словарь (для логирования)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type.value,
            'message_short': self.short_message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'is_delivered': self.is_delivered
        }

# Функция для создания всех таблиц
async def init_models():
    """Инициализация базы данных"""
    logger.info("Инициализация базы данных...")

    try:
        # Открываем транзакцию для инициализации
        async with engine.begin() as conn:
            # Применяем WAL настройки и оптимизации
            for sql_setting, description in DatabaseConfig.WAL_SETTINGS:
                try:
                    await conn.execute(text(sql_setting))
                    logger.debug(f"Применено: {description}")
                except Exception as e:
                    logger.warning(f"Не удалось применить {description}: {e}")

            # Создаем таблицы
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы созданы/проверены")

            # Создаем дополнительные индексы
            indexes_sql = [
                "CREATE INDEX IF NOT EXISTS idx_bookings_client_id_status ON bookings(client_id, booking_status)",
                "CREATE INDEX IF NOT EXISTS idx_bookings_created_at_status ON bookings(created_at, booking_status)",
                "CREATE INDEX IF NOT EXISTS idx_excursion_slots_start_status ON excursion_slots(start_datetime, status)",
                "CREATE INDEX IF NOT EXISTS idx_payments_created_at_status ON payments(created_at, status)",
                "CREATE INDEX IF NOT EXISTS idx_users_role_created_at ON users(role, created_at)",
            ]

            for index_sql in indexes_sql:
                try:
                    await conn.execute(text(index_sql))
                except Exception as e:
                    logger.warning(f"Не удалось создать индекс: {e}")

        # Проверяем созданные таблицы
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = [row[0] for row in result.fetchall()]

            logger.info(f"Всего таблиц в БД: {len(tables)}")
            logger.debug(f"Таблицы: {', '.join(tables)}")

            # ИСПРАВЛЕНО: синхронный метод
            result = await conn.execute(text("PRAGMA journal_mode"))
            journal_row = result.fetchone()
            journal_mode = journal_row[0] if journal_row else "unknown"
            logger.info(f"Режим журналирования: {journal_mode}")

        logger.info("База данных успешно инициализирована с WAL-режимом")

    except Exception as e:
        logger.critical(f"Ошибка инициализации БД: {e}", exc_info=True)
        raise
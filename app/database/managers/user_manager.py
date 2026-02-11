"""
Менеджер для бизнес-логики пользователей.
Содержит сложные операции с пользователями: создание через токены,
работа с детьми, привязка Telegram и т.д.
"""
import secrets

from datetime import datetime, date, timedelta
from typing import Optional, Tuple
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from .salary_manager import SalaryManager
from ..repositories.user_repository import UserRepository
from ..models import User, UserRole, RegistrationType

from app.routers.user.account.models import UserRegistrationData, ChildRegistrationData


class UserManager(BaseManager):
    """Менеджер для бизнес-логики пользователей"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_repo = UserRepository(session)

    async def _create_user_internal(
        self,
        telegram_id: Optional[int],
        full_name: str,
        role: UserRole,
        phone_number: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        address: Optional[str] = None,
        weight: Optional[int] = None,
        consent_to_pd: bool = False,
        is_virtual: bool = False,
        verification_token: Optional[str] = None,
        registration_type: RegistrationType = RegistrationType.SELF,
        created_by_id: Optional[int] = None,
        linked_to_parent_id: Optional[int] = None
    ) -> User:
        """Базовое создание пользователя в БД"""
        self._log_operation_start("_create_user_internal",
                                name=full_name,
                                telegram_id=telegram_id,
                                role=role.value,
                                is_virtual=is_virtual)

        try:
            user_data = {
                'telegram_id': telegram_id,
                'full_name': full_name,
                'role': role,
                'phone_number': phone_number,
                'date_of_birth': date_of_birth,
                'address': address,
                'weight': weight,
                'consent_to_pd': consent_to_pd,
                'is_virtual': is_virtual,
                'verification_token': verification_token,
                'registration_type': registration_type,
                'created_by_id': created_by_id,
                'linked_to_parent_id': linked_to_parent_id,
                'token_created_at': datetime.now() if verification_token else None
            }

            user = await self.user_repo.create(**user_data)

            self._log_operation_end("_create_user_internal",
                                success=True,
                                user_id=user.id)
            return user

        except Exception as e:
            self._log_operation_end("_create_user_internal", success=False)
            self.logger.error(f"Ошибка создания пользователя: {e}", exc_info=True)
            raise

    async def create_adult_user(
        self,
        telegram_id: int,
        user_data: UserRegistrationData
    ) -> User:
        """Создать взрослого пользователя (self-регистрация)"""
        self._log_operation_start("create_adult_user",
                                name=f"{user_data.surname} {user_data.name}",
                                telegram_id=telegram_id)

        try:
            full_name = f"{user_data.surname} {user_data.name}"
            date_of_birth = datetime.strptime(user_data.date_of_birth, "%d.%m.%Y").date()

            user = await self._create_user_internal(
                telegram_id=telegram_id,
                full_name=full_name,
                role=UserRole.client,
                phone_number=user_data.phone,
                date_of_birth=date_of_birth,
                address=user_data.address,
                weight=user_data.weight,
                consent_to_pd=True,
                is_virtual=False,
                verification_token=None,
                registration_type=RegistrationType.SELF
            )

            self._log_operation_end("create_adult_user",
                                success=True,
                                user_id=user.id)
            return user

        except Exception as e:
            self._log_operation_end("create_adult_user", success=False)
            self.logger.error(f"Ошибка регистрации взрослого: {e}", exc_info=True)
            raise

    async def _create_virtual_user(
        self,
        full_name: str,
        created_by_id: int,
        registration_type: RegistrationType,
        phone_number: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        weight: Optional[int] = None,
        address: Optional[str] = None,
        linked_to_parent_id: Optional[int] = None
    ) -> Tuple[User, str]:
        """Создать виртуального пользователя с токеном"""
        self._log_operation_start("_create_virtual_user",
                                name=full_name,
                                created_by=created_by_id,
                                type=registration_type.value)

        try:
            # Генерация короткого токена
            token = secrets.token_urlsafe(4)

            # Виртуальный телефон для детей
            if linked_to_parent_id and not phone_number:
                parent = await self.user_repo.get_by_id(created_by_id)
                if parent and parent.phone_number:
                    phone_number = f"{parent.phone_number}:{token}:child"
                    self.logger.debug(f"Сгенерирован виртуальный телефон: {phone_number}")

            user = await self._create_user_internal(
                telegram_id=None,
                full_name=full_name,
                role=UserRole.client,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                weight=weight,
                address=address,
                consent_to_pd=False,
                is_virtual=True,
                verification_token=token,
                registration_type=registration_type,
                created_by_id=created_by_id,
                linked_to_parent_id=linked_to_parent_id
            )

            self._log_operation_end("_create_virtual_user",
                                success=True,
                                user_id=user.id,
                                token=token[:8])
            return user, token

        except Exception as e:
            self._log_operation_end("_create_virtual_user", success=False)
            self.logger.error(f"Ошибка создания виртуального пользователя: {e}", exc_info=True)
            raise

    async def create_user_by_admin(
        self,
        full_name: str,
        phone_number: str,
        admin_id: int,
        date_of_birth: date = None,
        address: str = None,
        weight: int = None
    ) -> Tuple[User, str]:
        """Администратор создает пользователя (без Telegram)"""
        self._log_operation_start("create_user_by_admin",
                                name=full_name,
                                admin_id=admin_id)

        try:
            # Бизнес-логика: проверка уникальности телефона
            existing_user = await self.user_repo.get_by_phone(phone_number)
            if existing_user:
                error_msg = f"Номер телефона {phone_number} уже зарегистрирован"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Создаем виртуального пользователя через новый protected метод
            user, token = await self._create_virtual_user(
                full_name=full_name,
                created_by_id=admin_id,
                registration_type=RegistrationType.ADMIN,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                weight=weight
            )

            # Дополнительная логика: обновление адреса
            if address:
                await self.user_repo.update(user.id, address=address)
                await self._refresh(user)

            self._log_operation_end("create_user_by_admin",
                                success=True,
                                user_id=user.id,
                                token=token)

            return user, token

        except ValueError as e:
            self._log_operation_end("create_user_by_admin", success=False)
            self.logger.warning(f"Ошибка валидации при создании пользователя админом: {e}")
            raise
        except Exception as e:
            self._log_operation_end("create_user_by_admin", success=False)
            self.logger.error(f"Ошибка создания пользователя админом '{full_name}': {e}", exc_info=True)
            raise

    async def create_child_user(
        self,
        child_data: ChildRegistrationData,
        parent_telegram_id: int
    ) -> Tuple[User, str]:
        """Родитель создает ребенка"""
        self._log_operation_start("create_child_user",
                                child_name=f"{child_data.surname} {child_data.name}",
                                parent_tg_id=parent_telegram_id)

        try:
            # Бизнес-логика: поиск родителя
            parent = await self.user_repo.get_by_telegram_id(parent_telegram_id)
            if not parent:
                error_msg = f"Родитель с Telegram ID {parent_telegram_id} не найден"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Проверка parent_id в данных
            if child_data.parent_id != parent.id:
                error_msg = f"ID родителя в данных ({child_data.parent_id}) не совпадает с найденным ({parent.id})"
                self.logger.warning(error_msg)
                child_data.parent_id = parent.id  # исправляем

            parent_id = parent.id
            self.logger.debug(f"Родитель найден: ID={parent_id}, имя='{parent.full_name}'")

            # Бизнес-логика: проверка лимита детей (7)
            children = await self.user_repo.get_children_users(parent_id)
            if len(children) >= 7:
                error_msg = "Достигнут лимит добавления детей (максимум 7)"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            self.logger.debug(f"У родителя {parent_id} сейчас {len(children)} детей (лимит: 7)")

            # Преобразование даты
            date_of_birth = datetime.strptime(child_data.date_of_birth, "%d.%m.%Y").date()

            # Полное имя
            full_name = f"{child_data.surname} {child_data.name}"

            # Создаем ребенка
            user, token = await self._create_virtual_user(
                full_name=full_name,
                created_by_id=parent_id,
                registration_type=RegistrationType.PARENT,
                date_of_birth=date_of_birth,
                weight=child_data.weight,
                address=child_data.address,
                linked_to_parent_id=parent_id
            )

            self._log_operation_end("create_child_user",
                                success=True,
                                child_id=user.id,
                                token=token)

            return user, token

        except ValueError as e:
            self._log_operation_end("create_child_user", success=False)
            self.logger.warning(f"Ошибка валидации при создании ребенка: {e}")
            raise
        except Exception as e:
            self._log_operation_end("create_child_user", success=False)
            self.logger.error(f"Ошибка создания ребенка '{child_data.name}': {e}", exc_info=True)
            raise

    async def link_telegram_to_user(self, token: str, telegram_id: int) -> Optional[User]:
        """Привязать Telegram ID к пользователю по токену"""
        self._log_operation_start("link_telegram_to_user",
                                 token=token[:8] + "...",
                                 telegram_id=telegram_id)

        try:
            # Бизнес-логика: проверка занятости Telegram ID
            existing_user = await self.user_repo.get_by_telegram_id(telegram_id)
            if existing_user:
                error_msg = f"Telegram ID {telegram_id} уже используется пользователем {existing_user.id}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Получаем пользователя по токену
            user = await self.user_repo.get_by_token(token)
            if not user:
                self.logger.warning(f"Пользователь с токеном {token[:8]}... не найден")
                return None

            # Бизнес-логика: проверка, что Telegram еще не привязан
            if user.telegram_id:
                error_msg = f"Пользователь уже привязан к Telegram ID {user.telegram_id}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Обновляем пользователя через репозиторий
            updated = await self.user_repo.update(
                user.id,
                telegram_id=telegram_id,
                is_virtual=False,
                verification_token=None,
                token_created_at=None
            )

            if not updated:
                error_msg = f"Не удалось обновить пользователя {user.id}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Получаем обновленного пользователя
            updated_user = await self.user_repo.get_by_id(user.id)

            self._log_operation_end("link_telegram_to_user",
                                   success=True,
                                   user_id=updated_user.id)

            return updated_user

        except ValueError as e:
            self._log_operation_end("link_telegram_to_user", success=False)
            self.logger.warning(f"Ошибка валидации при привязке Telegram: {e}")
            raise
        except Exception as e:
            self._log_operation_end("link_telegram_to_user", success=False)
            self.logger.error(f"Ошибка привязки Telegram ID {telegram_id}: {e}", exc_info=True)
            raise

    async def get_user_token(self, user_id: int) -> Optional[str]:
        """Получить токен пользователя"""
        self._log_operation_start("get_user_token", user_id=user_id)

        try:
            user = await self.user_repo.get_by_id(user_id)
            if user and user.verification_token:
                self._log_operation_end("get_user_token", success=True, has_token=True)
                return user.verification_token

            self._log_operation_end("get_user_token", success=True, has_token=False)
            return None
        except Exception as e:
            self._log_operation_end("get_user_token", success=False)
            self.logger.error(f"Ошибка получения токена пользователя {user_id}: {e}", exc_info=True)
            return None

    async def get_captains_with_stats(self, period_start=None):
        """Получить список капитанов со статистикой"""

        if period_start is None:
            period_start = date.today().replace(day=1)

        result = await self.session.execute(
            select(User)
            .where(User.role == UserRole.captain)
            .where(User.telegram_id.isnot(None))
        )
        captains = result.scalars().all()

        # Добавляем статистику для каждого капитана
        captains_with_stats = []
        for captain in captains:
            salary_manager = SalaryManager(self.session)
            captain_stats = await salary_manager.calculate_captain_salary(
                captain.id,
                period_start
            )
            captains_with_stats.append({
                'captain': captain,
                'stats': captain_stats
            })

        return captains_with_stats

    async def search_clients(self, search_query: str, limit: int = 5):
        """Поиск клиентов по имени или телефону"""

        result = await self.session.execute(
            select(User)
            .where(User.role == UserRole.client)
            .where(
                (User.full_name.ilike(f"%{search_query}%")) |
                (User.phone_number.ilike(f"%{search_query}%"))
            )
        )
        clients = result.scalars().all()

        return clients[:limit] if limit else clients

    async def get_new_clients(self, days_ago: int = 7):
        """Получить новых клиентов за последние N дней"""

        week_ago = datetime.now() - timedelta(days=days_ago)

        result = await self.session.execute(
            select(User)
            .where(User.role == UserRole.client)
            .where(User.created_at >= week_ago)
            .order_by(User.created_at.desc())
        )
        return result.scalars().all()
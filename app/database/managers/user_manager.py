"""
Менеджер для бизнес-логики пользователей.
Содержит сложные операции с пользователями: создание через токены,
работа с детьми, привязка Telegram и т.д.
"""

from datetime import datetime, date
from typing import Optional, Tuple
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from ..repositories.user_repository import UserRepository
from app.database.models import User, UserRole, RegistrationType


class UserManager(BaseManager):
    """Менеджер для бизнес-логики пользователей"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_repo = UserRepository(session)

    async def create_user_with_token(
        self,
        telegram_id: int,
        full_name: str,
        role: UserRole,
        phone_number: str = None,
        date_of_birth: date = None,
        address: str = None,
        weight: int = None,
        consent_to_pd: bool = False,
        registration_type: RegistrationType = RegistrationType.SELF,
        created_by_id: int = None,
        linked_to_parent_id: int = None,
        is_virtual: bool = None,
        verification_token: str = None
    ) -> User:
        """Создать пользователя с токеном (бизнес-логика)"""
        self._log_operation_start("create_user_with_token",
                                 name=full_name,
                                 telegram_id=telegram_id,
                                 role=role.value)

        try:
            # Бизнес-логика: определение is_virtual
            if is_virtual is None:
                is_virtual = telegram_id is None

            # Бизнес-логика: генерация токена для виртуальных пользователей
            if is_virtual and not verification_token:
                verification_token = secrets.token_urlsafe(32)
                self.logger.debug(f"Сгенерирован токен для виртуального пользователя")

            # Подготавливаем данные
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

            # Вызываем репозиторий для сохранения (CRUD операция)
            user = await self.user_repo.create(**user_data)

            self._log_operation_end("create_user_with_token",
                                   success=True,
                                   user_id=user.id,
                                   is_virtual=user.is_virtual)

            if verification_token:
                self.logger.debug(f"Токен пользователя {user.id}: {verification_token}")

            return user

        except Exception as e:
            self._log_operation_end("create_user_with_token", success=False)
            self.logger.error(f"Ошибка создания пользователя '{full_name}': {e}", exc_info=True)
            raise

    async def create_virtual_user(
        self,
        full_name: str,
        created_by_id: int,
        registration_type: RegistrationType,
        phone_number: str = None,
        date_of_birth: date = None,
        weight: int = None,
        address: str = None,
        linked_to_parent_id: int = None
    ) -> Tuple[User, str]:
        """Создать виртуального пользователя (без Telegram)"""
        self._log_operation_start("create_virtual_user",
                                 name=full_name,
                                 created_by=created_by_id,
                                 type=registration_type.value)

        try:
            # Бизнес-логика: генерация короткого токена
            token = secrets.token_urlsafe(4)

            # Бизнес-логика: генерация виртуального телефона для детей
            if linked_to_parent_id and not phone_number:
                parent = await self.user_repo.get_user_by_id(created_by_id)
                if parent and parent.phone_number:
                    phone_number = f"{parent.phone_number}:{token}:child"
                    self.logger.debug(f"Сгенерирован виртуальный телефон для ребенка: {phone_number}")

            # Вызываем основной метод создания
            user = await self.create_user_with_token(
                telegram_id=None,
                full_name=full_name,
                role=UserRole.client,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                weight=weight,
                address=address,
                is_virtual=True,
                verification_token=token,
                registration_type=registration_type,
                created_by_id=created_by_id,
                linked_to_parent_id=linked_to_parent_id
            )

            self._log_operation_end("create_virtual_user",
                                   success=True,
                                   user_id=user.id,
                                   token=token)

            return user, token

        except Exception as e:
            self._log_operation_end("create_virtual_user", success=False)
            self.logger.error(f"Ошибка создания виртуального пользователя '{full_name}': {e}", exc_info=True)
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
            existing_user = await self.user_repo.get_user_by_phone(phone_number)
            if existing_user:
                error_msg = f"Номер телефона {phone_number} уже зарегистрирован"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Создаем виртуального пользователя
            user, token = await self.create_virtual_user(
                full_name=full_name,
                created_by_id=admin_id,
                registration_type=RegistrationType.ADMIN,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                weight=weight
            )

            # Дополнительная логика: обновление адреса
            if address:
                await self.user_repo.update_user_data(user.id, address=address)
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
        child_name: str,
        parent_telegram_id: int,
        date_of_birth: date = None,
        weight: int = None,
        address: str = None
    ) -> Tuple[User, str]:
        """Родитель создает ребенка"""
        self._log_operation_start("create_child_user",
                                 child_name=child_name,
                                 parent_tg_id=parent_telegram_id)

        try:
            # Бизнес-логика: поиск родителя
            parent = await self.user_repo.get_user_by_telegram_id(parent_telegram_id)
            if not parent:
                error_msg = f"Родитель с ID {parent_telegram_id} не найден"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            parent_id = parent.id
            self.logger.debug(f"Родитель найден: ID={parent_id}, имя='{parent.full_name}'")

            # Бизнес-логика: проверка лимита детей (7)
            children = await self.user_repo.get_children_users(parent_id)
            if len(children) >= 7:
                error_msg = "Достигнут лимит добавления детей (максимум 7)"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            self.logger.debug(f"У родителя {parent_id} сейчас {len(children)} детей (лимит: 7)")

            # Создаем ребенка
            user, token = await self.create_virtual_user(
                full_name=child_name,
                created_by_id=parent_id,
                registration_type=RegistrationType.PARENT,
                date_of_birth=date_of_birth,
                weight=weight,
                address=address,
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
            self.logger.error(f"Ошибка создания ребенка '{child_name}': {e}", exc_info=True)
            raise

    async def link_telegram_to_user(self, token: str, telegram_id: int) -> Optional[User]:
        """Привязать Telegram ID к пользователю по токену"""
        self._log_operation_start("link_telegram_to_user",
                                 token=token[:8] + "...",
                                 telegram_id=telegram_id)

        try:
            # Бизнес-логика: проверка занятости Telegram ID
            existing_user = await self.user_repo.get_user_by_telegram_id(telegram_id)
            if existing_user:
                error_msg = f"Telegram ID {telegram_id} уже используется пользователем {existing_user.id}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Получаем пользователя по токену
            user = await self.user_repo.get_user_by_token(token)
            if not user:
                self.logger.warning(f"Пользователь с токеном {token[:8]}... не найден")
                return None

            # Бизнес-логика: проверка, что Telegram еще не привязан
            if user.telegram_id:
                error_msg = f"Пользователь уже привязан к Telegram ID {user.telegram_id}"
                self.logger.warning(error_msg)
                raise ValueError(error_msg)

            # Обновляем пользователя через репозиторий
            updated = await self.user_repo.update_user_data(
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
            updated_user = await self.user_repo.get_user_by_id(user.id)

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
            user = await self.user_repo.get_user_by_id(user_id)
            if user and user.verification_token:
                self._log_operation_end("get_user_token", success=True, has_token=True)
                return user.verification_token

            self._log_operation_end("get_user_token", success=True, has_token=False)
            return None
        except Exception as e:
            self._log_operation_end("get_user_token", success=False)
            self.logger.error(f"Ошибка получения токена пользователя {user_id}: {e}", exc_info=True)
            return None
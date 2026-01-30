import secrets
from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy import select, update, and_, or_, func, case, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.utils.logging_config import get_logger
from app.database.models import (
    User, UserRole, Excursion, ExcursionSlot, SlotStatus,
    Booking, BookingStatus, ClientStatus, PaymentStatus,
    Payment, PromoCode, Salary, Expense, Notification, NotificationType,
    PaymentMethod, YooKassaStatus, RegistrationType
)


logger = get_logger(__name__)


class DatabaseManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        logger.debug(f"Инициализирован DatabaseManager с сессией ID: {id(session)}")

    # ===== USER OPERATIONS =====
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        try:
            logger.debug(f"Поиск пользователя по ID: {user_id}")
            result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Пользователь найден: ID={user.id}, имя='{user.full_name}'")
            else:
                logger.warning(f"Пользователь с ID {user_id} не найден")

            return user
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя по ID {user_id}: {e}", exc_info=True)
            return None

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        try:
            logger.debug(f"Поиск пользователя по Telegram ID: {telegram_id}")
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Пользователь найден по Telegram ID: {user.id}")
            else:
                logger.debug(f"Пользователь с Telegram ID {telegram_id} не найден")

            return user
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя по Telegram ID {telegram_id}: {e}", exc_info=True)
            return None

    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Получить пользователя по номеру телефона"""
        try:
            original_phone = phone_number
            logger.debug(f"Поиск пользователя по телефону: {original_phone}")

            # Нормализация номера
            if phone_number.startswith('8') and len(phone_number) == 11:
                phone_number = '+7' + phone_number[1:]
            elif phone_number.startswith('7') and len(phone_number) == 11:
                phone_number = '+' + phone_number

            logger.debug(f"Нормализованный номер: {phone_number}")

            result = await self.session.execute(
                select(User).where(User.phone_number == phone_number)
            )
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Пользователь найден по телефону: {user.id}")
            else:
                logger.debug(f"Пользователь с телефоном {original_phone} не найден")

            return user
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя по телефону {phone_number}: {e}", exc_info=True)
            return None

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        role: UserRole,
        phone_number: str = None,
        date_of_birth: date = None,
        address: str = None,
        weight: int = None,
        consent_to_pd: bool = False,
        # Новые параметры для виртуальных пользователей:
        registration_type: RegistrationType = RegistrationType.SELF,
        created_by_id: int = None,
        linked_to_parent_id: int = None,
        is_virtual: bool = None,
        verification_token: str = None
    ) -> User:
        """Создать нового пользователя (токенная версия)"""
        logger.info(
            f"Создание пользователя: name='{full_name}', "
            f"telegram_id={telegram_id}, role={role.value}, "
            f"registration_type={registration_type.value}"
        )

        try:
            # Автоматически определяем is_virtual если не указано
            if is_virtual is None:
                is_virtual = telegram_id is None

            # Если нет telegram_id и не передан токен - генерируем
            if is_virtual and not verification_token:
                verification_token = secrets.token_urlsafe(32)
                logger.debug(f"Сгенерирован токен для виртуального пользователя")

            user = User(
                telegram_id=telegram_id,
                full_name=full_name,
                role=role,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                address=address,
                weight=weight,
                consent_to_pd=consent_to_pd,
                # Новые поля:
                is_virtual=is_virtual,
                verification_token=verification_token,
                registration_type=registration_type,
                created_by_id=created_by_id,
                linked_to_parent_id=linked_to_parent_id,
                token_created_at=datetime.now() if verification_token else None
            )

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Пользователь успешно создан: ID={user.id}, is_virtual={user.is_virtual}")

            if verification_token:
                logger.debug(f"Токен пользователя {user.id}: {verification_token}")

            return user

        except Exception as e:
            logger.error(f"Ошибка создания пользователя '{full_name}': {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def update_user_data(self, id: int, **update_data) -> bool:
        """Обновить данные пользователя"""
        logger.info(f"Обновление данных пользователя id={id}")
        logger.debug(f"Данные для обновления: {update_data}")

        try:
            # Удаляем None значения чтобы не перезаписывать на None
            clean_data = {k: v for k, v in update_data.items() if v is not None}

            if not clean_data:
                logger.warning("Нет данных для обновления (все значения None)")
                return False

            result = await self.session.execute(
                update(User)
                .where(User.id == id)
                .values(**clean_data)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Данные пользователя {id} успешно обновлены")
                logger.debug(f"Обновленные поля: {list(clean_data.keys())}")
            else:
                logger.warning(f"Пользователь с id={id} не найден для обновления")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя {id}: {e}", exc_info=True)
            await self.session.rollback()
            return False

    async def update_user_consent(self, telegram_id: int, consent: bool) -> bool:
        """Обновить согласие на обработку персональных данных"""
        logger.info(f"Обновление согласия на ПД для пользователя {telegram_id}: {consent}")

        try:
            result = await self.session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(consent_to_pd=consent)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Согласие на ПД пользователя {telegram_id} обновлено на {consent}")
            else:
                logger.warning(f"Пользователь с telegram_id={telegram_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления согласия на ПД: {e}")
            await self.session.rollback()
            return False

    async def promote_to_admin(self, user: User) -> bool:
        logger.info(f"Повышение пользователя {user.id} до администратора")

        try:
            result = await self.session.execute(
                update(User)
                .where(User.telegram_id == user.telegram_id)
                .values(role=UserRole.admin)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Пользователь {user.id} успешно повышен до администратора")
            else:
                logger.warning(f"Не удалось повысить пользователя {user.id}")

            return success
        except Exception as e:
            logger.error(f"Ошибка повышения до администратора: {e}")
            await self.session.rollback()
            return False

    async def promote_to_captain(self, user: User) -> bool:
        logger.info(f"Повышение пользователя {user.id} до капитана")

        try:
            result = await self.session.execute(
                update(User)
                .where(User.telegram_id == user.telegram_id)
                .values(role=UserRole.captain)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Пользователь {user.id} успешно повышен до капитана")
            else:
                logger.warning(f"Не удалось повысить пользователя {user.id}")

            return success
        except Exception as e:
            logger.error(f"Ошибка повышения до капитана: {e}")
            await self.session.rollback()
            return False

    async def promote_to_client(self, user: User) -> bool:
        logger.info(f"Понижение пользователя {user.id} до клиента")

        try:
            result = await self.session.execute(
                update(User)
                .where(User.telegram_id == user.telegram_id)
                .values(role=UserRole.client)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Пользователь {user.id} понижен до клиента")
            else:
                logger.warning(f"Не удалось понизить пользователя {user.id}")

            return success
        except Exception as e:
            logger.error(f"Ошибка понижения до клиента: {e}")
            await self.session.rollback()
            return False

    async def check_user_exists(self, telegram_id: int) -> bool:
        """Проверить, существует ли пользователь с таким Telegram ID"""
        try:
            logger.debug(f"Проверка существования пользователя telegram_id={telegram_id}")
            result = await self.session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(f"Пользователь telegram_id={telegram_id} существует: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Ошибка проверки существования пользователя {telegram_id}: {e}", exc_info=True)
            return False

    async def check_phone_exists(self, phone_number: str) -> bool:
        """Проверить, существует ли пользователь с таким номером телефона"""
        try:
            logger.debug(f"Проверка существования телефона: {phone_number}")
            result = await self.session.execute(
                select(User).where(User.phone_number == phone_number)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(f"Телефон {phone_number} существует в базе: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Ошибка проверки существования телефона {phone_number}: {e}", exc_info=True)
            return False

    async def get_users_created_by(self, creator_id: int) -> list[User]:
        """Получить всех пользователей, созданных указанным пользователем"""
        logger.debug(f"Получение пользователей, созданных пользователем ID={creator_id}")

        try:
            result = await self.session.execute(
                select(User).where(User.created_by_id == creator_id)
            )
            users = result.scalars().all()

            logger.debug(f"Найдено пользователей, созданных пользователем {creator_id}: {len(users)}")
            return users
        except Exception as e:
            logger.error(f"Ошибка получения пользователей создателя {creator_id}: {e}", exc_info=True)
            return []

    async def user_has_children(self, user_id: int) -> bool:
        """Проверить есть ли у пользователя дети (оптимизированный запрос)"""
        try:
            from app.database.models import User
            result = await self.session.execute(
                select(User.id)
                .where(User.linked_to_parent_id == user_id)
                .limit(1)
            )
            has_child = result.first() is not None
            logger.debug(f"Пользователь {user_id} имеет детей: {has_child}")
            return has_child
        except Exception as e:
            logger.error(f"Ошибка проверки детей: {e}")
            return False

    async def get_children_users(self, parent_id: int) -> list[User]:
        """Получить всех детей пользователя"""
        logger.debug(f"Получение детей пользователя ID={parent_id}")

        try:
            result = await self.session.execute(
                select(User).where(User.linked_to_parent_id == parent_id)
            )
            children = result.scalars().all()

            logger.debug(f"Найдено детей у пользователя {parent_id}: {len(children)}")
            return children
        except Exception as e:
            logger.error(f"Ошибка получения детей пользователя {parent_id}: {e}", exc_info=True)
            return []

    async def get_all_captains(self) -> List[User]:
        """Получить всех капитанов"""
        logger.debug("Получение списка капитанов")

        try:
            result = await self.session.execute(
                select(User).where(User.role == UserRole.captain)
            )
            captains = result.scalars().all()

            logger.debug(f"Найдено капитанов: {len(captains)}")
            return captains
        except Exception as e:
            logger.error(f"Ошибка получения капитанов: {e}", exc_info=True)
            return []

    async def get_available_captains(self, start_datetime: datetime, end_datetime: datetime) -> List[User]:
        """Получить капитанов, свободных в указанный период времени"""
        try:
            # Запрос для получения капитанов, у которых нет слотов в это время
            query = (
                select(User)
                .where(User.role == UserRole.captain)
                .where(
                    ~exists().where(
                        and_(
                            ExcursionSlot.captain_id == User.id,
                            ExcursionSlot.status.in_([SlotStatus.scheduled, SlotStatus.in_progress]),
                            ExcursionSlot.start_datetime < end_datetime,
                            ExcursionSlot.end_datetime > start_datetime
                        )
                    )
                )
                .order_by(User.full_name)
            )

            result = await self.session.execute(query)
            captains = result.scalars().all()

            logger.debug(f"Найдено {len(captains)} свободных капитанов на период {start_datetime} - {end_datetime}")
            return captains

        except Exception as e:
            logger.error(f"Ошибка при получении доступных капитанов: {e}")
            return []

    async def check_captain_availability(
        self,
        captain_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_slot_id: int = None
    ) -> bool:
        """Проверить, занят ли капитан в указанное время

        Returns:
            bool: True если капитан занят, False если свободен
        """
        try:
            query = select(ExcursionSlot).where(
                and_(
                    ExcursionSlot.captain_id == captain_id,
                    ExcursionSlot.status.in_([SlotStatus.scheduled, SlotStatus.in_progress]),
                    ExcursionSlot.start_datetime < end_datetime,
                    ExcursionSlot.end_datetime > start_datetime
                )
            )

            if exclude_slot_id:
                query = query.where(ExcursionSlot.id != exclude_slot_id)

            result = await self.session.execute(query)
            conflicting_slots = result.scalars().all()

            return len(conflicting_slots) > 0

        except Exception as e:
            logger.error(f"Ошибка проверки доступности капитана: {e}")
            return True  # В случае ошибки считаем, что капитан занят

    # ===== EXCURSION OPERATIONS =====
    async def get_all_excursions(self, active_only: bool = True) -> List[Excursion]:
        """Получить все экскурсии"""
        logger.debug(f"Получение всех экскурсий, active_only={active_only}")

        try:
            query = select(Excursion)
            if active_only:
                query = query.where(Excursion.is_active == True)

            result = await self.session.execute(query)
            excursions = result.scalars().all()

            logger.debug(f"Найдено экскурсий: {len(excursions)}")
            return excursions
        except Exception as e:
            logger.error(f"Ошибка получения экскурсий: {e}", exc_info=True)
            return []

    async def get_excursion_by_id(self, excursion_id: int) -> Optional[Excursion]:
        """Получить экскурсию по ID"""
        logger.debug(f"Получение экскурсии по ID: {excursion_id}")

        try:
            result = await self.session.execute(
                select(Excursion).where(Excursion.id == excursion_id)
            )
            excursion = result.scalar_one_or_none()

            if excursion:
                logger.debug(f"Экскурсия найдена: {excursion.name}")
            else:
                logger.warning(f"Экскурсия с ID {excursion_id} не найдена")

            return excursion
        except Exception as e:
            logger.error(f"Ошибка получения экскурсии {excursion_id}: {e}", exc_info=True)
            return None

    async def get_excursion_by_name(self, name: str) -> Optional[Excursion]:
        """Получить экскурсию по точному названию"""
        logger.debug(f"Поиск экскурсии по имени: '{name}'")

        try:
            result = await self.session.execute(
                select(Excursion).where(Excursion.name == name)
            )
            excursion = result.scalar_one_or_none()

            if excursion:
                logger.debug(f"Экскурсия найдена: ID={excursion.id}")
            else:
                logger.debug(f"Экскурсия с именем '{name}' не найдена")

            return excursion
        except Exception as e:
            logger.error(f"Ошибка поиска экскурсии по имени '{name}': {e}", exc_info=True)
            return None

    async def create_excursion(self, name: str, base_duration_minutes: int, base_price: int,
                          description: str = None, child_discount: int = 0,
                          is_active: bool = True) -> Excursion:
        """Создать новую экскурсию"""
        logger.info(f"Создание новой экскурсии: '{name}'")
        logger.debug(f"Параметры: duration={base_duration_minutes}мин, price={base_price}руб")

        try:
            excursion = Excursion(
                name=name,
                description=description,
                base_duration_minutes=base_duration_minutes,
                base_price=base_price,
                child_discount=child_discount,
                is_active=is_active
            )
            self.session.add(excursion)
            await self.session.commit()
            await self.session.refresh(excursion)

            logger.info(f"Экскурсия создана: ID={excursion.id}, '{excursion.name}'")
            return excursion

        except Exception as e:
            logger.error(f"Ошибка создания экскурсии '{name}': {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def update_excursion_data(self, exc_id: int, **update_data) -> bool:
        """Обновить данные экскурсии"""
        logger.info(f"Обновление экскурсии ID={exc_id}")
        logger.debug(f"Данные для обновления: {update_data}")

        try:
            # Удаляем None значения чтобы не перезаписывать на None
            clean_data = {k: v for k, v in update_data.items() if v is not None}
            if not clean_data:
                logger.warning("Нет данных для обновления экскурсии (все значения None)")
                return False

            result = await self.session.execute(
                update(Excursion)
                .where(Excursion.id == exc_id)
                .values(**clean_data)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Экскурсия {exc_id} успешно обновлена")
                logger.debug(f"Обновленные поля: {list(clean_data.keys())}")
            else:
                logger.warning(f"Экскурсия с ID {exc_id} не найдена")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления экскурсии {exc_id}: {e}", exc_info=True)
            await self.session.rollback()
            return False

    async def get_excursion_schedule(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        excursion_id: Optional[int] = None,
        include_cancelled: bool = False
    ) -> List[ExcursionSlot]:
        """Получить расписание экскурсий"""
        logger.debug(
            f"Получение расписания: from={date_from}, to={date_to}, "
            f"exc_id={excursion_id}, include_cancelled={include_cancelled}"
        )

        try:
            query = select(ExcursionSlot).join(Excursion)

            # Фильтры по дате
            if date_from:
                query = query.where(ExcursionSlot.start_datetime >= date_from)
            if date_to:
                query = query.where(ExcursionSlot.start_datetime <= date_to)

            # Фильтр по экскурсии
            if excursion_id:
                query = query.where(ExcursionSlot.excursion_id == excursion_id)

            # Фильтр по статусу
            if not include_cancelled:
                query = query.where(ExcursionSlot.status != SlotStatus.cancelled)

            query = query.order_by(ExcursionSlot.start_datetime)
            result = await self.session.execute(query)
            slots = result.scalars().all()

            logger.debug(f"Найдено слотов в расписании: {len(slots)}")
            return slots
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}", exc_info=True)
            return []

    # ===== SLOT OPERATIONS =====
    async def get_slot_by_id(self, slot_id: int) -> Optional[ExcursionSlot]:
        """Получить слот по ID"""
        try:
            result = await self.session.execute(
                select(ExcursionSlot).where(ExcursionSlot.id == slot_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка получения слота {slot_id}: {e}")
            return None

    async def get_available_slots(self, excursion_id: int, date_from: datetime,
                                date_to: datetime) -> List[ExcursionSlot]:
        """Получить доступные слоты для экскурсии в указанный период"""
        logger.debug(
            f"Поиск доступных слотов: excursion_id={excursion_id}, "
            f"период с {date_from} по {date_to}"
        )

        try:
            result = await self.session.execute(
                select(ExcursionSlot)
                .options(selectinload(ExcursionSlot.excursion))
                .options(selectinload(ExcursionSlot.captain))
                .where(
                    and_(
                        ExcursionSlot.excursion_id == excursion_id,
                        ExcursionSlot.start_datetime >= date_from,
                        ExcursionSlot.end_datetime <= date_to,
                        ExcursionSlot.status == SlotStatus.scheduled
                    )
                )
                .order_by(ExcursionSlot.start_datetime)
            )
            slots = result.scalars().all()

            logger.debug(f"Найдено доступных слотов: {len(slots)}")
            return slots
        except Exception as e:
            logger.error(f"Ошибка поиска доступных слотов: {e}", exc_info=True)
            return []

    async def get_slot_with_bookings(self, slot_id: int) -> Optional[ExcursionSlot]:
        """Получить слот с информацией о бронированиях"""
        logger.debug(f"Получение слота {slot_id} с бронированиями")

        try:
            result = await self.session.execute(
                select(ExcursionSlot)
                .options(
                    selectinload(ExcursionSlot.excursion),
                    selectinload(ExcursionSlot.captain),
                    selectinload(ExcursionSlot.bookings).selectinload(Booking.client)
                )
                .where(ExcursionSlot.id == slot_id)
            )
            slot = result.scalar_one_or_none()

            if slot:
                logger.debug(f"Слот найден: {slot.excursion.name}, {slot.start_datetime}")
                logger.debug(f"Количество бронирований в слоте: {len(slot.bookings)}")
            else:
                logger.warning(f"Слот с ID {slot_id} не найден")

            return slot
        except Exception as e:
            logger.error(f"Ошибка получения слота {slot_id}: {e}", exc_info=True)
            return None

    async def get_captain_slots(self, captain_telegram_id: int,
                              start_date: datetime, end_date: datetime) -> List[ExcursionSlot]:
        """Получить слоты капитана за период"""
        logger.debug(
            f"Получение слотов капитана TG_ID={captain_telegram_id}, "
            f"период с {start_date} по {end_date}"
        )

        try:
            result = await self.session.execute(
                select(ExcursionSlot)
                .options(
                    selectinload(ExcursionSlot.excursion),
                    selectinload(ExcursionSlot.bookings).selectinload(Booking.client)
                )
                .join(User, ExcursionSlot.captain_id == User.id)
                .where(
                    and_(
                        User.telegram_id == captain_telegram_id,
                        ExcursionSlot.start_datetime >= start_date,
                        ExcursionSlot.end_datetime <= end_date
                    )
                )
                .order_by(ExcursionSlot.start_datetime)
            )
            slots = result.scalars().all()

            logger.debug(f"Найдено слотов капитана: {len(slots)}")
            return slots
        except Exception as e:
            logger.error(f"Ошибка получения слотов капитана: {e}", exc_info=True)
            return []

    async def get_available_slots_for_period(
        self,
        date_from: datetime,
        date_to: datetime
    ) -> List[ExcursionSlot]:
        """Получить все доступные слоты за период"""
        logger.debug(f"Поиск доступных слотов за период: {date_from} - {date_to}")

        try:
            result = await self.session.execute(
                select(ExcursionSlot)
                .options(selectinload(ExcursionSlot.excursion))
                .where(
                    and_(
                        ExcursionSlot.start_datetime >= date_from,
                        ExcursionSlot.start_datetime <= date_to,
                        ExcursionSlot.status == SlotStatus.scheduled
                    )
                )
                .order_by(ExcursionSlot.start_datetime)
            )
            slots = result.scalars().all()

            logger.debug(f"Найдено доступных слотов: {len(slots)}")
            return slots
        except Exception as e:
            logger.error(f"Ошибка поиска доступных слотов: {e}", exc_info=True)
            return []

    async def create_excursion_slot(
            self,
            excursion_id: int,
            start_datetime: datetime,
            max_people: int,
            max_weight: int,
            captain_id: Optional[int] = None,
            status: SlotStatus = SlotStatus.scheduled
        ) -> Optional[ExcursionSlot]:
        """Создать новый слот в расписании"""
        logger.info(f"Создание слота с весом {max_weight}кг для {max_people} чел.")

        try:
            excursion = await self.get_excursion_by_id(excursion_id)
            if not excursion:
                return None

            end_datetime = start_datetime + timedelta(minutes=excursion.base_duration_minutes)

            # Проверяем конфликты
            conflicting_slot = await self.get_conflicting_slot(excursion_id, start_datetime, end_datetime)
            if conflicting_slot:
                return None

            slot = ExcursionSlot(
                excursion_id=excursion_id,
                captain_id=captain_id,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                max_people=max_people,
                max_weight=max_weight,
                status=status
            )

            self.session.add(slot)
            await self.session.commit()
            await self.session.refresh(slot)
            return slot

        except Exception as e:
            logger.error(f"Ошибка создания слота: {e}")
            await self.session.rollback()
            return None

    async def get_conflicting_slot(
        self,
        excursion_id: int,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> Optional[ExcursionSlot]:
        """Проверить наличие конфликтующего слота"""
        logger.debug(
            f"Проверка конфликтов: exc_id={excursion_id}, "
            f"{start_datetime} - {end_datetime}"
        )

        try:
            result = await self.session.execute(
                select(ExcursionSlot)
                .where(
                    and_(
                        ExcursionSlot.excursion_id == excursion_id,
                        ExcursionSlot.status != SlotStatus.cancelled,
                        or_(
                            and_(
                                ExcursionSlot.start_datetime <= start_datetime,
                                ExcursionSlot.end_datetime > start_datetime
                            ),
                            and_(
                                ExcursionSlot.start_datetime < end_datetime,
                                ExcursionSlot.end_datetime >= end_datetime
                            ),
                            and_(
                                ExcursionSlot.start_datetime >= start_datetime,
                                ExcursionSlot.end_datetime <= end_datetime
                            )
                        )
                    )
                )
            )
            slot = result.scalar_one_or_none()

            if slot:
                logger.debug(f"Найден конфликтующий слот: ID={slot.id}")
            else:
                logger.debug("Конфликтующих слотов не найдено")

            return slot
        except Exception as e:
            logger.error(f"Ошибка проверки конфликтов: {e}", exc_info=True)
            return None

    async def get_conflicting_slot_excluding(
        self,
        excursion_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_slot_id: int
    ) -> Optional[ExcursionSlot]:
        """Проверить конфликты, исключая указанный слот"""
        try:
            query = select(ExcursionSlot).where(
                and_(
                    ExcursionSlot.excursion_id == excursion_id,
                    ExcursionSlot.id != exclude_slot_id,  # ← исключаем этот слот
                    ExcursionSlot.status != SlotStatus.cancelled,
                    or_(
                        and_(
                            ExcursionSlot.start_datetime <= start_datetime,
                            ExcursionSlot.end_datetime > start_datetime
                        ),
                        and_(
                            ExcursionSlot.start_datetime < end_datetime,
                            ExcursionSlot.end_datetime >= end_datetime
                        ),
                        and_(
                            ExcursionSlot.start_datetime >= start_datetime,
                            ExcursionSlot.end_datetime <= end_datetime
                        )
                    )
                )
            )

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Ошибка проверки конфликтов (с исключением): {e}")
            return None

    async def update_slot_status(
        self,
        slot_id: int,
        status: SlotStatus
    ) -> bool:
        """Обновить статус слота"""
        logger.info(f"Обновление статуса слота {slot_id} на {status}")

        try:
            result = await self.session.execute(
                update(ExcursionSlot)
                .where(ExcursionSlot.id == slot_id)
                .values(status=status)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Статус слота {slot_id} обновлен на {status}")
            else:
                logger.warning(f"Слот с ID {slot_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления статуса слота {slot_id}: {e}", exc_info=True)
            await self.session.rollback()
            return False

    async def assign_captain_to_slot(self, slot_id: int, captain_id: int) -> bool:
        """Назначить капитана на слот"""
        logger.info(f"Назначение капитана {captain_id} на слот {slot_id}")

        try:
            result = await self.session.execute(
                update(ExcursionSlot)
                .where(ExcursionSlot.id == slot_id)
                .values(captain_id=captain_id)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Капитан {captain_id} назначен на слот {slot_id}")
            else:
                logger.warning(f"Слот {slot_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка назначения капитана: {e}", exc_info=True)
            await self.session.rollback()
            return False

    async def reschedule_slot(
        self,
        slot_id: int,
        new_start_datetime: datetime
    ) -> tuple[bool, str]:
        """Перенести слот на новое время

        Returns:
            tuple[bool, str]: (успех, сообщение об ошибке)
        """
        try:
            # Получаем текущий слот
            slot = await self.get_slot_by_id(slot_id)
            if not slot:
                return False, "Слот не найден"

            # Рассчитываем новое время окончания
            excursion = await self.get_excursion_by_id(slot.excursion_id)
            if not excursion:
                return False, "Экскурсия не найдена"

            new_end_datetime = new_start_datetime + timedelta(
                minutes=excursion.base_duration_minutes
            )

            # Проверяем конфликты (исключая сам этот слот)
            conflicting_slot = await self.get_conflicting_slot_excluding(
                slot.excursion_id,
                new_start_datetime,
                new_end_datetime,
                exclude_slot_id=slot_id
            )

            if conflicting_slot:
                logger.warning(f"Конфликт с слотом ID={conflicting_slot.id}")
                return False, f"Конфликт с слотом #{conflicting_slot.id}"

            # Проверяем доступность капитана, если он назначен
            if slot.captain_id:
                # Проверяем, свободен ли капитан в новое время
                captain_busy = await self.check_captain_availability(
                    slot.captain_id,
                    new_start_datetime,
                    new_end_datetime,
                    exclude_slot_id=slot_id
                )

                if captain_busy:
                    captain = await self.get_user_by_id(slot.captain_id)
                    captain_name = captain.full_name if captain else f"ID {slot.captain_id}"
                    return False, f"Капитан {captain_name} занят в это время"

            # Обновляем слот
            result = await self.session.execute(
                update(ExcursionSlot)
                .where(ExcursionSlot.id == slot_id)
                .values(
                    start_datetime=new_start_datetime,
                    end_datetime=new_end_datetime
                )
            )

            await self.session.commit()

            if result.rowcount > 0:
                return True, ""
            else:
                return False, "Не удалось обновить слот"

        except Exception as e:
            logger.error(f"Ошибка переноса слота: {e}")
            await self.session.rollback()
            return False, f"Ошибка: {str(e)}"

    async def get_booked_places_for_slot(self, slot_id: int) -> int:
        """Получить количество забронированных мест для слота"""
        stmt = select(func.coalesce(func.sum(Booking.people_count), 0)).where(
            (Booking.slot_id == slot_id) &
            (Booking.booking_status == BookingStatus.active)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_current_weight_for_slot(self, slot_id: int) -> int:
        """Получить текущий вес для слота"""
        # Получаем вес активных клиентов
        stmt = select(func.coalesce(func.sum(User.weight), 0)).select_from(Booking).join(
            User, Booking.client_id == User.id
        ).where(
            (Booking.slot_id == slot_id) &
            (Booking.booking_status == BookingStatus.active) &
            (User.weight.is_not(None))
        )
        client_weight = (await self.session.execute(stmt)).scalar() or 0

        # Получаем вес капитана
        slot_stmt = select(ExcursionSlot.captain_id).where(ExcursionSlot.id == slot_id)
        slot_result = await self.session.execute(slot_stmt)
        captain_id = slot_result.scalar_one_or_none()

        captain_weight = 0
        if captain_id:
            captain_stmt = select(User.weight).where(User.id == captain_id)
            captain_result = await self.session.execute(captain_stmt)
            captain_weight = captain_result.scalar_one_or_none() or 0

        return client_weight + captain_weight

    async def get_booking_calculated_price(self, booking_id: int) -> int:
        """Получить расчетную стоимость бронирования"""
        from sqlalchemy.orm import selectinload

        stmt = select(Booking).options(
            selectinload(Booking.slot).selectinload(ExcursionSlot.excursion)
        ).where(Booking.id == booking_id)

        result = await self.session.execute(stmt)
        booking = result.scalar_one_or_none()

        if not booking or not booking.slot or not booking.slot.excursion:
            return 0

        base_price = booking.slot.excursion.base_price
        child_price = booking.slot.excursion.child_price
        adults = booking.people_count - booking.children_count

        return (adults * base_price) + (booking.children_count * child_price)

    async def get_slot_full_info(self, slot_id: int) -> dict:
        """Получить полную информацию о слоте"""
        from sqlalchemy.orm import selectinload

        stmt = select(ExcursionSlot).options(
            selectinload(ExcursionSlot.excursion),
            selectinload(ExcursionSlot.captain),
            selectinload(ExcursionSlot.bookings).selectinload(Booking.client)
        ).where(ExcursionSlot.id == slot_id)

        result = await self.session.execute(stmt)
        slot = result.scalar_one_or_none()

        if not slot:
            return None

        # Рассчитываем показатели
        booked_places = sum(
            b.people_count for b in slot.bookings
            if b.booking_status == BookingStatus.active
        )

        current_weight = sum(
            b.client.weight for b in slot.bookings
            if b.client and b.client.weight and b.booking_status == BookingStatus.active
        )

        if slot.captain and slot.captain.weight:
            current_weight += slot.captain.weight

        return {
            'slot': slot,
            'available_places': max(0, slot.max_people - booked_places),
            'booked_places': booked_places,
            'current_weight': current_weight,
            'available_weight': max(0, slot.max_weight - current_weight),
            'is_available': (
                slot.status == SlotStatus.scheduled and
                slot.start_datetime > datetime.now()
            )
        }

    async def get_slots_for_date_with_excursion(self, target_date: date) -> List[ExcursionSlot]:
        """Получить слоты на дату с предзагруженной экскурсией"""
        from sqlalchemy.orm import selectinload

        logger.debug(f"Получение слотов на дату {target_date} с предзагрузкой excursion")

        date_from = datetime.combine(target_date, datetime.min.time())
        date_to = datetime.combine(target_date, datetime.max.time())

        try:
            stmt = select(ExcursionSlot).options(
                selectinload(ExcursionSlot.excursion)
            ).where(
                (ExcursionSlot.start_datetime >= date_from) &
                (ExcursionSlot.start_datetime <= date_to)
            ).order_by(ExcursionSlot.start_datetime)

            result = await self.session.execute(stmt)
            slots = result.scalars().all()

            # Логирование для отладки
            logger.debug(f"Найдено слотов: {len(slots)}")

            if slots:
                first_slot = slots[0]
                logger.debug(f"Первый слот ID: {first_slot.id}")
                logger.debug(f"Тип excursion: {type(first_slot.excursion)}")
                logger.debug(f"Excursion ID из слота: {first_slot.excursion_id}")

                if hasattr(first_slot.excursion, '__class__'):
                    logger.debug(f"Класс excursion: {first_slot.excursion.__class__.__name__}")
                    logger.debug(f"Есть ли name? {hasattr(first_slot.excursion, 'name')}")
                    if hasattr(first_slot.excursion, 'name'):
                        logger.debug(f"Название экскурсии: {first_slot.excursion.name}")
                    else:
                        logger.debug("У excursion нет атрибута 'name'")
                else:
                    logger.debug(f"Excursion значение: {first_slot.excursion}")

            return slots

        except Exception as e:
            logger.error(f"Ошибка получения слотов с предзагрузкой: {e}", exc_info=True)
            return []

    async def get_slots_for_period_with_excursion(self, date_from: datetime, date_to: datetime) -> List[ExcursionSlot]:
        """Получить слоты за период с предзагруженной экскурсией"""
        from sqlalchemy.orm import selectinload

        logger.debug(f"Получение слотов за период {date_from} - {date_to} с предзагрузкой excursion")

        try:
            stmt = select(ExcursionSlot).options(
                selectinload(ExcursionSlot.excursion)
            ).where(
                (ExcursionSlot.start_datetime >= date_from) &
                (ExcursionSlot.start_datetime <= date_to)
            ).order_by(ExcursionSlot.start_datetime)

            result = await self.session.execute(stmt)
            slots = result.scalars().all()

            # Логирование для отладки
            logger.debug(f"Найдено слотов: {len(slots)}")

            if slots:
                for i, slot in enumerate(slots[:3]):  # Проверяем первые 3
                    logger.debug(f"Слот #{i+1} ID: {slot.id}")
                    logger.debug(f"  Тип excursion: {type(slot.excursion)}")
                    logger.debug(f"  Excursion ID из слота: {slot.excursion_id}")

                    if isinstance(slot.excursion, int):
                        logger.debug(f"  WARNING: excursion это int: {slot.excursion}")
                    elif hasattr(slot.excursion, '__class__'):
                        logger.debug(f"  Класс excursion: {slot.excursion.__class__.__name__}")
                        if hasattr(slot.excursion, 'name'):
                            logger.debug(f"  Название экскурсии: {slot.excursion.name}")
                        else:
                            logger.debug("  У excursion нет атрибута 'name'")
                    else:
                        logger.debug(f"  Excursion значение: {slot.excursion}")

                    # Проверим также через dir
                    logger.debug(f"  Атрибуты slot: {[a for a in dir(slot) if not a.startswith('_')][:10]}")

            return slots

        except Exception as e:
            logger.error(f"Ошибка получения слотов с предзагрузкой: {e}", exc_info=True)
            return []

    # ===== BOOKING OPERATIONS =====
    async def create_booking(self, slot_id: int, client_id: int, people_count: int,
                           children_count: int, total_price: int,
                           admin_creator_id: int = None, promo_code_id: int = None) -> Booking:
        """Создать бронирование"""
        logger.info(
            f"Создание бронирования: slot_id={slot_id}, client_id={client_id}, "
            f"людей={people_count}, детей={children_count}, цена={total_price}"
        )

        try:
            booking = Booking(
                slot_id=slot_id,
                client_id=client_id,
                admin_creator_id=admin_creator_id,
                people_count=people_count,
                children_count=children_count,
                total_price=total_price,
                promo_code_id=promo_code_id
            )
            self.session.add(booking)
            await self.session.commit()

            logger.info(f"Бронирование создано: ID={booking.id}")
            return booking

        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_user_bookings(self, user_telegram_id: int) -> List[Booking]:
        """Получить бронирования пользователя"""
        logger.debug(f"Получение бронирований пользователя TG_ID={user_telegram_id}")

        try:
            result = await self.session.execute(
                select(Booking)
                .options(
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.captain)
                )
                .join(User, Booking.client_id == User.id)
                .where(User.telegram_id == user_telegram_id)
                .order_by(Booking.created_at.desc())
            )
            bookings = result.scalars().all()

            logger.debug(f"Найдено бронирований пользователя: {len(bookings)}")
            return bookings
        except Exception as e:
            logger.error(f"Ошибка получения бронирований пользователя: {e}", exc_info=True)
            return []

    async def cancel_booking(self, booking_id: int, cancelled_by_admin: bool = False) -> bool:
        """Отменить бронирование"""
        logger.info(
            f"Отмена бронирования ID={booking_id}, "
            f"отменено администратором: {cancelled_by_admin}"
        )

        try:
            result = await self.session.execute(
                update(Booking)
                .where(Booking.id == booking_id)
                .values(booking_status=BookingStatus.cancelled)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Бронирование {booking_id} отменено")
            else:
                logger.warning(f"Бронирование с ID {booking_id} не найдено")

            return success
        except Exception as e:
            logger.error(f"Ошибка отмены бронирования {booking_id}: {e}")
            await self.session.rollback()
            return False

    async def update_booking_status(self, booking_id: int,
                                  client_status: ClientStatus = None,
                                  payment_status: PaymentStatus = None) -> bool:
        """Обновить статусы бронирования"""
        logger.info(f"Обновление статусов бронирования ID={booking_id}")
        logger.debug(f"client_status={client_status}, payment_status={payment_status}")

        try:
            update_data = {}
            if client_status:
                update_data['client_status'] = client_status
            if payment_status:
                update_data['payment_status'] = payment_status

            result = await self.session.execute(
                update(Booking)
                .where(Booking.id == booking_id)
                .values(**update_data)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Статусы бронирования {booking_id} обновлены")
            else:
                logger.warning(f"Бронирование с ID {booking_id} не найдено")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления статусов бронирования {booking_id}: {e}")
            await self.session.rollback()
            return False

    async def get_booking_by_id(self, booking_id: int) -> Optional[Booking]:
        """Получить бронирование по ID"""
        logger.debug(f"Получение бронирования по ID: {booking_id}")

        try:
            result = await self.session.execute(
                select(Booking)
                .options(
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.captain),
                    selectinload(Booking.client),
                    selectinload(Booking.payments)
                )
                .where(Booking.id == booking_id)
            )
            booking = result.scalar_one_or_none()

            if booking:
                logger.debug(f"Бронирование найдено: клиент={booking.client.full_name}")
            else:
                logger.warning(f"Бронирование с ID {booking_id} не найдено")

            return booking
        except Exception as e:
            logger.error(f"Ошибка получения бронирования {booking_id}: {e}", exc_info=True)
            return None

    # ===== PAYMENT OPERATIONS =====
    async def create_payment(self, booking_id: int, amount: int,
                           payment_method: PaymentMethod,
                           yookassa_payment_id: str = None) -> Payment:
        """Создать запись о платеже"""
        logger.info(
            f"Создание платежа: booking_id={booking_id}, "
            f"сумма={amount}, метод={payment_method.value}"
        )

        try:
            payment = Payment(
                booking_id=booking_id,
                amount=amount,
                payment_method=payment_method,
                yookassa_payment_id=yookassa_payment_id,
                status=YooKassaStatus.pending if payment_method == PaymentMethod.online else None
            )
            self.session.add(payment)
            await self.session.commit()

            logger.info(f"Платеж создан: ID={payment.id}")
            return payment

        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def update_payment_status(self, yookassa_payment_id: str,
                                  status: YooKassaStatus) -> bool:
        """Обновить статус онлайн платежа"""
        logger.info(f"Обновление статуса платежа YooKassa: {yookassa_payment_id} -> {status.value}")

        try:
            result = await self.session.execute(
                update(Payment)
                .where(Payment.yookassa_payment_id == yookassa_payment_id)
                .values(status=status)
            )

            success = result.rowcount > 0
            if success:
                logger.info(f"Статус платежа YooKassa {yookassa_payment_id} обновлен на {status.value}")

                if status == YooKassaStatus.succeeded:
                    # Обновляем статус оплаты в бронировании
                    payment_result = await self.session.execute(
                        select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id)
                    )
                    payment = payment_result.scalar_one()

                    await self.session.execute(
                        update(Booking)
                        .where(Booking.id == payment.booking_id)
                        .values(payment_status=PaymentStatus.paid)
                    )

                    logger.info(f"Статус бронирования {payment.booking_id} обновлен на 'оплачено'")

                await self.session.commit()
            else:
                logger.warning(f"Платеж YooKassa с ID {yookassa_payment_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа {yookassa_payment_id}: {e}", exc_info=True)
            await self.session.rollback()
            return False

    # ===== PROMOCODE OPERATIONS =====
    async def get_promocode(self, code: str) -> Optional[PromoCode]:
        """Получить промокод по коду"""
        logger.debug(f"Поиск промокода: '{code}'")

        try:
            result = await self.session.execute(
                select(PromoCode)
                .where(
                    and_(
                        PromoCode.code == code,
                        PromoCode.valid_from <= datetime.now(),
                        PromoCode.valid_until >= datetime.now(),
                        PromoCode.used_count < PromoCode.usage_limit
                    )
                )
            )
            promo = result.scalar_one_or_none()

            if promo:
                logger.debug(f"Промокод найден: {promo.code}, использований: {promo.used_count}/{promo.usage_limit}")
            else:
                logger.debug(f"Промокод '{code}' не найден или недействителен")

            return promo
        except Exception as e:
            logger.error(f"Ошибка поиска промокода '{code}': {e}", exc_info=True)
            return None

    async def apply_promocode(self, promo_code_id: int) -> bool:
        """Применить промокод (увеличить счетчик использований)"""
        logger.info(f"Применение промокода ID={promo_code_id}")

        try:
            result = await self.session.execute(
                update(PromoCode)
                .where(PromoCode.id == promo_code_id)
                .values(used_count=PromoCode.used_count + 1)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Промокод {promo_code_id} применен")
            else:
                logger.warning(f"Промокод с ID {promo_code_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка применения промокода {promo_code_id}: {e}")
            await self.session.rollback()
            return False

    async def get_all_promocodes(self, include_inactive: bool = False) -> List[PromoCode]:
        """Получить все промокоды"""
        logger.debug(f"Получение всех промокодов, include_inactive={include_inactive}")

        try:
            query = select(PromoCode).order_by(PromoCode.valid_until.desc())

            if not include_inactive:
                query = query.where(PromoCode.valid_until >= datetime.now())

            result = await self.session.execute(query)
            promocodes = result.scalars().all()

            logger.debug(f"Найдено промокодов: {len(promocodes)}")
            return promocodes
        except Exception as e:
            logger.error(f"Ошибка получения промокодов: {e}", exc_info=True)
            return []

    async def get_promocode_usage_count(self, promocode_id: int) -> int:
        """Получить количество использований промокода"""
        logger.debug(f"Получение количества использований промокода ID={promocode_id}")

        try:
            result = await self.session.execute(
                select(PromoCode.used_count)
                .where(PromoCode.id == promocode_id)
            )
            used_count = result.scalar_one_or_none()

            if used_count is not None:
                logger.debug(f"Промокод {promocode_id} использован {used_count} раз")
                return used_count
            return 0
        except Exception as e:
            logger.error(f"Ошибка получения количества использований промокода {promocode_id}: {e}", exc_info=True)
            return 0

    async def deactivate_promocode(self, promocode_id: int) -> bool:
        """Деактивировать промокод"""
        logger.info(f"Деактивация промокода ID={promocode_id}")

        try:
            result = await self.session.execute(
                update(PromoCode)
                .where(PromoCode.id == promocode_id)
                .values(valid_until=datetime.now())
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Промокод {promocode_id} деактивирован")
            else:
                logger.warning(f"Промокод с ID {promocode_id} не найден")

            return success
        except Exception as e:
            logger.error(f"Ошибка деактивации промокода {promocode_id}: {e}", exc_info=True)
            await self.session.rollback()
            return False

    # ===== STATISTICS OPERATIONS =====

    async def get_statistics(self, start_date: date, end_date: date) -> dict:
        """Получить статистику за период"""
        logger.info(f"Получение статистики за период: {start_date} - {end_date}")

        try:
            # Статистика по экскурсиям
            excursions_stats = await self.session.execute(
                select(
                    Excursion.id,
                    Excursion.name,
                    func.count(Booking.id).label('total_bookings'),
                    func.sum(Booking.people_count).label('total_people'),
                    func.sum(case((Booking.booking_status == BookingStatus.cancelled, 1), else_=0)).label('cancellations'),
                    func.sum(case((Booking.booking_status == BookingStatus.no_show, 1), else_=0)).label('no_shows'),
                    func.sum(Booking.total_price).label('total_revenue')
                )
                .select_from(Excursion)
                .join(ExcursionSlot, Excursion.id == ExcursionSlot.excursion_id)
                .join(Booking, ExcursionSlot.id == Booking.slot_id)
                .where(
                    and_(
                        ExcursionSlot.start_datetime >= start_date,
                        ExcursionSlot.start_datetime <= end_date
                    )
                )
                .group_by(Excursion.id, Excursion.name)
            )

            # Статистика по капитанам
            captains_stats = await self.session.execute(
                select(
                    User.id,
                    User.full_name,
                    func.count(ExcursionSlot.id).label('total_slots'),
                    func.count(Booking.id).label('total_bookings'),
                    func.sum(Booking.people_count).label('total_people')
                )
                .select_from(User)
                .join(ExcursionSlot, User.id == ExcursionSlot.captain_id)
                .join(Booking, ExcursionSlot.id == Booking.slot_id)
                .where(
                    and_(
                        User.role == UserRole.captain,
                        ExcursionSlot.start_datetime >= start_date,
                        ExcursionSlot.start_datetime <= end_date
                    )
                )
                .group_by(User.id, User.full_name)
            )

            stats = {
                'excursions': [dict(row) for row in excursions_stats],
                'captains': [dict(row) for row in captains_stats]
            }

            logger.info(f"Статистика получена: {len(stats['excursions'])} экскурсий, {len(stats['captains'])} капитанов")
            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
            return {'excursions': [], 'captains': []}

    # ===== NOTIFICATION OPERATIONS =====
    async def create_notification(self, user_id: int, notification_type: NotificationType,
                                message: str) -> Notification:
        """Создать уведомление"""
        logger.info(
            f"Создание уведомления: user_id={user_id}, "
            f"type={notification_type.value}, message='{message[:50]}...'"
        )

        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                message=message
            )
            self.session.add(notification)
            await self.session.commit()

            logger.info(f"Уведомление создано: ID={notification.id}")
            return notification

        except Exception as e:
            logger.error(f"Ошибка создания уведомления: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_undelivered_notifications(self) -> List[Notification]:
        """Получить недоставленные уведомления"""
        logger.debug("Получение недоставленных уведомлений")

        try:
            result = await self.session.execute(
                select(Notification)
                .options(selectinload(Notification.user))
                .where(Notification.is_delivered == False)
            )
            notifications = result.scalars().all()

            logger.debug(f"Найдено недоставленных уведомлений: {len(notifications)}")
            return notifications
        except Exception as e:
            logger.error(f"Ошибка получения недоставленных уведомлений: {e}", exc_info=True)
            return []

    async def mark_notification_delivered(self, notification_id: int) -> bool:
        """Пометить уведомление как доставленное"""
        logger.info(f"Пометка уведомления {notification_id} как доставленного")

        try:
            result = await self.session.execute(
                update(Notification)
                .where(Notification.id == notification_id)
                .values(is_delivered=True)
            )
            await self.session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"Уведомление {notification_id} помечено как доставленное")
            else:
                logger.warning(f"Уведомление с ID {notification_id} не найдено")

            return success
        except Exception as e:
            logger.error(f"Ошибка пометки уведомления {notification_id} как доставленного: {e}")
            await self.session.rollback()
            return False

    # ===== SALARY OPERATIONS =====
    async def calculate_captain_salary(self, captain_id: int, period: date) -> dict:
        """Рассчитать зарплату капитана за период"""
        logger.info(f"Расчет зарплаты капитана {captain_id} за период {period}")

        try:
            # Получаем все завершенные слоты капитана за период
            slots_result = await self.session.execute(
                select(ExcursionSlot)
                .options(selectinload(ExcursionSlot.bookings))
                .where(
                    and_(
                        ExcursionSlot.captain_id == captain_id,
                        ExcursionSlot.start_datetime >= period,
                        ExcursionSlot.start_datetime < period + timedelta(days=30),
                        ExcursionSlot.status == SlotStatus.completed
                    )
                )
            )

            slots = slots_result.scalars().all()

            total_bookings = 0
            total_people = 0
            total_revenue = 0

            for slot in slots:
                for booking in slot.bookings:
                    if booking.booking_status == BookingStatus.completed:
                        total_bookings += 1
                        total_people += booking.people_count
                        total_revenue += booking.total_price

            # Пример расчета зарплаты (нужно уточнить бизнес-логику)
            base_salary = total_bookings * 500  # Базовая ставка
            bonus = total_people * 100  # Бонус за количество людей
            total_amount = base_salary + bonus

            result = {
                'captain_id': captain_id,
                'period': period,
                'base_salary': base_salary,
                'bonus': bonus,
                'total_amount': total_amount,
                'total_bookings': total_bookings,
                'total_people': total_people,
                'total_revenue': total_revenue
            }

            logger.info(
                f"Зарплата капитана {captain_id} рассчитана: "
                f"база={base_salary}, бонус={bonus}, итого={total_amount}"
            )
            return result

        except Exception as e:
            logger.error(f"Ошибка расчета зарплаты капитана {captain_id}: {e}", exc_info=True)
            raise

    async def create_salary_record(self, user_id: int, period: date,
                                 base_salary: int, bonus: int, total_amount: int) -> Salary:
        """Создать запись о зарплате"""
        logger.info(
            f"Создание записи о зарплате: user_id={user_id}, период={period}, "
            f"база={base_salary}, бонус={bonus}, итого={total_amount}"
        )

        try:
            salary = Salary(
                user_id=user_id,
                period=period,
                base_salary=base_salary,
                bonus=bonus,
                total_amount=total_amount
            )
            self.session.add(salary)
            await self.session.commit()

            logger.info(f"Запись о зарплате создана: ID={salary.id}")
            return salary

        except Exception as e:
            logger.error(f"Ошибка создания записи о зарплате: {e}", exc_info=True)
            await self.session.rollback()
            raise

    # ===== EXPENSE OPERATIONS =====
    async def create_expense(self, category: str, amount: int, description: str,
                           expense_date: date, created_by_id: int) -> Expense:
        """Создать запись о расходе"""
        logger.info(
            f"Создание записи о расходе: категория='{category}', "
            f"сумма={amount}, дата={expense_date}"
        )

        try:
            expense = Expense(
                category=category,
                amount=amount,
                description=description,
                expense_date=expense_date,
                created_by_id=created_by_id
            )
            self.session.add(expense)
            await self.session.commit()

            logger.info(f"Запись о расходе создана: ID={expense.id}")
            return expense

        except Exception as e:
            logger.error(f"Ошибка создания записи о расходе: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def get_expenses(self, start_date: date, end_date: date) -> List[Expense]:
        """Получить расходы за период"""
        logger.debug(f"Получение расходов за период: {start_date} - {end_date}")

        try:
            result = await self.session.execute(
                select(Expense)
                .options(selectinload(Expense.created_by))
                .where(
                    and_(
                        Expense.expense_date >= start_date,
                        Expense.expense_date <= end_date
                    )
                )
                .order_by(Expense.expense_date.desc())
            )
            expenses = result.scalars().all()

            logger.debug(f"Найдено расходов: {len(expenses)}")
            return expenses
        except Exception as e:
            logger.error(f"Ошибка получения расходов: {e}", exc_info=True)
            return []

    # ===== UTILITY METHODS =====
    async def get_upcoming_bookings_for_reminder(self, hours_before: int = 24) -> List[Booking]:
        """Получить бронирования для отправки напоминаний"""
        logger.debug(f"Поиск бронирований для напоминаний (за {hours_before} часов)")

        try:
            reminder_time = datetime.now() + timedelta(hours=hours_before)

            result = await self.session.execute(
                select(Booking)
                .options(
                    selectinload(Booking.client),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion)
                )
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .where(
                    and_(
                        ExcursionSlot.start_datetime >= datetime.now(),
                        ExcursionSlot.start_datetime <= reminder_time,
                        Booking.booking_status == BookingStatus.active,
                        Booking.payment_status == PaymentStatus.paid
                    )
                )
            )
            bookings = result.scalars().all()

            logger.debug(f"Найдено бронирований для напоминаний: {len(bookings)}")
            return bookings
        except Exception as e:
            logger.error(f"Ошибка поиска бронирований для напоминаний: {e}", exc_info=True)
            return []

    async def check_slot_availability(self, slot_id: int, additional_people: int = 0) -> bool:
        """Проверить доступность слота для бронирования"""
        logger.debug(f"Проверка доступности слота {slot_id}, дополнительно людей: {additional_people}")

        try:
            slot_result = await self.session.execute(
                select(ExcursionSlot).where(ExcursionSlot.id == slot_id)
            )
            slot = slot_result.scalar_one_or_none()

            if not slot:
                logger.warning(f"Слот с ID {slot_id} не найден")
                return False

            # Считаем уже забронированные места
            booked_people_result = await self.session.execute(
                select(func.sum(Booking.people_count))
                .where(
                    and_(
                        Booking.slot_id == slot_id,
                        Booking.booking_status == BookingStatus.active
                    )
                )
            )
            booked_people = booked_people_result.scalar() or 0

            available = (booked_people + additional_people) <= slot.max_people

            logger.debug(
                f"Доступность слота {slot_id}: "
                f"занято={booked_people}, максимум={slot.max_people}, "
                f"дополнительно={additional_people}, доступно={available}"
            )

            return available

        except Exception as e:
            logger.error(f"Ошибка проверки доступности слота {slot_id}: {e}", exc_info=True)
            return False

   # ===== ТОКЕНЫ И ВИРТУАЛЬНЫЕ ПОЛЬЗОВАТЕЛИ =====

    async def generate_user_token(self, user_id: int) -> str:
        """Сгенерировать постоянный токен для пользователя"""
        logger.info(f"Генерация токена для пользователя ID={user_id}")

        try:
            token = secrets.token_urlsafe(32)

            await self.session.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    verification_token=token,
                    token_created_at=datetime.now()
                )
            )
            await self.session.commit()

            logger.info(f"Токен для пользователя {user_id} сгенерирован")
            logger.debug(f"Токен: {token}")
            return token

        except Exception as e:
            logger.error(f"Ошибка генерации токена для пользователя {user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_user_by_token(self, token: str) -> Optional[User]:
        """Получить пользователя по токену"""
        logger.debug(f"Поиск пользователя по токену: {token[:8]}...")

        try:
            result = await self.session.execute(
                select(User).where(User.verification_token == token)
            )
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Пользователь найден по токену: ID={user.id}, имя='{user.full_name}'")
            else:
                logger.warning(f"Пользователь с токеном {token[:8]}... не найден")

            return user
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя по токену: {e}", exc_info=True)
            return None

    async def link_telegram_to_user(self, token: str, telegram_id: int) -> Optional[User]:
        """Привязать Telegram ID к пользователю по токену"""
        logger.info(f"Привязка Telegram ID {telegram_id} к пользователю по токену {token[:8]}...")

        try:
            # Проверяем, не занят ли telegram_id
            existing_user = await self.get_user_by_telegram_id(telegram_id)
            if existing_user:
                error_msg = f"Telegram ID {telegram_id} уже используется пользователем {existing_user.id}"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            # Получаем пользователя по токену
            user = await self.get_user_by_token(token)
            if not user:
                logger.warning(f"Пользователь с токеном {token[:8]}... не найден")
                return None

            # Проверяем, не привязан ли уже Telegram
            if user.telegram_id:
                error_msg = f"Пользователь уже привязан к Telegram ID {user.telegram_id}"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            # Обновляем пользователя
            await self.session.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    telegram_id=telegram_id,
                    is_virtual=False,
                    verification_token=None,
                    token_created_at=None
                )
            )
            await self.session.commit()

            # Получаем обновленного пользователя
            result = await self.session.execute(
                select(User).where(User.id == user.id)
            )
            updated_user = result.scalar_one()

            logger.info(f"Telegram ID {telegram_id} успешно привязан к пользователю {updated_user.id}")
            return updated_user

        except ValueError as e:
            logger.warning(f"Ошибка валидации при привязке Telegram: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка привязки Telegram ID {telegram_id}: {e}", exc_info=True)
            await self.session.rollback()
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
    ) -> tuple[User, str]:
        """Создать виртуального пользователя (без Telegram)"""
        logger.info(
            f"Создание виртуального пользователя: name='{full_name}', "
            f"created_by={created_by_id}, type={registration_type.value}"
        )

        try:
            # Генерируем постоянный токен
            token = secrets.token_urlsafe(4)

            # Если это ребенок и не указан телефон, генерируем виртуальный
            if linked_to_parent_id and not phone_number:
                parent = await self.get_user_by_id(created_by_id)
                if parent and parent.phone_number:
                    phone_number = f"{parent.phone_number}:{token}:child"
                    logger.debug(f"Сгенерирован виртуальный телефон для ребенка: {phone_number}")

            user = User(
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
                linked_to_parent_id=linked_to_parent_id,
                token_created_at=datetime.now()
            )

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Виртуальный пользователь создан: ID={user.id}, токен={token}")
            return user, token

        except Exception as e:
            logger.error(f"Ошибка создания виртуального пользователя '{full_name}': {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def create_user_by_admin(
        self,
        full_name: str,
        phone_number: str,
        admin_id: int,
        date_of_birth: date = None,
        address: str = None,
        weight: int = None
    ) -> tuple[User, str]:
        """Администратор создает пользователя (без Telegram)"""
        logger.info(f"Создание пользователя администратором: name='{full_name}', admin_id={admin_id}")

        try:
            # Проверяем уникальность телефона
            existing_user = await self.get_user_by_phone(phone_number)
            if existing_user:
                error_msg = f"Номер телефона {phone_number} уже зарегистрирован"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            user, token = await self.create_virtual_user(
                full_name=full_name,
                created_by_id=admin_id,
                registration_type=RegistrationType.ADMIN,
                phone_number=phone_number,
                date_of_birth=date_of_birth,
                weight=weight
            )

            # Обновляем адрес если указан
            if address:
                user.address = address
                await self.session.commit()
                await self.session.refresh(user)

            logger.info(f"Пользователь создан администратором: ID={user.id}, токен={token}")
            return user, token

        except ValueError as e:
            logger.warning(f"Ошибка валидации при создании пользователя админом: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка создания пользователя админом '{full_name}': {e}", exc_info=True)
            raise

    async def create_child_user(
        self,
        child_name: str,
        parent_telegram_id: int,
        date_of_birth: date = None,
        weight: int = None,
        address: str = None
    ) -> tuple[User, str]:
        """Родитель создает ребенка"""
        logger.info(
            f"Создание ребенка: name='{child_name}', "
            f"родитель TG_ID={parent_telegram_id}"
        )

        try:
            parent = await self.get_user_by_telegram_id(parent_telegram_id)
            if not parent:
                error_msg = f"Родитель с ID {parent_telegram_id} не найден"
                logger.error(error_msg)
                raise ValueError(error_msg)

            parent_id = parent.id

            logger.debug(f"Родитель найден: ID={parent_id}, имя='{parent.full_name}'")

            # Проверяем лимит детей (не больше 7)
            children = await self.get_children_users(parent_id)
            if len(children) >= 7:
                error_msg = "Достигнут лимит добавления детей (максимум 7)"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            logger.debug(f"У родителя {parent_id} сейчас {len(children)} детей (лимит: 7)")

            user, token = await self.create_virtual_user(
                full_name=child_name,
                created_by_id=parent_id,
                registration_type=RegistrationType.PARENT,
                date_of_birth=date_of_birth,
                weight=weight,
                address=address,
                linked_to_parent_id=parent_id
            )

            logger.info(f"Ребенок создан: ID={user.id}, токен={token}")
            return user, token

        except ValueError as e:
            logger.warning(f"Ошибка валидации при создании ребенка: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка создания ребенка '{child_name}': {e}", exc_info=True)
            raise

    async def regenerate_user_token(self, user_id: int) -> str:
        """Перегенерировать токен для пользователя"""
        logger.info(f"Перегенерация токена для пользователя ID={user_id}")

        try:
            # Проверяем, есть ли пользователь
            user = await self.get_user_by_id(user_id)
            if not user:
                error_msg = f"Пользователь с ID {user_id} не найден"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Проверяем, не привязан ли уже Telegram
            if user.telegram_id:
                error_msg = "Невозможно перегенерировать токен для пользователя с привязанным Telegram"
                logger.warning(error_msg)
                raise ValueError(error_msg)

            # Генерируем новый токен
            new_token = secrets.token_urlsafe(32)

            await self.session.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    verification_token=new_token,
                    token_created_at=datetime.now()
                )
            )
            await self.session.commit()

            logger.info(f"Токен пользователя {user_id} перегенерирован")
            logger.debug(f"Новый токен: {new_token}")
            return new_token

        except ValueError as e:
            logger.warning(f"Ошибка валидации при перегенерации токена: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка перегенерации токена для пользователя {user_id}: {e}")
            await self.session.rollback()
            raise

    async def revoke_user_token(self, user_id: int) -> bool:
        """Отозвать токен пользователя"""
        logger.info(f"Отзыв токена пользователя ID={user_id}")

        try:
            # Проверяем, есть ли пользователь
            user = await self.get_user_by_id(user_id)
            if not user:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                return False

            # Отзываем только если нет привязанного Telegram
            if not user.telegram_id:
                await self.session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        verification_token=None,
                        token_created_at=None
                    )
                )
                await self.session.commit()
                logger.info(f"Токен пользователя {user_id} отозван")
                return True
            else:
                logger.warning(f"Нельзя отозвать токен у пользователя с привязанным Telegram")
                return False

        except Exception as e:
            logger.error(f"Ошибка отзыва токена пользователя {user_id}: {e}")
            await self.session.rollback()
            return False

    async def get_user_token(self, user_id: int) -> Optional[str]:
        """Получить токен пользователя"""
        logger.debug(f"Получение токена пользователя ID={user_id}")

        try:
            user = await self.get_user_by_id(user_id)
            if user and user.verification_token:
                logger.debug(f"Токен пользователя {user_id} получен")
                return user.verification_token

            logger.debug(f"Токен пользователя {user_id} не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения токена пользователя {user_id}: {e}", exc_info=True)
            return None

    async def can_user_use_token(self, user_id: int) -> bool:
        """Может ли пользователь использовать токен"""
        logger.debug(f"Проверка возможности использования токена пользователем ID={user_id}")

        try:
            user = await self.get_user_by_id(user_id)
            can_use = user and not user.telegram_id and user.verification_token

            logger.debug(f"Пользователь {user_id} может использовать токен: {can_use}")
            return can_use
        except Exception as e:
            logger.error(f"Ошибка проверки возможности использования токена: {e}", exc_info=True)
            return False

    # ===== БРОНИРОВАНИЕ С ТОКЕНАМИ =====

    async def create_booking_with_token(
        self,
        user_id: int,
        excursion_slot_id: int,
        token: str,
        booked_by_id: int = None
    ) -> Optional[Booking]:
        """Создать бронирование с проверкой токена"""
        logger.info(
            f"Создание бронирования с токеном: user_id={user_id}, "
            f"slot_id={excursion_slot_id}, booked_by={booked_by_id}"
        )

        try:
            # Проверяем пользователя и токен
            user = await self.get_user_by_id(user_id)
            if not user or user.verification_token != token:
                logger.warning(f"Неверный токен для пользователя {user_id}")
                return None

            # Проверяем, что это виртуальный пользователь
            if not user.is_virtual:
                logger.warning(f"Пользователь {user_id} не виртуальный, нельзя использовать токен")
                return None

            # Создаем бронирование
            booking = Booking(
                client_id=user_id,
                excursion_slot_id=excursion_slot_id,
                booking_token=token,
                booked_by_id=booked_by_id,
                status=BookingStatus.CONFIRMED
            )

            self.session.add(booking)
            await self.session.commit()
            await self.session.refresh(booking)

            logger.info(f"Бронирование с токеном создано: ID={booking.id}")
            return booking

        except Exception as e:
            logger.error(f"Ошибка создания бронирования с токеном: {e}", exc_info=True)
            await self.session.rollback()
            return None
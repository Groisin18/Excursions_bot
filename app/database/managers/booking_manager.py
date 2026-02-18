"""Менеджер для бизнес-логики бронирований"""

from datetime import datetime
from typing import Tuple, Optional, Dict, List
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession


from .base import BaseManager
from app.database.repositories import (
    BookingRepository, SlotRepository, UserRepository, PromoCodeRepository
)
from app.database.models import (
    Booking, BookingStatus, SlotStatus, ClientStatus, BookingChild,
    ExcursionSlot
)
from app.database.managers import SlotManager
from app.utils.calculators import PriceCalculator


class BookingManager(BaseManager):
    """Менеджер для бизнес-логики бронирований"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.booking_repo = BookingRepository(session)
        self.slot_repo = SlotRepository(session)
        self.user_repo = UserRepository(session)
        self.promo_repo = PromoCodeRepository(session)

    async def create_booking(
        self,
        slot_id: int,
        adult_user_id: int,
        children_count: int,
        total_price: int,
        admin_creator_id: int = None,
        promo_code_id: int = None,
        children_data: Optional[list] = None,
        total_weight: Optional[int] = None
    ) -> Tuple[Optional[Booking], str]:
        """Создать бронирование с проверками"""
        self._log_operation_start("create_booking",
                                 slot_id=slot_id,
                                 adult_user_id=adult_user_id,
                                 people_count=children_count+1)

        try:
            # Проверяем существование слота
            slot = await self.slot_repo.get_by_id(slot_id)
            if not slot:
                error_msg = "Слот не найден"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем статус слота
            if slot.status != SlotStatus.scheduled:
                error_msg = f"Слот имеет статус {slot.status.value}, недоступен для бронирования"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем существование клиента
            adult_user = await self.user_repo.get_by_id(adult_user_id)
            if not adult_user:
                error_msg = "Клиент не найден"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем доступность промокода
            if promo_code_id:
                promo = await self.promo_repo.get_by_id(promo_code_id)
                if not promo or not promo.is_valid:
                    error_msg = "Промокод недействителен"
                    self.logger.warning(error_msg)
                    return None, error_msg

            # Проверяем, нет ли уже активной брони
            existing_booking = await self.booking_repo.get_user_active_for_slot(adult_user_id, slot_id)
            if existing_booking:
                error_msg = "У вас уже есть активная бронь на этот слот"
                self.logger.warning(error_msg)
                return None, error_msg

            slot_manager = SlotManager(self.session)

            # Проверяем количество мест
            booked_places = await slot_manager.get_booked_places(slot_id)
            total_people = 1 + children_count  # 1 взрослый + дети
            if booked_places + total_people > slot.max_people:
                error_msg = f"Недостаточно свободных мест. Свободно: {slot.max_people - booked_places}, требуется: {total_people}"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем вес, если он передан
            if total_weight is not None:
                current_weight = await slot_manager.get_current_weight(slot_id)

                if current_weight + total_weight > slot.max_weight:
                    error_msg = f"Превышение допустимого веса. Доступно: {slot.max_weight - current_weight} кг, вес заявки: {total_weight} кг"
                    self.logger.warning(error_msg)
                    return None, error_msg

                self.logger.info(f"Проверка веса пройдена: текущий {current_weight}кг + новый {total_weight}кг <= макс {slot.max_weight}кг")

            # Создаем бронирование
            booking = await self.booking_repo.create(
                slot_id=slot_id,
                adult_user_id=adult_user_id,
                total_price=total_price,
                admin_creator_id=admin_creator_id,
                promo_code_id=promo_code_id
            )

            # Добавляем детей если есть данные
            if children_data:
                for child_data in children_data:
                    # Проверяем, что age_category есть
                    age_category = child_data.get('age_category')
                    if not age_category:
                        self.logger.error(f"Отсутствует age_category для ребенка {child_data.get('child_id')}")
                        return None, "Ошибка: не указана возрастная категория ребенка"

                    child = BookingChild(
                        booking_id=booking.id,
                        child_user_id=child_data['child_id'],
                        age_category=age_category,
                        calculated_price=child_data.get('price', 0)
                    )
                    self.session.add(child)

                await self._commit()
                await self._refresh(booking)

            self._log_operation_end("create_booking",
                                   success=True,
                                   booking_id=booking.id)

            return booking, ""

        except Exception as e:
            self._log_operation_end("create_booking", success=False)
            error_msg = f"Ошибка создания бронирования: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return None, error_msg

    async def create_booking_with_token(
        self,
        user_id: int,
        slot_id: int,
        token: str,
        booked_by_id: int = None
    ) -> Optional[Booking]:
        """Создать бронирование с проверкой токена виртуального пользователя"""
        self._log_operation_start("create_booking_with_token",
                                user_id=user_id,
                                slot_id=slot_id,
                                booked_by_id=booked_by_id)

        try:
            # Проверяем пользователя и токен
            user = await self.user_repo.get_by_id(user_id)
            if not user or user.verification_token != token:
                self.logger.warning(f"Неверный токен для пользователя {user_id}")
                self._log_operation_end("create_booking_with_token", success=False, error="invalid_token")
                return None

            # Бизнес-логика: проверяем, что это виртуальный пользователь
            if not user.is_virtual:
                self.logger.warning(f"Пользователь {user_id} не виртуальный, нельзя использовать токен")
                self._log_operation_end("create_booking_with_token", success=False, error="not_virtual")
                return None

            # Проверяем слот
            slot = await self.slot_repo.get_by_id(slot_id)
            if not slot or slot.status != SlotStatus.scheduled:
                self.logger.warning(f"Слот {slot_id} не найден или недоступен")
                self._log_operation_end("create_booking_with_token", success=False, error="slot_unavailable")
                return None

            # Проверяем, нет ли уже активной брони
            existing_booking = await self.booking_repo.get_user_active_for_slot(user_id, slot_id)
            if existing_booking:
                self.logger.warning(f"У пользователя {user_id} уже есть активная бронь на слот {slot_id}")
                self._log_operation_end("create_booking_with_token", success=False, error="duplicate_booking")
                return None

            # Создаем бронирование через репозиторий
            booking = await self.booking_repo.create_booking_with_token(
                user_id=user_id,
                slot_id=slot_id,
                token=token,
                booked_by_id=booked_by_id
            )

            if booking:
                self._log_operation_end("create_booking_with_token", success=True, booking_id=booking.id)
            else:
                self._log_operation_end("create_booking_with_token", success=False, error="creation_failed")

            return booking

        except Exception as e:
            self._log_operation_end("create_booking_with_token", success=False)
            self.logger.error(f"Ошибка создания бронирования с токеном: {e}", exc_info=True)
            return None

    async def calculate_price(
        self,
        slot_id: int,
        adult_user_id: int,
        child_user_ids: Optional[list] = None,
        promo_code: Optional[str] = None
    ) -> Tuple[int, Dict]:
        """Рассчитать стоимость бронирования"""
        try:
            # Получаем слот и экскурсию
            slot = await self.slot_repo.get_with_bookings(slot_id)
            if not slot or not slot.excursion:
                return 0, {}

            base_price = slot.excursion.base_price
            total_price = base_price  # Взрослый

            # Расчет для детей
            children_prices = {}
            if child_user_ids:
                for child_id in child_user_ids:
                    child = await self.user_repo.get_by_id(child_id)
                    if child and child.date_of_birth:
                        child_price, category = PriceCalculator.calculate_child_price(
                            base_price, child.date_of_birth
                        )
                        children_prices[child_id] = {
                            'price': child_price,
                            'category': category
                        }
                        total_price += child_price

            # Применение промокода
            discount_info = {}
            if promo_code:
                promo = await self.promo_repo.get_by_code(promo_code)
                if promo and promo.is_valid:
                    if promo.discount_type == 'percent':
                        discount = total_price * promo.discount_value / 100
                    else:  # fixed
                        discount = promo.discount_value

                    total_price = max(0, total_price - discount)
                    discount_info = {
                        'promo_code': promo.code,
                        'discount': discount,
                        'final_price': total_price
                    }

            return total_price, {
                'base_price': base_price,
                'children_prices': children_prices,
                'discount_info': discount_info,
                'total': total_price
            }

        except Exception as e:
            self.logger.error(f"Ошибка расчета стоимости: {e}", exc_info=True)
            return 0, {}

    async def get_full_info(self, booking_id: int) -> Optional[Dict]:
        """Получить полную информацию о бронировании"""
        try:
            booking = await self.booking_repo.get_by_id(booking_id)
            if not booking:
                return None

            # Расчетная стоимость
            calculated_price = await self.calculate_price(
                booking.slot_id,
                booking.adult_user_id,
                # TODO: получить ID детей
            )

            return {
                'booking': booking,
                'calculated_price': calculated_price,
                'slot_info': await self.slot_repo.get_with_bookings(booking.slot_id),
                'adult_user': booking.adult_user,
                'payments': booking.payments
            }

        except Exception as e:
            self.logger.error(f"Ошибка получения информации о бронировании {booking_id}: {e}")
            return None

    async def mark_client_arrived(self, booking_id: int) -> bool:
        """Отметить клиента как прибывшего"""

        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            return False

        booking.client_status = ClientStatus.arrived
        await self.booking_repo.update(booking)
        return True


    async def get_user_active_bookings(self, user_id: int) -> List[Booking]:
        """
        Получить активные бронирования пользователя.

        Активными считаются бронирования со статусом active,
        у которых слот ещё не начался.

        Args:
            user_id: ID пользователя

        Returns:
            List[Booking]: Список активных бронирований,
                        отсортированных по дате слота (ближайшие сверху)
        """
        self._log_operation_start("get_user_active_bookings", user_id=user_id)

        try:

            # Запрос на получение активных бронирований
            query = (
                select(Booking)
                .options(
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.captain),
                    selectinload(Booking.payments),
                    selectinload(Booking.booking_children)
                )
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .where(
                    and_(
                        Booking.adult_user_id == user_id,
                        Booking.booking_status == BookingStatus.active,
                        ExcursionSlot.start_datetime > datetime.now()  # Слот в будущем
                    )
                )
                .order_by(ExcursionSlot.start_datetime.asc())  # Сначала ближайшие
            )

            result = await self.session.execute(query)
            bookings = list(result.scalars().all())

            self._log_operation_end(
                "get_user_active_bookings",
                success=True,
                count=len(bookings)
            )

            return bookings

        except Exception as e:
            self._log_operation_end("get_user_active_bookings", success=False)
            self.logger.error(f"Ошибка получения активных бронирований: {e}", exc_info=True)
            return []

    async def get_user_history_bookings(self, user_id: int) -> List[Booking]:
        """
        Получить историю бронирований пользователя.

        Историей считаются бронирования со статусом:
        - cancelled (отменённые)
        - completed (завершённые)

        Args:
            user_id: ID пользователя

        Returns:
            List[Booking]: Список бронирований из истории,
                        отсортированных по дате слота (новые сверху)
        """
        self._log_operation_start("get_user_history_bookings", user_id=user_id)

        try:
            query = (
                select(Booking)
                .options(
                    selectinload(Booking.slot).selectinload(ExcursionSlot.excursion),
                    selectinload(Booking.slot).selectinload(ExcursionSlot.captain),
                    selectinload(Booking.payments),
                    selectinload(Booking.booking_children)
                )
                .join(ExcursionSlot, Booking.slot_id == ExcursionSlot.id)
                .where(
                    and_(
                        Booking.adult_user_id == user_id,
                        Booking.booking_status.in_([
                            BookingStatus.cancelled,
                            BookingStatus.completed
                        ])
                    )
                )
                .order_by(ExcursionSlot.start_datetime.desc())  # Сначала новые
            )

            result = await self.session.execute(query)
            bookings = list(result.scalars().all())

            self._log_operation_end(
                "get_user_history_bookings",
                success=True,
                count=len(bookings)
            )
            return bookings

        except Exception as e:
            self._log_operation_end("get_user_history_bookings", success=False)
            self.logger.error(f"Ошибка получения истории бронирований: {e}", exc_info=True)
            return []

    async def cancel_booking(
        self,
        booking_id: int,
        auto_refund: bool = True
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Отменить бронирование.

        Args:
            booking_id: ID бронирования
            auto_refund: Автоматически инициировать возврат если возможно

        Returns:
            Tuple[bool, str, Optional[Dict]]:
                - Успех операции
                - Сообщение
                - Данные для возврата (если требуется и auto_refund=True)
        """
        self._log_operation_start(
            "cancel_booking",
            booking_id=booking_id,
            auto_refund=auto_refund
        )

        try:
            # Получаем бронирование
            booking = await self.booking_repo.get_by_id(booking_id)

            if not booking:
                error_msg = "Бронирование не найдено"
                self.logger.warning(error_msg)
                return False, error_msg, None

            # Проверяем, можно ли отменить
            if booking.booking_status == BookingStatus.cancelled:
                error_msg = "Бронирование уже отменено"
                self.logger.warning(error_msg)
                return False, error_msg, None

            if booking.booking_status == BookingStatus.completed:
                error_msg = "Нельзя отменить завершённое бронирование"
                self.logger.warning(error_msg)
                return False, error_msg, None

            # Меняем статус бронирования
            await self.booking_repo.update(
                booking_id,
                booking_status=BookingStatus.cancelled
            )

            self._log_business_event(
                "booking_cancelled",
                booking_id=booking_id,
                slot_id=booking.slot_id,
                was_paid=booking.is_paid
            )

            # Проверяем необходимость возврата
            refund_data = None

            if auto_refund and booking.is_paid:
                # TODO Проверяем возможность возврата через PaymentManager
                # (PaymentManager будет добавлен позже)
                refund_data = {
                    "booking_id": booking_id,
                    "amount": booking.total_price,
                    "reason": "user_cancelled",
                    "needs_refund": True
                }

                self.logger.info(
                    f"Требуется возврат для бронирования {booking_id}, "
                    f"сумма: {booking.total_price}"
                )

            self._log_operation_end(
                "cancel_booking",
                success=True,
                needs_refund=refund_data is not None
            )

            return True, "Бронирование отменено", refund_data

        except Exception as e:
            self._log_operation_end("cancel_booking", success=False)
            error_msg = f"Ошибка отмены бронирования: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg, None


# TODO: Создать отдельный процесс (фоновую задачу), который:
# 1. Находит активные бронирования на прошедшие слоты (start_datetime < now())
# 2. Для неоплаченных - автоматически отменяет их (booking_status = cancelled)
# 3. Для оплаченных - возможно, меняет статус на completed?
# 4. Логирует все изменения

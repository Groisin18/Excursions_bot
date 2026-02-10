"""Менеджер для бизнес-логики бронирований"""

from typing import Tuple, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseManager
from ..repositories.booking_repository import BookingRepository
from ..repositories.slot_repository import SlotRepository
from ..repositories.user_repository import UserRepository
from ..repositories.promocode_repository import PromoCodeRepository
from app.database.models import (
    Booking, BookingStatus, SlotStatus
)
from app.utils.price_calculator import PriceCalculator


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
        client_id: int,
        people_count: int,
        children_count: int,
        total_price: int,
        admin_creator_id: int = None,
        promo_code_id: int = None,
        children_data: Optional[list] = None
    ) -> Tuple[Optional[Booking], str]:
        """Создать бронирование с проверками"""
        self._log_operation_start("create_booking",
                                 slot_id=slot_id,
                                 client_id=client_id,
                                 people_count=people_count)

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
            client = await self.user_repo.get_user_by_id(client_id)
            if not client:
                error_msg = "Клиент не найден"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем доступность промокода
            if promo_code_id:
                promo = await self.promo_repo.get_by_id(promo_code_id)
                if not promo or not promo.is_valid():
                    error_msg = "Промокод недействителен"
                    self.logger.warning(error_msg)
                    return None, error_msg

            # Проверяем, нет ли уже активной брони
            existing_booking = await self.booking_repo.get_user_active_for_slot(client_id, slot_id)
            if existing_booking:
                error_msg = "У вас уже есть активная бронь на этот слот"
                self.logger.warning(error_msg)
                return None, error_msg

            # Проверяем доступность мест и веса
            # (нужен SlotManager для проверки доступности)
            # TODO: добавить проверку через SlotManager

            # Создаем бронирование
            booking = await self.booking_repo.create(
                slot_id=slot_id,
                client_id=client_id,
                people_count=people_count,
                children_count=children_count,
                total_price=total_price,
                admin_creator_id=admin_creator_id,
                promo_code_id=promo_code_id
            )

            # Добавляем детей если есть данные
            if children_data:
                from app.database.models import BookingChild
                for child_data in children_data:
                    child = BookingChild(
                        booking_id=booking.id,
                        child_user_id=child_data['child_id'],
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
            user = await self.user_repo.get_user_by_id(user_id)
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
                    child = await self.user_repo.get_user_by_id(child_id)
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
                if promo and promo.is_valid():
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

    async def cancel_booking(self, booking_id: int, cancelled_by_admin: bool = False) -> Tuple[bool, str]:
        """Отменить бронирование"""
        self._log_operation_start("cancel_booking",
                                 booking_id=booking_id,
                                 by_admin=cancelled_by_admin)

        try:
            booking = await self.booking_repo.get_by_id(booking_id)
            if not booking:
                error_msg = "Бронирование не найдено"
                self.logger.warning(error_msg)
                return False, error_msg

            # Бизнес-правила: можно ли отменять?
            if booking.booking_status == BookingStatus.cancelled:
                error_msg = "Бронирование уже отменено"
                self.logger.warning(error_msg)
                return False, error_msg

            # TODO: Проверка времени до начала экскурсии
            # TODO: Проверка оплаты и возврата средств

            cancelled = await self.booking_repo.cancel(booking_id)

            if cancelled:
                self._log_operation_end("cancel_booking", success=True)
                self._log_business_event("booking_cancelled",
                                        booking_id=booking_id,
                                        by_admin=cancelled_by_admin,
                                        slot_id=booking.slot_id,
                                        client_id=booking.client_id)
                return True, ""
            else:
                error_msg = "Не удалось отменить бронирование"
                self.logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            self._log_operation_end("cancel_booking", success=False)
            error_msg = f"Ошибка отмены бронирования: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def get_full_info(self, booking_id: int) -> Optional[Dict]:
        """Получить полную информацию о бронировании"""
        try:
            booking = await self.booking_repo.get_by_id(booking_id)
            if not booking:
                return None

            # Расчетная стоимость
            calculated_price = await self.calculate_price(
                booking.slot_id,
                booking.client_id,
                # TODO: получить ID детей
            )

            return {
                'booking': booking,
                'calculated_price': calculated_price,
                'slot_info': await self.slot_repo.get_with_bookings(booking.slot_id),
                'client': booking.client,
                'payments': booking.payments
            }

        except Exception as e:
            self.logger.error(f"Ошибка получения информации о бронировании {booking_id}: {e}")
            return None
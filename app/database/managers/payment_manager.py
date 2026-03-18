"""Менеджер для бизнес-логики бронирований"""

import os
from datetime import datetime
from typing import Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession


from .base import BaseManager
from app.database.repositories import (
    BookingRepository, SlotRepository, UserRepository, PromoCodeRepository,
    PaymentRepository
)
from app.database.models import (
    Booking,PaymentStatus, YooKassaStatus, Payment, PaymentMethod
)


class PaymentManager(BaseManager):
    """Менеджер для бизнес-логики оплаты"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.booking_repo = BookingRepository(session)
        self.slot_repo = SlotRepository(session)
        self.user_repo = UserRepository(session)
        self.promo_repo = PromoCodeRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def can_refund(self, booking: Booking) -> Tuple[bool, str]:
        """
        Проверить, возможен ли возврат средств за бронирование.

        Возврат возможен если:
        - Бронирование оплачено (payment_status = paid)
        - До начала экскурсии осталось больше 4 часов (константа)

        Args:
            booking: Объект бронирования (должен быть загружен со slot)

        Returns:
            Tuple[bool, str]: (возможен ли возврат, причина если нет)
        """
        self._log_operation_start("can_refund", booking_id=booking.id)

        try:
            # Проверка оплаты
            if booking.payment_status != PaymentStatus.paid:
                reason = "Бронирование не оплачено"
                self.logger.info(f"Возврат невозможен: {reason}")
                return False, reason

            # Проверка наличия слота
            if not booking.slot:
                reason = "Информация о слоте отсутствует"
                self.logger.error(f"Возврат невозможен: {reason}")
                return False, reason

            # Проверка времени до начала экскурсии
            time_until_start = booking.slot.start_datetime - datetime.now()
            hours_until_start = time_until_start.total_seconds() / 3600
            refund_hours_before = int(os.getenv('REFUND_HOURS_BEFORE', default=4))
            if hours_until_start <= refund_hours_before:
                reason = f"До начала экскурсии осталось меньше {refund_hours_before} часов"
                self.logger.info(f"Возврат невозможен: {reason}")
                return False, reason

            self._log_operation_end("can_refund", success=True, hours_until_start=hours_until_start)
            return True, ""

        except Exception as e:
            self._log_operation_end("can_refund", success=False)
            self.logger.error(f"Ошибка проверки возможности возврата: {e}", exc_info=True)
            return False, "Ошибка при проверке возможности возврата"

    async def get_booking_payments_info(self, booking_id: int) -> Dict:
        """
        Получить информацию о платежах по бронированию.

        Args:
            booking_id: ID бронирования

        Returns:
            Dict с информацией:
            {
                'has_payments': bool,
                'payments': List[Dict],  # список платежей
                'total_paid': int,  # общая сумма оплаченных
                'last_payment': Optional[Dict],  # последний платёж
                'can_refund': bool,  # можно ли вернуть (обёртка над can_refund)
                'refund_reason': str  # причина если нельзя
            }
        """
        self._log_operation_start("get_booking_payments_info", booking_id=booking_id)

        try:
            # Получаем платежи
            payments = await self.payment_repo.get_payments_by_booking(booking_id)

            if not payments:
                result = {
                    'has_payments': False,
                    'payments': [],
                    'total_paid': 0,
                    'last_payment': None,
                    'can_refund': False,
                    'refund_reason': 'Платежи отсутствуют'
                }

                self._log_operation_end("get_booking_payments_info", success=True, has_payments=False)
                return result

            # Преобразуем платежи в словари
            payments_data = []
            total_paid = 0

            for payment in payments:
                payment_dict = {
                    'id': payment.id,
                    'amount': payment.amount,
                    'payment_method': payment.payment_method.value,
                    'status': payment.status.value if payment.status else None,
                    'created_at': payment.created_at,
                    'is_successful': payment.is_successful,
                    'is_online': payment.is_online,
                    'yookassa_payment_id': payment.yookassa_payment_id
                }

                payments_data.append(payment_dict)

                if payment.is_successful:
                    total_paid += payment.amount

            # Последний платёж
            last_payment = payments_data[0] if payments_data else None

            # Получаем бронирование для проверки возврата
            # (нужен доступ к бронированию, возможно передавать его параметром)
            # TODO Пока без проверки can_refund, так как нужен booking со slot

            result = {
                'has_payments': True,
                'payments': payments_data,
                'total_paid': total_paid,
                'last_payment': last_payment,
                'can_refund': False,  # Будет заполнено отдельно
                'refund_reason': 'Требуется проверка бронирования'
            }

            self._log_operation_end(
                "get_booking_payments_info",
                success=True,
                payments_count=len(payments_data),
                total_paid=total_paid
            )

            return result

        except Exception as e:
            self._log_operation_end("get_booking_payments_info", success=False)
            self.logger.error(f"Ошибка получения информации о платежах: {e}", exc_info=True)
            return {
                'has_payments': False,
                'payments': [],
                'total_paid': 0,
                'last_payment': None,
                'can_refund': False,
                'refund_reason': 'Ошибка получения данных'
            }

    async def calculate_refund_amount(self, booking: Booking) -> int:
        """
        Рассчитать сумму к возврату.

        По умолчанию возвращается полная стоимость бронирования.
        В будущем здесь могут быть правила частичного возврата.

        Args:
            booking: Объект бронирования

        Returns:
            int: Сумма к возврату
        """
        self._log_operation_start("calculate_refund_amount", booking_id=booking.id)

        try:
            # Получаем все успешные платежи по бронированию
            payments = await self.payment_repo.get_payments_by_booking(booking.id)

            total_paid = 0
            for payment in payments:
                if payment.is_successful:
                    total_paid += payment.amount

            self._log_operation_end(
                "calculate_refund_amount",
                success=True,
                amount=total_paid
            )

            return total_paid

        except Exception as e:
            self._log_operation_end("calculate_refund_amount", success=False)
            self.logger.error(f"Ошибка расчёта суммы возврата: {e}", exc_info=True)
            return 0

    async def process_refund(self, booking_id: int, amount: int = None) -> Tuple[bool, str]:
        """
        Инициировать процесс возврата средств.

        Args:
            booking_id: ID бронирования
            amount: Сумма возврата (если None - полная стоимость)

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        self._log_operation_start("process_refund", booking_id=booking_id, amount=amount)

        try:
            # TODO: Реализовать логику возврата через YooKassa
            # 1. Получить платежи
            # 2. Для каждого онлайн-платежа создать запрос на возврат через API
            # 3. Обновить статус платежа
            # 4. Обновить статус бронирования (payment_status = refunded)

            self.logger.info(f"Запрос на возврат для бронирования {booking_id}, сумма: {amount}")

            # Временно просто логируем
            self._log_business_event(
                "refund_requested",
                booking_id=booking_id,
                amount=amount
            )

            self._log_operation_end("process_refund", success=True)

            return True, "Запрос на возврат принят в обработку"

        except Exception as e:
            self._log_operation_end("process_refund", success=False)
            self.logger.error(f"Ошибка инициации возврата: {e}", exc_info=True)
            return False, f"Ошибка при создании возврата: {str(e)}"

    async def create_payment_for_booking(
        self,
        booking_id: int,
        amount: int
    ) -> Payment:
        """
        Создать запись о платеже для бронирования.
        Перед созданием отменяет все существующие pending платежи по этой брони.
        """
        self._log_operation_start("create_payment_for_booking", booking_id=booking_id, amount=amount)

        try:
            # Сначала отменяем все старые pending платежи по этой брони
            old_payments = await self.payment_repo.get_pending_payments_by_booking(booking_id)

            for old_payment in old_payments:
                await self.payment_repo.update_payment_by_id(
                    old_payment.id,
                    status=YooKassaStatus.canceled
                )
                self._log_business_event(
                    "old_payment_canceled",
                    old_payment_id=old_payment.id,
                    booking_id=booking_id
                )

            if old_payments:
                self.logger.info(f"Отменено {len(old_payments)} старых платежей для бронирования {booking_id}")

            # Создаем новый платеж
            payment = await self.payment_repo.create_payment(
                booking_id=booking_id,
                amount=amount,
                payment_method=PaymentMethod.online
            )

            self._log_operation_end(
                "create_payment_for_booking",
                success=True,
                payment_id=payment.id
            )
            return payment

        except Exception as e:
            self._log_operation_end("create_payment_for_booking", success=False)
            self.logger.error(f"Ошибка создания платежа: {e}", exc_info=True)
            raise

    async def confirm_payment_success(
        self,
        payment_id: int,
        yookassa_payment_id: str,
        booking_repo: BookingRepository = None
    ) -> bool:
        """
        Подтвердить успешный платеж.
        Обновляет статус платежа и (опционально) бронирования.
        """
        self._log_operation_start(
            "confirm_payment_success",
            payment_id=payment_id,
            yookassa_id=yookassa_payment_id
        )

        try:
            # Обновляем статус платежа
            success = await self.payment_repo.update_payment_by_id(
                payment_id,
                status=YooKassaStatus.succeeded,
                yookassa_payment_id=yookassa_payment_id
            )

            if not success:
                self.logger.error(f"Не удалось обновить платеж {payment_id}")
                return False

            # Если передан репозиторий бронирований, обновляем статус брони
            if booking_repo:
                # Получаем платеж, чтобы узнать booking_id
                payment = await self.payment_repo.get_payment_by_id(payment_id)
                if payment:
                    await booking_repo.update(
                        payment.booking_id,
                        payment_status=PaymentStatus.paid
                    )
                    self._log_business_event(
                        "booking_paid",
                        booking_id=payment.booking_id,
                        payment_id=payment_id
                    )

            self._log_operation_end("confirm_payment_success", success=True)
            return True

        except Exception as e:
            self._log_operation_end("confirm_payment_success", success=False)
            self.logger.error(f"Ошибка подтверждения платежа: {e}", exc_info=True)
            return False

    async def cancel_pending_payment(self, payment_id: int) -> bool:
        """
        Отменить ожидающий платеж.

        Args:
            payment_id: ID платежа

        Returns:
            bool: Успешность операции
        """
        self._log_operation_start("cancel_pending_payment", payment_id=payment_id)

        try:
            # Получаем платеж для проверки статуса
            payment = await self.payment_repo.get_payment_by_id(payment_id)
            if not payment:
                self.logger.error(f"Платеж {payment_id} не найден")
                return False

            # Проверяем, что платеж в статусе pending
            if payment.status != YooKassaStatus.pending:
                self.logger.warning(
                    f"Платеж {payment_id} не в статусе pending (текущий: {payment.status})"
                )
                return False

            # Обновляем статус через репозиторий
            success = await self.payment_repo.update_payment_by_id(
                payment_id,
                status=YooKassaStatus.canceled
            )

            if success:
                self._log_operation_end("cancel_pending_payment", success=True)
            else:
                self._log_operation_end("cancel_pending_payment", success=False)

            return success

        except Exception as e:
            self._log_operation_end("cancel_pending_payment", success=False)
            self.logger.error(f"Ошибка отмены платежа: {e}", exc_info=True)
            return False


# TODO: Реализовать полноценную логику возврата:
# - Интеграция с YooKassa API для создания возвратов
# - Обработка вебхуков от YooKassa по статусам возвратов
# - Частичные возвраты
# - Логирование всех операций с возвратами
# - Уведомления пользователям о статусе возврата
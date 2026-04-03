"""Менеджер для бизнес-логики бронирований"""

import os
import asyncio
from datetime import datetime
from typing import Tuple, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


from .base import BaseManager
from app.database.repositories import (
    BookingRepository, SlotRepository, UserRepository, PromoCodeRepository,
    PaymentRepository, RefundRepository
)
from app.database.models import (
    Booking,PaymentStatus, YooKassaStatus, Payment, PaymentMethod,
    RefundStatus, Refund
)
from app.services.yookassa_refund_client import yookassa_refund_client


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

    async def can_refund_with_cancel_time(
        self,
        booking: Booking,
        cancelled_at: datetime = None
    ) -> Tuple[bool, str]:
        """
        Проверить, возможен ли возврат средств с учетом времени отмены.

        Возврат возможен если:
        - Бронирование оплачено
        - Отмена произошла более чем за 4 часа до начала экскурсии

        Args:
            booking: Объект бронирования (должен быть загружен со slot)
            cancelled_at: Время отмены (если None - текущее время)

        Returns:
            Tuple[bool, str]: (возможен ли возврат, причина если нет)
        """
        self._log_operation_start(
            "can_refund_with_cancel_time",
            booking_id=booking.id,
            cancelled_at=cancelled_at
        )

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

            # Определяем время, относительно которого проверяем
            check_time = cancelled_at if cancelled_at else datetime.now()

            # Проверка времени до начала экскурсии на момент отмены
            time_until_start = booking.slot.start_datetime - check_time
            hours_until_start = time_until_start.total_seconds() / 3600

            refund_hours_before = int(os.getenv('REFUND_HOURS_BEFORE', default=4))

            if hours_until_start <= refund_hours_before:
                reason = f"Отмена произошла менее чем за {refund_hours_before} часов до начала экскурсии"
                self.logger.info(f"Возврат невозможен: {reason} (осталось {hours_until_start:.1f} часов)")
                return False, reason

            self._log_operation_end(
                "can_refund_with_cancel_time",
                success=True,
                hours_until_start=hours_until_start
            )
            return True, ""

        except Exception as e:
            self._log_operation_end("can_refund_with_cancel_time", success=False)
            self.logger.error(f"Ошибка проверки возможности возврата: {e}", exc_info=True)
            return False, "Ошибка при проверке возможности возврата"

    async def get_booking_payments_info(self, booking_id: int, booking: Booking = None) -> Dict:
        """
        Получить информацию о платежах по бронированию.

        Args:
            booking_id: ID бронирования
            booking: Объект бронирования (опционально, если передан - используется для проверки возврата)

        Returns:
            Dict с информацией:
            {
                'has_payments': bool,
                'payments': List[Dict],  # список платежей
                'total_paid': int,  # общая сумма оплаченных
                'last_payment': Optional[Dict],  # последний платёж
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
                    'last_payment': None
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

            result = {
                'has_payments': True,
                'payments': payments_data,
                'total_paid': total_paid,
                'last_payment': last_payment,
            }

            self._log_operation_end(
                "get_booking_payments_info",
                success=True,
                payments_count=len(payments_data),
                total_paid=total_paid,
            )

            return result

        except Exception as e:
            self._log_operation_end("get_booking_payments_info", success=False)
            self.logger.error(f"Ошибка получения информации о платежах: {e}", exc_info=True)
            return {
                'has_payments': False,
                'payments': [],
                'total_paid': 0,
                'last_payment': None
            }

    async def calculate_refund_amount(self, booking: Booking) -> int:
        """
        Рассчитать сумму к возврату в копейках.

        По умолчанию возвращается полная стоимость бронирования.

        Args:
            booking: Объект бронирования

        Returns:
            int: Сумма к возврату
        """
        self._log_operation_start("calculate_refund_amount", booking_id=booking.id)

        try:
            payments = await self.payment_repo.get_payments_by_booking(booking.id)

            total_paid_rub = 0
            for payment in payments:
                if payment.is_successful:
                    total_paid_rub += payment.amount

            total_paid_kopecks = total_paid_rub * 100

            return total_paid_kopecks

        except Exception as e:
            self.logger.error(f"Ошибка расчёта суммы возврата: {e}", exc_info=True)
            return 0

    async def process_refund(
        self,
        booking_id: int,
        reason: str = None,
        amount: int = None,
        max_retries: int = 1
    ) -> Tuple[bool, str, Optional[Refund]]:
        """
        Инициировать процесс возврата средств.

        Args:
            booking_id: ID бронирования
            reason: Причина возврата
            amount: Сумма возврата в копейках (если None - полная стоимость)
            max_retries: Максимальное количество попыток при ошибке

        Returns:
            Tuple[bool, str, Optional[Refund]]: (успех, сообщение, объект возврата)
        """
        self._log_operation_start("process_refund", booking_id=booking_id, amount=amount, reason=reason)

        try:
            booking = await self.booking_repo.get_by_id(booking_id)
            if not booking:
                return False, f"Бронирование {booking_id} не найдено", None

            if booking.slot is None:
                booking = await self.booking_repo.get_with_slot(booking_id)
                if not booking or not booking.slot:
                    return False, "Информация о слоте отсутствует", None

            can_refund, refund_reason = await self.can_refund(booking)
            if not can_refund:
                return False, refund_reason, None

            # Получаем сумму возврата в копейках
            if amount is not None:
                refund_amount_kopecks = amount
            else:
                refund_amount_kopecks = await self.calculate_refund_amount(booking)

            self.logger.info(f"process_refund: refund_amount_kopecks={refund_amount_kopecks} коп.")

            if refund_amount_kopecks <= 0:
                return False, "Сумма возврата равна 0", None

            # Для хранения в БД переводим в рубли
            refund_amount_rub = refund_amount_kopecks // 100

            payments = await self.payment_repo.get_payments_by_booking(booking_id)
            successful_payments = [p for p in payments if p.is_successful and p.is_online]

            if not successful_payments:
                return False, "Не найдено успешных онлайн-платежей для возврата", None

            refund_repo = RefundRepository(self.session)

            all_success = True
            last_refund = None
            messages = []

            for payment in successful_payments:
                existing_refunds = await refund_repo.get_refunds_by_payment(payment.id)
                successful_refunds = [r for r in existing_refunds if r.status == RefundStatus.SUCCEEDED]

                if successful_refunds:
                    messages.append(f"Платеж #{payment.id} уже возвращен")
                    continue

                refund = await refund_repo.create_refund(
                    payment_id=payment.id,
                    booking_id=booking_id,
                    amount=refund_amount_rub,
                    reason=reason or f"Возврат по бронированию #{booking_id}",
                    status=RefundStatus.PENDING
                )
                last_refund = refund

                success, error_msg = await self._execute_refund_with_retry(
                    refund=refund,
                    payment=payment,
                    amount=refund_amount_kopecks,
                    max_retries=max_retries
                )

                if success:
                    messages.append(f"Возврат для платежа #{payment.id} инициирован")
                else:
                    all_success = False
                    messages.append(f"Ошибка возврата для платежа #{payment.id}: {error_msg}")

            if all_success and successful_payments:
                await self.booking_repo.update(
                    booking_id,
                    payment_status=PaymentStatus.refunded
                )
                self._log_business_event(
                    "booking_refunded",
                    booking_id=booking_id,
                    amount=refund_amount_rub
                )

            result_message = "\n".join(messages)
            self._log_operation_end("process_refund", success=all_success, message=result_message)

            return all_success, result_message, last_refund

        except Exception as e:
            self._log_operation_end("process_refund", success=False)
            self.logger.error(f"Ошибка инициации возврата: {e}", exc_info=True)
            return False, f"Ошибка при создании возврата: {str(e)}", None

    async def _execute_refund_with_retry(
        self,
        refund: Refund,
        payment: Payment,
        amount: int,
        max_retries: int = 1
    ) -> Tuple[bool, str]:
        """
        Выполнить создание возврата в YooKassa с ретраем при ошибке.

        Args:
            refund: Объект возврата
            payment: Объект платежа
            amount: Сумма возврата в КОПЕЙКАХ
            max_retries: Максимальное количество попыток

        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """

        refund_repo = RefundRepository(self.session)
        idempotence_key = f"refund:{payment.booking_id}:{payment.id}:{refund.id}:{int(datetime.now().timestamp())}"

        for attempt in range(max_retries + 1):
            try:
                await refund_repo.update_refund_status(
                    refund.id,
                    RefundStatus.PROCESSING,
                    completed_at=None
                )

                success, response_data, error_msg = await yookassa_refund_client.create_refund(
                    payment_id=payment.yookassa_payment_id,
                    amount=amount,
                    idempotence_key=idempotence_key,
                    reason=refund.reason
                )

                if success and response_data:
                    yookassa_refund_id = response_data.get('id')
                    status_from_yookassa = response_data.get('status')

                    if status_from_yookassa == 'succeeded':
                        new_status = RefundStatus.SUCCEEDED
                        completed_at = datetime.now()
                    elif status_from_yookassa == 'canceled':
                        new_status = RefundStatus.CANCELED
                        completed_at = datetime.now()
                        cancellation = response_data.get('cancellation_details', {})
                        await refund_repo.update_refund_status(
                            refund.id,
                            new_status,
                            yookassa_refund_id=yookassa_refund_id,
                            completed_at=completed_at,
                            cancellation_party=cancellation.get('party'),
                            cancellation_reason=cancellation.get('reason')
                        )
                        return False, f"Возврат отменен YooKassa: {cancellation.get('reason', 'неизвестная причина')}"
                    else:
                        new_status = RefundStatus.PROCESSING
                        completed_at = None

                    await refund_repo.update_refund_status(
                        refund.id,
                        new_status,
                        yookassa_refund_id=yookassa_refund_id,
                        completed_at=completed_at
                    )

                    self.logger.info(f"Возврат #{refund.id} успешно создан в YooKassa, статус: {new_status.value}")
                    return True, f"Возврат создан, статус: {status_from_yookassa}"

                else:
                    self.logger.warning(f"Попытка {attempt + 1} создания возврата #{refund.id} не удалась: {error_msg}")

                    if attempt < max_retries:
                        wait_time = 2 ** attempt
                        self.logger.info(f"Повторная попытка через {wait_time} секунд")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        await refund_repo.update_refund_status(
                            refund.id,
                            RefundStatus.FAILED,
                            completed_at=datetime.now()
                        )
                        await refund_repo.increment_retry_count(refund.id)
                        return False, f"Не удалось создать возврат после {max_retries + 1} попыток: {error_msg}"

            except Exception as e:
                self.logger.error(f"Исключение при создании возврата #{refund.id}: {e}", exc_info=True)

                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    await refund_repo.update_refund_status(
                        refund.id,
                        RefundStatus.FAILED,
                        completed_at=datetime.now()
                    )
                    await refund_repo.increment_retry_count(refund.id)
                    return False, f"Ошибка при создании возврата: {str(e)}"

        return False, "Неизвестная ошибка"

    async def check_refund_status(self, refund_id: int) -> Tuple[bool, str]:
        """
        Проверить статус возврата в YooKassa и обновить локальный статус.

        Args:
            refund_id: ID возврата в нашей системе

        Returns:
            Tuple[bool, str]: (успех обновления, сообщение)
        """
        refund_repo = RefundRepository(self.session)
        refund = await refund_repo.get_refund_by_id(refund_id)

        if not refund:
            return False, "Возврат не найден"

        if not refund.yookassa_refund_id:
            return False, "У возврата нет ID в YooKassa"

        # Если возврат уже завершен, не проверяем
        if refund.is_completed:
            return True, f"Возврат уже завершен (статус: {refund.status.value})"

        # Запрашиваем статус из YooKassa
        success, response_data, error_msg = await yookassa_refund_client.get_refund(refund.yookassa_refund_id)

        if not success:
            return False, f"Не удалось получить статус: {error_msg}"

        status_from_yookassa = response_data.get('status')

        if status_from_yookassa == 'succeeded':
            await refund_repo.update_refund_status(
                refund.id,
                RefundStatus.SUCCEEDED,
                completed_at=datetime.now()
            )

            # Обновляем статус бронирования
            await self.booking_repo.update(
                refund.booking_id,
                payment_status=PaymentStatus.refunded
            )

            self._log_business_event(
                "refund_completed",
                refund_id=refund.id,
                booking_id=refund.booking_id,
                amount=refund.amount
            )
            return True, "Возврат успешно завершен"

        elif status_from_yookassa == 'canceled':
            cancellation = response_data.get('cancellation_details', {})
            await refund_repo.update_refund_status(
                refund.id,
                RefundStatus.CANCELED,
                completed_at=datetime.now(),
                cancellation_party=cancellation.get('party'),
                cancellation_reason=cancellation.get('reason')
            )
            return True, f"Возврат отменен: {cancellation.get('reason', 'неизвестная причина')}"

        elif status_from_yookassa in ('pending', 'processing'):
            # Обновляем статус, если он изменился с pending на processing
            if refund.status != RefundStatus.PROCESSING:
                await refund_repo.update_refund_status(refund.id, RefundStatus.PROCESSING)

            return True, f"Возврат в процессе обработки (статус: {status_from_yookassa})"

        else:
            return False, f"Неизвестный статус возврата: {status_from_yookassa}"

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

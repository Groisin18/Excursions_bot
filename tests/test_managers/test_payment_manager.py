"""Тесты для PaymentManager — часть 1."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.database.managers.payment_manager import PaymentManager
from app.database.models import PaymentStatus, YooKassaStatus, PaymentMethod, RefundStatus


class TestPaymentManagerPart1:
    """Тесты для PaymentManager — часть 1."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        return AsyncMock()

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканными зависимостями."""
        with patch("app.database.managers.payment_manager.BaseManager.__init__", return_value=None):
            manager = PaymentManager(mock_session)
            manager.session = mock_session
            manager.logger = MagicMock()
            manager.booking_repo = AsyncMock()
            manager.slot_repo = AsyncMock()
            manager.user_repo = AsyncMock()
            manager.promo_repo = AsyncMock()
            manager.payment_repo = AsyncMock()
            return manager

    # ========== can_refund ==========

    @pytest.mark.asyncio
    async def test_can_refund_not_paid(self, manager):
        """Бронирование не оплачено."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.not_paid

        result, reason = await manager.can_refund(booking)

        assert result is False
        assert "не оплачено" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_refund_no_slot(self, manager):
        """Нет информации о слоте."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = None

        result, reason = await manager.can_refund(booking)

        assert result is False

    @pytest.mark.asyncio
    async def test_can_refund_too_late(self, manager):
        """До начала меньше 4 часов."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=2)

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            result, reason = await manager.can_refund(booking)

            assert result is False
            assert "меньше" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_refund_success(self, manager):
        """Возврат возможен."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=10)

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            result, reason = await manager.can_refund(booking)

            assert result is True
            assert reason == ""

    @pytest.mark.asyncio
    async def test_can_refund_exception(self, manager):
        """Ошибка при проверке."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime.side_effect = Exception("Error")

        result, reason = await manager.can_refund(booking)

        assert result is False
        assert "ошибка" in reason.lower()

    # ========== can_refund_with_cancel_time ==========

    @pytest.mark.asyncio
    async def test_can_refund_with_cancel_time_not_paid(self, manager):
        """Не оплачено."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.not_paid

        result, reason = await manager.can_refund_with_cancel_time(booking)

        assert result is False

    @pytest.mark.asyncio
    async def test_can_refund_with_cancel_time_success(self, manager):
        """Возврат возможен с учётом времени отмены."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=10)
        cancelled_at = datetime.now() - timedelta(hours=1)

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            result, reason = await manager.can_refund_with_cancel_time(booking, cancelled_at)

            assert result is True

    @pytest.mark.asyncio
    async def test_can_refund_with_cancel_time_too_late(self, manager):
        """Отмена слишком поздно."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=2)
        cancelled_at = datetime.now()

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            result, reason = await manager.can_refund_with_cancel_time(booking, cancelled_at)

            assert result is False

    @pytest.mark.asyncio
    async def test_can_refund_with_cancel_time_no_slot(self, manager):
        """Нет слота."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = None

        result, reason = await manager.can_refund_with_cancel_time(booking)

        assert result is False

    # ========== get_booking_payments_info ==========

    @pytest.mark.asyncio
    async def test_get_booking_payments_info_no_payments(self, manager):
        """Нет платежей."""
        manager.payment_repo.get_payments_by_booking.return_value = []

        result = await manager.get_booking_payments_info(1)

        assert result['has_payments'] is False
        assert result['payments'] == []
        assert result['total_paid'] == 0
        assert result['last_payment'] is None

    @pytest.mark.asyncio
    async def test_get_booking_payments_info_with_payments(self, manager):
        """Есть платежи."""
        p1 = MagicMock()
        p1.id = 1
        p1.amount = 5000
        p1.payment_method = PaymentMethod.online
        p1.status = YooKassaStatus.succeeded
        p1.created_at = datetime.now()
        p1.is_successful = True
        p1.is_online = True
        p1.yookassa_payment_id = "test-id"

        manager.payment_repo.get_payments_by_booking.return_value = [p1]

        result = await manager.get_booking_payments_info(1)

        assert result['has_payments'] is True
        assert result['total_paid'] == 5000
        assert len(result['payments']) == 1

    @pytest.mark.asyncio
    async def test_get_booking_payments_info_error(self, manager):
        """Ошибка при получении."""
        manager.payment_repo.get_payments_by_booking.side_effect = Exception("DB error")

        result = await manager.get_booking_payments_info(1)

        assert result['has_payments'] is False

    # ========== calculate_refund_amount ==========

    @pytest.mark.asyncio
    async def test_calculate_refund_amount(self, manager):
        """Расчёт суммы возврата."""
        p1 = MagicMock()
        p1.amount = 5000
        p1.is_successful = True

        manager.payment_repo.get_payments_by_booking.return_value = [p1]

        result = await manager.calculate_refund_amount(MagicMock())

        assert result == 500000  # 5000 руб * 100 коп

    @pytest.mark.asyncio
    async def test_calculate_refund_amount_error(self, manager):
        """Ошибка при расчёте."""
        manager.payment_repo.get_payments_by_booking.side_effect = Exception("Error")

        result = await manager.calculate_refund_amount(MagicMock())

        assert result == 0

    # ========== cancel_pending_payment ==========

    @pytest.mark.asyncio
    async def test_cancel_pending_payment_not_found(self, manager):
        """Платёж не найден."""
        manager.payment_repo.get_payment_by_id.return_value = None

        result = await manager.cancel_pending_payment(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_pending_payment_not_pending(self, manager):
        """Платёж не в статусе pending."""
        payment = MagicMock()
        payment.status = YooKassaStatus.succeeded
        manager.payment_repo.get_payment_by_id.return_value = payment

        result = await manager.cancel_pending_payment(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_pending_payment_success(self, manager):
        """Успешная отмена."""
        payment = MagicMock()
        payment.status = YooKassaStatus.pending
        manager.payment_repo.get_payment_by_id.return_value = payment
        manager.payment_repo.update_payment_by_id.return_value = True

        result = await manager.cancel_pending_payment(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_pending_payment_error(self, manager):
        """Ошибка при отмене."""
        payment = MagicMock()
        payment.status = YooKassaStatus.pending
        manager.payment_repo.get_payment_by_id.return_value = payment
        manager.payment_repo.update_payment_by_id.side_effect = Exception("Error")

        result = await manager.cancel_pending_payment(1)

        assert result is False

    # ========== confirm_payment_success ==========

    @pytest.mark.asyncio
    async def test_confirm_payment_success_no_booking_repo(self, manager):
        """Подтверждение без booking_repo."""
        manager.payment_repo.update_payment_by_id.return_value = True

        result = await manager.confirm_payment_success(
            1, "yookassa-123", booking_repo=None
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_payment_success_with_booking_repo(self, manager):
        """Подтверждение с обновлением бронирования."""
        manager.payment_repo.update_payment_by_id.return_value = True
        payment = MagicMock()
        payment.booking_id = 10
        manager.payment_repo.get_payment_by_id.return_value = payment

        mock_booking_repo = AsyncMock()

        result = await manager.confirm_payment_success(
            1, "yookassa-123", booking_repo=mock_booking_repo
        )

        assert result is True
        mock_booking_repo.update.assert_called_once_with(10, payment_status=PaymentStatus.paid)

    @pytest.mark.asyncio
    async def test_confirm_payment_success_update_failed(self, manager):
        """Не удалось обновить платёж."""
        manager.payment_repo.update_payment_by_id.return_value = False

        result = await manager.confirm_payment_success(1, "yookassa-123")

        assert result is False

    # ========== create_payment_for_booking ==========

    @pytest.mark.asyncio
    async def test_create_payment_for_booking_no_old_payments(self, manager):
        """Создание нового платежа без старых."""
        manager.payment_repo.get_pending_payments_by_booking.return_value = []
        mock_payment = MagicMock()
        mock_payment.id = 1
        manager.payment_repo.create_payment.return_value = mock_payment

        result = await manager.create_payment_for_booking(10, 5000)

        assert result is mock_payment
        manager.payment_repo.create_payment.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_payment_for_booking_with_old_payments(self, manager):
        """Создание с отменой старых pending платежей."""
        old_payment = MagicMock()
        old_payment.id = 99
        manager.payment_repo.get_pending_payments_by_booking.return_value = [old_payment]
        mock_payment = MagicMock()
        mock_payment.id = 1
        manager.payment_repo.create_payment.return_value = mock_payment

        result = await manager.create_payment_for_booking(10, 5000)

        assert result is mock_payment
        manager.payment_repo.update_payment_by_id.assert_called_once_with(
            99, status=YooKassaStatus.canceled
        )

    @pytest.mark.asyncio
    async def test_create_payment_for_booking_error(self, manager):
        """Ошибка при создании."""
        manager.payment_repo.get_pending_payments_by_booking.side_effect = Exception("Error")

        with pytest.raises(Exception):
            await manager.create_payment_for_booking(10, 5000)

    # ========== process_refund ==========

    @pytest.mark.asyncio
    async def test_process_refund_booking_not_found(self, manager):
        """Бронирование не найдено."""
        manager.booking_repo.get_by_id.return_value = None

        success, msg, refund = await manager.process_refund(1)

        assert success is False
        assert "не найдено" in msg.lower()

    @pytest.mark.asyncio
    async def test_process_refund_cannot_refund(self, manager):
        """Возврат невозможен."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.not_paid
        manager.booking_repo.get_by_id.return_value = booking

        success, msg, refund = await manager.process_refund(1)

        assert success is False
        assert "не оплачено" in msg.lower()

    @pytest.mark.asyncio
    async def test_process_refund_zero_amount(self, manager):
        """Сумма возврата равна 0."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=10)
        manager.booking_repo.get_by_id.return_value = booking
        manager.payment_repo.get_payments_by_booking.return_value = []

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            success, msg, refund = await manager.process_refund(1, amount=0)

            assert success is False
            assert "0" in msg

    @pytest.mark.asyncio
    async def test_process_refund_no_successful_online_payments(self, manager):
        """Нет успешных онлайн-платежей."""
        booking = MagicMock()
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=10)
        manager.booking_repo.get_by_id.return_value = booking

        p1 = MagicMock()
        p1.is_successful = True
        p1.is_online = False  # Наличные
        manager.payment_repo.get_payments_by_booking.return_value = [p1]

        with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
            success, msg, refund = await manager.process_refund(1, amount=500000)

            assert success is False
            assert "онлайн" in msg.lower()

    @pytest.mark.asyncio
    async def test_process_refund_success(self, manager):
        """Успешный возврат."""
        booking = MagicMock()
        booking.id = 1
        booking.payment_status = PaymentStatus.paid
        booking.slot = MagicMock()
        booking.slot.start_datetime = datetime.now() + timedelta(hours=10)
        manager.booking_repo.get_by_id.return_value = booking

        payment = MagicMock()
        payment.id = 10
        payment.is_successful = True
        payment.is_online = True
        manager.payment_repo.get_payments_by_booking.return_value = [payment]

        mock_refund = MagicMock()
        mock_refund.id = 1

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.create_refund.return_value = mock_refund
            mock_refund_repo.get_refunds_by_payment.return_value = []
            MockRefundRepo.return_value = mock_refund_repo

            manager._execute_refund_with_retry = AsyncMock(return_value=(True, "OK"))

            with patch("app.database.managers.payment_manager.os.getenv", return_value="4"):
                success, msg, refund = await manager.process_refund(1, amount=500000)

                assert success is True
                assert mock_refund_repo.create_refund.called

    @pytest.mark.asyncio
    async def test_process_refund_exception(self, manager):
        """Ошибка при возврате."""
        manager.booking_repo.get_by_id.side_effect = Exception("DB error")

        success, msg, refund = await manager.process_refund(1)

        assert success is False
        assert "ошибка" in msg.lower()

    # ========== check_refund_status ==========

    @pytest.mark.asyncio
    async def test_check_refund_status_not_found(self, manager):
        """Возврат не найден."""
        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = None
            MockRefundRepo.return_value = mock_refund_repo

            success, msg = await manager.check_refund_status(1)

            assert success is False
            assert "не найден" in msg.lower()

    @pytest.mark.asyncio
    async def test_check_refund_status_no_yookassa_id(self, manager):
        """Нет ID в YooKassa."""
        refund = MagicMock()
        refund.yookassa_refund_id = None
        refund.is_completed = False

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = refund
            MockRefundRepo.return_value = mock_refund_repo

            success, msg = await manager.check_refund_status(1)

            assert success is False
            assert "yookassa" in msg.lower() or "ID" in msg

    @pytest.mark.asyncio
    async def test_check_refund_status_already_completed(self, manager):
        """Возврат уже завершён."""
        refund = MagicMock()
        refund.yookassa_refund_id = "test-id"
        refund.is_completed = True
        refund.status = RefundStatus.SUCCEEDED

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = refund
            MockRefundRepo.return_value = mock_refund_repo

            success, msg = await manager.check_refund_status(1)

            assert success is True
            assert "завершен" in msg.lower()

    @pytest.mark.asyncio
    async def test_check_refund_status_succeeded(self, manager):
        """Возврат успешно завершился."""
        refund = MagicMock()
        refund.id = 1
        refund.yookassa_refund_id = "test-id"
        refund.is_completed = False
        refund.booking_id = 10
        refund.amount = 5000

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = refund
            MockRefundRepo.return_value = mock_refund_repo

            with patch("app.database.managers.payment_manager.yookassa_refund_client") as mock_client:
                mock_client.get_refund = AsyncMock(return_value=(
                    True, {'status': 'succeeded'}, None
                ))

                success, msg = await manager.check_refund_status(1)

                assert success is True
                manager.booking_repo.update.assert_called_once_with(
                    10, payment_status=PaymentStatus.refunded
                )

    @pytest.mark.asyncio
    async def test_check_refund_status_canceled(self, manager):
        """Возврат отменён YooKassa."""
        refund = MagicMock()
        refund.id = 1
        refund.yookassa_refund_id = "test-id"
        refund.is_completed = False

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = refund
            MockRefundRepo.return_value = mock_refund_repo

            with patch("app.database.managers.payment_manager.yookassa_refund_client") as mock_client:
                mock_client.get_refund = AsyncMock(return_value=(
                    True, {'status': 'canceled', 'cancellation_details': {'party': 'yookassa', 'reason': 'expired'}}, None
                ))

                success, msg = await manager.check_refund_status(1)

                assert success is True
                assert "отмен" in msg.lower()

    @pytest.mark.asyncio
    async def test_check_refund_status_processing(self, manager):
        """Возврат в обработке."""
        refund = MagicMock()
        refund.id = 1
        refund.yookassa_refund_id = "test-id"
        refund.is_completed = False
        refund.status = RefundStatus.PENDING

        with patch("app.database.managers.payment_manager.RefundRepository") as MockRefundRepo:
            mock_refund_repo = AsyncMock()
            mock_refund_repo.get_refund_by_id.return_value = refund
            MockRefundRepo.return_value = mock_refund_repo

            with patch("app.database.managers.payment_manager.yookassa_refund_client") as mock_client:
                mock_client.get_refund = AsyncMock(return_value=(
                    True, {'status': 'pending'}, None
                ))

                success, msg = await manager.check_refund_status(1)

                assert success is True
                assert "обработк" in msg.lower() or "pending" in msg.lower()
"""Тесты для моделей базы данных."""

import pytest
from datetime import datetime, date, timedelta

from app.database.models import (
    User, Excursion, ExcursionSlot, Booking, BookingChild,
    Payment, Refund, PromoCode, Notification, TelegramFile,
    SystemSetting,
    UserRole, SlotStatus, BookingStatus, ClientStatus,
    PaymentStatus, PaymentMethod, YooKassaStatus, RefundStatus,
    DiscountType, RegistrationType, FileType,
    NotificationStatus, SchedulePeriod
)


# ========== ТЕСТЫ ENUM-КЛАССОВ ==========

class TestUserRole:
    def test_values(self):
        assert UserRole.client.value == "client"
        assert UserRole.captain.value == "captain"
        assert UserRole.admin.value == "admin"

    def test_membership(self):
        assert "client" in [r.value for r in UserRole]
        assert "captain" in [r.value for r in UserRole]


class TestSlotStatus:
    def test_values(self):
        assert SlotStatus.scheduled.value == "scheduled"
        assert SlotStatus.completed.value == "completed"
        assert SlotStatus.cancelled.value == "cancelled"
        assert SlotStatus.in_progress.value == "in_progress"

    def test_count(self):
        assert len(SlotStatus) == 4


class TestBookingStatus:
    def test_values(self):
        assert BookingStatus.pending_payment.value == "pending_payment"
        assert BookingStatus.active.value == "active"
        assert BookingStatus.cancelled.value == "cancelled"
        assert BookingStatus.completed.value == "completed"

    def test_equality(self):
        assert BookingStatus.active == BookingStatus.active
        assert BookingStatus.active != BookingStatus.cancelled


class TestClientStatus:
    def test_values(self):
        assert ClientStatus.not_arrived.value == "not_arrived"
        assert ClientStatus.arrived.value == "arrived"


class TestPaymentStatus:
    def test_values(self):
        assert PaymentStatus.not_paid.value == "not_paid"
        assert PaymentStatus.pending.value == "pending"
        assert PaymentStatus.paid.value == "paid"
        assert PaymentStatus.refunded.value == "refunded"

    def test_count(self):
        assert len(PaymentStatus) == 4


class TestPaymentMethod:
    def test_values(self):
        assert PaymentMethod.cash.value == "cash"
        assert PaymentMethod.online.value == "online"


class TestYooKassaStatus:
    def test_values(self):
        assert YooKassaStatus.pending.value == "pending"
        assert YooKassaStatus.succeeded.value == "succeeded"
        assert YooKassaStatus.canceled.value == "canceled"


class TestRefundStatus:
    def test_values(self):
        assert RefundStatus.PENDING.value == "pending"
        assert RefundStatus.PROCESSING.value == "processing"
        assert RefundStatus.SUCCEEDED.value == "succeeded"
        assert RefundStatus.FAILED.value == "failed"
        assert RefundStatus.CANCELED.value == "canceled"

    def test_count(self):
        assert len(RefundStatus) == 5


class TestDiscountType:
    def test_values(self):
        assert DiscountType.percent.value == "percent"
        assert DiscountType.fixed.value == "fixed"


class TestRegistrationType:
    def test_values(self):
        assert RegistrationType.SELF.value == "self"
        assert RegistrationType.ADMIN.value == "admin"
        assert RegistrationType.PARENT.value == "parent"
        assert RegistrationType.VIRTUAL_CHILD.value == "virtual_child"


class TestFileType:
    def test_values(self):
        assert FileType.CPD.value == "concent_personal_data"
        assert FileType.CPD_MINOR.value == "concent_personal_data_minor"
        assert FileType.OTHER.value == "other"


class TestNotificationStatus:
    def test_values(self):
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.IN_PROGRESS.value == "in_progress"
        assert NotificationStatus.COMPLETED.value == "completed"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.CANCELLED.value == "cancelled"


# ========== ТЕСТЫ МОДЕЛИ USER ==========

class TestUserModel:
    @pytest.fixture
    def user(self):
        return User(
            id=1,
            telegram_id=123456,
            role=UserRole.client,
            full_name="Иван Иванов",
            phone_number="+71234567890",
            date_of_birth=date(1990, 5, 15),
            email="ivan@example.com",
            address="г. Москва",
            weight=80,
            consent_to_pd=True,
            is_virtual=False,
            verification_token="abc123",
            registration_type=RegistrationType.SELF,
            receive_mass_notifications=True,
            created_at=datetime(2026, 1, 1, 12, 0, 0)
        )

    @pytest.fixture
    def virtual_user(self):
        return User(
            id=2,
            role=UserRole.client,
            full_name="Ребёнок",
            phone_number="+71234567890:token123:child",
            is_virtual=True,
            verification_token="token123",
            telegram_id=None,
            registration_type=RegistrationType.PARENT
        )

    def test_repr(self, user):
        result = repr(user)
        assert "User(id=1" in result
        assert "Иван Иванов" in result
        assert "client" in result

    def test_str(self, user):
        result = str(user)
        assert "Иван Иванов" in result
        assert "client" in result

    def test_has_active_token_true(self, virtual_user):
        assert virtual_user.has_active_token is True

    def test_has_active_token_false_with_telegram(self, user):
        # Есть токен, но есть telegram_id — значит уже активирован
        assert user.has_active_token is False

    def test_has_active_token_false_no_token(self):
        u = User(verification_token=None, telegram_id=None)
        assert u.has_active_token is False

    def test_is_self_registered(self, user):
        assert user.is_self_registered is True

    def test_is_self_registered_admin(self):
        u = User(registration_type=RegistrationType.ADMIN)
        assert u.is_self_registered is False

    def test_is_virtual_phone_true(self, virtual_user):
        assert virtual_user.is_virtual_phone is True

    def test_is_virtual_phone_false(self, user):
        assert user.is_virtual_phone is False

    def test_age(self, user):
        # Возраст на момент теста
        assert user.age is not None
        assert user.age > 0

    def test_age_no_date_of_birth(self):
        u = User(date_of_birth=None)
        assert u.age is None

    def test_to_dict(self, user):
        d = user.to_dict()
        assert d['id'] == 1
        assert d['telegram_id'] == 123456
        assert d['role'] == 'client'
        assert d['full_name'] == 'Иван Иванов'
        assert '***' in d['phone_number']
        assert d['is_virtual'] is False
        assert d['registration_type'] == 'self'
        assert d['created_at'] is not None

    def test_to_dict_no_phone(self):
        u = User(
            role=UserRole.client,
            full_name="Тест",
            phone_number=None,
            registration_type=RegistrationType.SELF
        )
        d = u.to_dict()
        assert d['phone_number'] is None


# ========== ТЕСТЫ МОДЕЛИ EXCURSION ==========

class TestExcursionModel:
    @pytest.fixture
    def excursion(self):
        return Excursion(
            id=1,
            name="Морская прогулка",
            description="Отличная прогулка",
            base_duration_minutes=120,
            base_price=5000,
            is_active=True
        )

    def test_repr(self, excursion):
        result = repr(excursion)
        assert "Морская прогулка" in result
        assert "5000" in result

    def test_str(self, excursion):
        result = str(excursion)
        assert "Морская прогулка" in result
        assert "5000" in result
        assert "120" in result

    def test_to_dict(self, excursion):
        d = excursion.to_dict()
        assert d['name'] == 'Морская прогулка'
        assert d['base_price'] == 5000
        assert d['duration_minutes'] == 120
        assert d['is_active'] is True


# ========== ТЕСТЫ МОДЕЛИ EXCURSION_SLOT ==========

class TestExcursionSlotModel:
    @pytest.fixture
    def future_slot(self):
        exc = Excursion(id=1, name="Тест", base_duration_minutes=60, base_price=1000)
        slot = ExcursionSlot(
            id=1,
            excursion_id=1,
            start_datetime=datetime.now() + timedelta(hours=5),
            end_datetime=datetime.now() + timedelta(hours=6),
            max_people=10,
            max_weight=1000,
            status=SlotStatus.scheduled
        )
        slot.excursion = exc
        return slot

    @pytest.fixture
    def past_slot(self):
        exc = Excursion(id=2, name="Тест 2", base_duration_minutes=60, base_price=1000)
        slot = ExcursionSlot(
            id=2,
            excursion_id=2,
            start_datetime=datetime.now() - timedelta(hours=5),
            end_datetime=datetime.now() - timedelta(hours=4),
            max_people=10,
            max_weight=1000,
            status=SlotStatus.scheduled
        )
        slot.excursion = exc
        return slot

    def test_is_available_true(self, future_slot):
        assert future_slot.is_available is True

    def test_is_available_past(self, past_slot):
        assert past_slot.is_available is False

    def test_is_available_cancelled(self):
        slot = ExcursionSlot(
            start_datetime=datetime.now() + timedelta(hours=1),
            status=SlotStatus.cancelled
        )
        assert slot.is_available is False

    def test_is_available_completed(self):
        slot = ExcursionSlot(
            start_datetime=datetime.now() + timedelta(hours=1),
            status=SlotStatus.completed
        )
        assert slot.is_available is False

    def test_repr(self, future_slot):
        result = repr(future_slot)
        assert "ExcursionSlot" in result
        assert "scheduled" in result

    def test_str(self, future_slot):
        result = str(future_slot)
        assert "Тест" in result
        assert "scheduled" in result

    def test_to_dict(self, future_slot):
        d = future_slot.to_dict()
        assert d['excursion_id'] == 1
        assert d['max_people'] == 10
        assert d['status'] == 'scheduled'


# ========== ТЕСТЫ МОДЕЛИ BOOKING ==========

class TestBookingModel:
    @pytest.fixture
    def booking(self):
        b = Booking(
            id=1,
            slot_id=10,
            adult_user_id=5,
            total_price=5000,
            booking_status=BookingStatus.active,
            client_status=ClientStatus.not_arrived,
            payment_status=PaymentStatus.not_paid,
            created_at=datetime(2026, 1, 1, 12, 0, 0)
        )
        # Мокаем детей для people_count
        child1 = BookingChild(age_category="8-12 лет", calculated_price=1000)
        child2 = BookingChild(age_category="4-7 лет", calculated_price=500)
        b.booking_children = [child1, child2]
        return b

    def test_people_count(self, booking):
        assert booking.people_count == 3  # 1 взрослый + 2 ребёнка

    def test_children_count(self, booking):
        assert booking.children_count == 2

    def test_adults_count(self, booking):
        assert booking.adults_count == 1

    def test_is_active_true(self, booking):
        assert booking.is_active is True

    def test_is_active_false(self):
        b = Booking(booking_status=BookingStatus.cancelled)
        assert b.is_active is False

    def test_is_paid_true(self):
        b = Booking(payment_status=PaymentStatus.paid)
        assert b.is_paid is True

    def test_is_paid_false(self):
        b = Booking(payment_status=PaymentStatus.not_paid)
        assert b.is_paid is False

    def test_to_dict(self, booking):
        d = booking.to_dict()
        assert d['id'] == 1
        assert d['slot_id'] == 10
        assert d['people_count'] == 3
        assert d['children_count'] == 2
        assert d['total_price'] == 5000
        assert d['booking_status'] == 'active'
        assert d['payment_status'] == 'not_paid'


# ========== ТЕСТЫ МОДЕЛИ PAYMENT ==========

class TestPaymentModel:
    @pytest.fixture
    def payment_online(self):
        return Payment(
            id=1,
            booking_id=10,
            amount=5000,
            payment_method=PaymentMethod.online,
            yookassa_payment_id="test-payment-id",
            status=YooKassaStatus.succeeded,
            created_at=datetime(2026, 1, 1, 12, 0, 0)
        )

    @pytest.fixture
    def payment_cash(self):
        return Payment(
            id=2,
            booking_id=11,
            amount=3000,
            payment_method=PaymentMethod.cash,
            status=YooKassaStatus.succeeded
        )

    def test_is_online_true(self, payment_online):
        assert payment_online.is_online is True

    def test_is_online_false(self, payment_cash):
        assert payment_cash.is_online is False

    def test_is_successful_true(self, payment_online):
        assert payment_online.is_successful is True

    def test_is_successful_false(self):
        p = Payment(payment_method=PaymentMethod.online, status=YooKassaStatus.pending)
        assert p.is_successful is False

    def test_repr(self, payment_online):
        result = repr(payment_online)
        assert "5000" in result
        assert "online" in result

    def test_str(self, payment_online):
        result = str(payment_online)
        assert "5000" in result
        assert "онлайн" in result

    def test_str_cash(self, payment_cash):
        result = str(payment_cash)
        assert "наличные" in result

    def test_to_dict(self, payment_online):
        d = payment_online.to_dict()
        assert d['amount'] == 5000
        assert d['payment_method'] == 'online'
        assert d['status'] == 'succeeded'
        assert d['is_online'] is True


# ========== ТЕСТЫ МОДЕЛИ REFUND ==========

class TestRefundModel:
    @pytest.fixture
    def refund_succeeded(self):
        return Refund(
            id=1,
            payment_id=10,
            booking_id=5,
            amount=5000,
            status=RefundStatus.SUCCEEDED,
            yookassa_refund_id="test-refund-id",
            retry_count=0,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            completed_at=datetime(2026, 1, 1, 12, 5, 0)
        )

    @pytest.fixture
    def refund_pending(self):
        return Refund(
            id=2,
            payment_id=11,
            booking_id=6,
            amount=3000,
            status=RefundStatus.PENDING
        )

    def test_is_completed_succeeded(self, refund_succeeded):
        assert refund_succeeded.is_completed is True

    def test_is_completed_failed(self):
        r = Refund(status=RefundStatus.FAILED)
        assert r.is_completed is True

    def test_is_completed_canceled(self):
        r = Refund(status=RefundStatus.CANCELED)
        assert r.is_completed is True

    def test_is_completed_pending(self, refund_pending):
        assert refund_pending.is_completed is False

    def test_is_completed_processing(self):
        r = Refund(status=RefundStatus.PROCESSING)
        assert r.is_completed is False

    def test_repr(self, refund_succeeded):
        result = repr(refund_succeeded)
        assert "5000" in result
        assert "succeeded" in result

    def test_str(self, refund_succeeded):
        result = str(refund_succeeded)
        assert "5000" in result
        assert "succeeded" in result

    def test_to_dict(self, refund_succeeded):
        d = refund_succeeded.to_dict()
        assert d['amount'] == 5000
        assert d['status'] == 'succeeded'
        assert d['retry_count'] == 0
        assert d['booking_id'] == 5


# ========== ТЕСТЫ МОДЕЛИ PROMOCODE ==========

class TestPromoCodeModel:
    @pytest.fixture
    def valid_promo_percent(self):
        return PromoCode(
            id=1,
            code="SALE20",
            discount_type=DiscountType.percent,
            discount_value=20,
            valid_from=datetime.now() - timedelta(days=10),
            valid_until=datetime.now() + timedelta(days=10),
            usage_limit=10,
            used_count=3
        )

    @pytest.fixture
    def valid_promo_fixed(self):
        return PromoCode(
            id=2,
            code="FLAT500",
            discount_type=DiscountType.fixed,
            discount_value=500,
            valid_from=datetime.now() - timedelta(days=10),
            valid_until=None,
            usage_limit=0,
            used_count=100
        )

    @pytest.fixture
    def expired_promo(self):
        return PromoCode(
            id=3,
            code="OLD10",
            discount_type=DiscountType.percent,
            discount_value=10,
            valid_from=datetime.now() - timedelta(days=30),
            valid_until=datetime.now() - timedelta(days=1),
            usage_limit=5,
            used_count=0
        )

    @pytest.fixture
    def exhausted_promo(self):
        return PromoCode(
            id=4,
            code="USEDUP",
            discount_type=DiscountType.fixed,
            discount_value=100,
            valid_from=datetime.now() - timedelta(days=5),
            valid_until=datetime.now() + timedelta(days=5),
            usage_limit=5,
            used_count=5
        )

    def test_is_valid_true_percent(self, valid_promo_percent):
        assert valid_promo_percent.is_valid is True

    def test_is_valid_true_fixed(self, valid_promo_fixed):
        assert valid_promo_fixed.is_valid is True

    def test_is_valid_expired(self, expired_promo):
        assert expired_promo.is_valid is False

    def test_is_valid_exhausted(self, exhausted_promo):
        assert exhausted_promo.is_valid is False

    def test_remaining_uses(self, valid_promo_percent):
        assert valid_promo_percent.remaining_uses == 7

    def test_remaining_uses_unlimited(self, valid_promo_fixed):
        assert valid_promo_fixed.remaining_uses == 0  # max(0, 0 - 100) = 0

    def test_remaining_uses_exhausted(self, exhausted_promo):
        assert exhausted_promo.remaining_uses == 0

    def test_apply_discount_percent(self, valid_promo_percent):
        result = valid_promo_percent.apply_discount(5000)
        assert result == 4000  # 5000 - 20% = 4000

    def test_apply_discount_fixed(self, valid_promo_fixed):
        result = valid_promo_fixed.apply_discount(5000)
        assert result == 4500  # 5000 - 500 = 4500

    def test_apply_discount_not_negative(self):
        promo = PromoCode(discount_type=DiscountType.fixed, discount_value=9999)
        result = promo.apply_discount(1000)
        assert result == 0

    def test_str_percent(self, valid_promo_percent):
        result = str(valid_promo_percent)
        assert "SALE20" in result
        assert "20%" in result

    def test_str_fixed(self, valid_promo_fixed):
        result = str(valid_promo_fixed)
        assert "500 руб" in result

    def test_to_dict(self, valid_promo_percent):
        d = valid_promo_percent.to_dict()
        assert d['code'] == 'SALE20'
        assert d['discount_type'] == 'percent'
        assert d['discount_value'] == 20
        assert d['is_valid'] is True
        assert d['remaining_uses'] == 7


# ========== ТЕСТЫ МОДЕЛИ NOTIFICATION ==========

class TestNotificationModel:
    @pytest.fixture
    def notification(self):
        return Notification(
            id=1,
            message="Важная информация для всех клиентов! Не забудьте про скидки.",
            audience_type=UserRole.client,
            status=NotificationStatus.PENDING,
            total_recipients=100,
            sent_count=45,
            failed_count=5,
            created_at=datetime(2026, 1, 1, 12, 0, 0)
        )

    def test_repr(self, notification):
        result = repr(notification)
        assert "client" in result
        assert "pending" in result

    def test_str(self, notification):
        result = str(notification)
        assert "клиент" in result.lower() or "client" in result

    def test_short_message_long(self, notification):
        assert len(notification.short_message) <= 50
        assert "..." in notification.short_message

    def test_short_message_short(self):
        n = Notification(message="Короткое сообщение")
        assert n.short_message == "Короткое сообщение"

    def test_progress_percent(self, notification):
        assert notification.progress_percent == 50.0  # (45 + 5) / 100 * 100

    def test_progress_percent_zero_recipients(self):
        n = Notification(total_recipients=0)
        assert n.progress_percent == 0.0

    def test_progress_percent_completed(self):
        n = Notification(total_recipients=10, sent_count=10, failed_count=0)
        assert n.progress_percent == 100.0

    def test_to_dict(self, notification):
        d = notification.to_dict()
        assert d['audience_type'] == 'client'
        assert d['total'] == 100
        assert d['sent'] == 45
        assert d['failed'] == 5
        assert d['progress'] == 50.0


# ========== ТЕСТЫ МОДЕЛИ TELEGRAM_FILE ==========

class TestTelegramFileModel:
    @pytest.fixture
    def telegram_file(self):
        return TelegramFile(
            id=1,
            file_type=FileType.CPD,
            file_telegram_id="BQACAgIAAxkBAA",
            file_name="consent.pdf",
            file_size=123456,
            uploaded_by=10,
            uploaded_at=datetime(2026, 1, 1, 12, 0, 0)
        )

    def test_repr(self, telegram_file):
        result = repr(telegram_file)
        assert "TelegramFile" in result

    def test_to_dict(self, telegram_file):
        d = telegram_file.to_dict()
        assert d['file_type'] == FileType.CPD
        assert d['file_name'] == 'consent.pdf'
        assert d['file_size'] == 123456
        assert d['uploaded_by'] == 10


# ========== ТЕСТЫ МОДЕЛИ SYSTEM_SETTING ==========

class TestSystemSettingModel:
    @pytest.fixture
    def setting(self):
        return SystemSetting(
            id=1,
            key="vat_rate",
            value="20",
            description="Ставка НДС",
            updated_at=datetime(2026, 1, 1, 12, 0, 0)
        )

    def test_repr(self, setting):
        result = repr(setting)
        assert "vat_rate" in result
        assert "20" in result

    def test_to_dict(self, setting):
        d = setting.to_dict()
        assert d['key'] == 'vat_rate'
        assert d['value'] == '20'
        assert d['description'] == 'Ставка НДС'
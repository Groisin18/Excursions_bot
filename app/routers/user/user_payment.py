"""
Модуль для оплаты бронирований пользователем через YooKassa.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, ContentType
)
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

from app.database.session import async_session
from app.database.unit_of_work import UnitOfWork
from app.database.repositories import (
    BookingRepository, PaymentRepository, UserRepository
)
from app.database.models import (
    PaymentStatus, YooKassaStatus, PaymentMethod, BookingStatus, User, Payment
)
from app.utils.logging_config import get_logger
from app.user_panel.keyboards import(
    main_menu, booking_detail_keyboard
)

# https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-bank-card-data тестовые карты
# https://yookassa.ru/my/payments Основная страница
# https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram Инструкция для разработчика


load_dotenv()
PAYMENTS_TOKEN = os.getenv('PAYMENTS_TOKEN')
# Флаг отправки чеков по 54-ФЗ (true/false)
SEND_RECEIPT = os.getenv('SEND_RECEIPT', 'false').lower() == 'true'

if not PAYMENTS_TOKEN:
    logger = get_logger(__name__)
    logger.error("PAYMENTS_TOKEN не установлен в переменных окружения")

router = Router(name="user_payment")
logger = get_logger(__name__)

# Константа для проверки срока оплаты (сама отмена происходит через scheduler)
PAYMENT_TIMEOUT_HOURS = 24


def build_receipt_data(user: User, booking, excursion) -> Optional[Dict]:
    """
    Формирует данные для чека по 54-ФЗ.

    Args:
        user: Объект пользователя
        booking: Объект бронирования
        excursion: Объект экскурсии

    Returns:
        Dict с данными для чека или None, если отправка чеков отключена
    """
    if not SEND_RECEIPT:
        return None

    # TODO: Сделать возможность изменения SEND_RECEIPT через админ-панель
    # Планируется добавить в раздел настроек админки:
    # - Вкл/Выкл отправку чеков
    # - Выбор системы налогообложения
    # - Настройку ставок НДС

    # Базовая структура чека
    receipt_data = {
        "receipt": {
            "customer": {},
            "items": []
        }
    }

    # Добавляем данные клиента (что есть)
    if user.full_name:
        receipt_data["receipt"]["customer"]["full_name"] = user.full_name
    if user.phone_number:
        receipt_data["receipt"]["customer"]["phone"] = user.phone_number
    if user.email:
        receipt_data["receipt"]["customer"]["email"] = user.email

    # Формируем позицию в чеке
    # Внимание! vat_code нужно настроить под систему налогообложения ИП
    # По умолчанию ставим 1 (НДС 20%), но лучше уточнить у заказчика
    item = {
        "description": f"Экскурсия {excursion.name}",
        "quantity": 1,
        "amount": {
            "value": f"{booking.total_price}.00",
            "currency": "RUB"
        },
        "vat_code": 1  # TODO: Сделать настраиваемым через админ-панель
    }

    receipt_data["receipt"]["items"].append(item)

    return receipt_data


@router.callback_query(F.data.startswith('pay_booking:'))
async def initiate_payment(callback: CallbackQuery):
    """
    Запуск процесса оплаты для конкретного бронирования.
    Проверяет возможность оплаты и отправляет инвойс.
    """
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} инициирует оплату")

    try:
        # Парсим ID бронирования
        booking_id = int(callback.data.split(':')[1])
        await callback.answer()

        # Проверяем наличие токена
        if not PAYMENTS_TOKEN:
            logger.error("PAYMENTS_TOKEN не настроен")
            await callback.message.answer(
                "Оплата временно недоступна. Пожалуйста, попробуйте позже или свяжитесь с администратором.",
                reply_markup=main_menu()
            )
            return

        async with async_session() as session:
            # Получаем репозитории
            booking_repo = BookingRepository(session)
            user_repo = UserRepository(session)
            payment_repo = PaymentRepository(session)

            # Проверяем существование брони
            booking = await booking_repo.get_by_id(booking_id)
            if not booking:
                logger.warning(f"Бронирование {booking_id} не найдено для пользователя {user_telegram_id}")
                await callback.message.answer(
                    "Бронирование не найдено.",
                    reply_markup=main_menu()
                )
                return

            # Проверяем, что бронь принадлежит этому пользователю
            user = await user_repo.get_by_telegram_id(user_telegram_id)
            if not user or booking.adult_user_id != user.id:
                logger.warning(
                    f"Пользователь {user_telegram_id} пытается оплатить чужое бронирование {booking_id}"
                )
                await callback.message.answer(
                    "У вас нет доступа к этому бронированию.",
                    reply_markup=main_menu()
                )
                return

            # Проверяем статус брони
            if booking.booking_status != BookingStatus.active:
                logger.info(
                    f"Бронирование {booking_id} не активно (статус: {booking.booking_status.value})"
                )
                await callback.message.answer(
                    "Это бронирование уже неактивно и не может быть оплачено.",
                    reply_markup=booking_detail_keyboard(booking_id, show_pay=False)
                )
                return

            # Проверяем статус оплаты
            if booking.payment_status == PaymentStatus.paid:
                logger.info(f"Бронирование {booking_id} уже оплачено")
                await callback.message.answer(
                    "Это бронирование уже оплачено.",
                    reply_markup=booking_detail_keyboard(booking_id, show_pay=False)
                )
                return

            if booking.payment_status == PaymentStatus.pending:
                logger.info(f"Платеж для бронирования {booking_id} уже в обработке")
                await callback.message.answer(
                    "Платеж для этого бронирования уже обрабатывается.\n"
                    "Пожалуйста, дождитесь завершения или попробуйте позже.",
                    reply_markup=booking_detail_keyboard(booking_id, show_pay=False)
                )
                return

            # Проверяем, не истек ли срок оплаты (только проверка, отменяет scheduler)
            time_elapsed = datetime.now() - booking.created_at
            if time_elapsed > timedelta(hours=PAYMENT_TIMEOUT_HOURS):
                logger.info(f"Срок оплаты для бронирования {booking_id} истек")
                await callback.message.answer(
                    f"Срок оплаты бронирования истек (более {PAYMENT_TIMEOUT_HOURS} часов).\n"
                    f"Пожалуйста, создайте новое бронирование.",
                    reply_markup=main_menu()
                )
                return

            # Получаем информацию об экскурсии для описания
            slot = booking.slot
            excursion = slot.excursion if slot else None

            if not excursion:
                logger.error(f"Не найдена экскурсия для бронирования {booking_id}")
                await callback.message.answer(
                    "Ошибка: информация об экскурсии не найдена.",
                    reply_markup=main_menu()
                )
                return

            # Создаем запись о платеже в статусе pending
            payment = await payment_repo.create_payment(
                booking_id=booking_id,
                amount=booking.total_price,
                payment_method=PaymentMethod.online,
                status=YooKassaStatus.pending
            )
            logger.info(f"Создана запись платежа #{payment.id} для бронирования {booking_id}")

            # Формируем описание для инвойса
            date_str = slot.start_datetime.strftime("%d.%m.%Y в %H:%M")
            description = (
                f"{excursion.name}\n"
                f"{date_str}\n"
                f"Участников: {booking.people_count}"
            )

            # Создаем цену (сумма в рублях * 100 = копейки)
            price = LabeledPrice(
                label=f"Экскурсия {excursion.name}",
                amount=booking.total_price * 100
            )

            # Формируем уникальный payload для связи платежа с бронированием
            payload = f"booking:{booking_id}:{payment.id}"

            # Формируем данные для чека (если включено)
            provider_data = build_receipt_data(user, booking, excursion)
            if provider_data:
                logger.info(f"Для платежа #{payment.id} будут отправлены чеки по 54-ФЗ")

            # Отправляем инвойс
            await callback.bot.send_invoice(
                chat_id=callback.message.chat.id,
                title=f"Оплата экскурсии",
                description=description,
                provider_token=PAYMENTS_TOKEN,
                currency="rub",
                prices=[price],
                start_parameter=f"pay_booking_{booking_id}",
                payload=payload,
                need_name=False,
                need_phone=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
                provider_data=provider_data,  # Данные для чека (или None)
                disable_notification=False,
                protect_content=False,
                reply_to_message_id=None,
                reply_markup=None
            )

            logger.info(
                f"Инвойс отправлен для бронирования {booking_id}, "
                f"сумма: {booking.total_price} руб., payload: {payload}"
            )

    except ValueError:
        logger.error(f"Ошибка парсинга booking_id для пользователя {user_telegram_id}")
        await callback.message.answer(
            "Ошибка: некорректный идентификатор бронирования"
        )
    except TelegramBadRequest as e:
        logger.error(f"Ошибка Telegram при отправке инвойса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при создании платежа. Попробуйте позже.",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(
            f"Ошибка инициации платежа для пользователя {user_telegram_id}: {e}",
            exc_info=True
        )
        await callback.message.answer(
            "Произошла ошибка при создании платежа. Попробуйте позже.",
            reply_markup=main_menu()
        )


@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_q: PreCheckoutQuery):
    """
    Обработка предварительного запроса на оплату.
    Проверяет, что бронирование всё ещё доступно для оплаты.
    """
    user_id = pre_checkout_q.from_user.id
    payload = pre_checkout_q.invoice_payload
    logger.info(
        f"Pre-checkout запрос: пользователь={user_id}, "
        f"сумма={pre_checkout_q.total_amount // 100} {pre_checkout_q.currency}, "
        f"payload={payload}"
    )

    try:
        # Парсим payload
        if not payload.startswith("booking:"):
            logger.error(f"Неверный формат payload: {payload}")
            await pre_checkout_q.bot.answer_pre_checkout_query(
                pre_checkout_q.id,
                ok=False,
                error_message="Ошибка: неверный формат платежа"
            )
            return

        _, booking_id_str, payment_id_str = payload.split(':')
        booking_id = int(booking_id_str)
        payment_id = int(payment_id_str)

        async with async_session() as session:
            booking_repo = BookingRepository(session)
            payment_repo = PaymentRepository(session)
            user_repo = UserRepository(session)

            # Проверяем бронирование
            booking = await booking_repo.get_by_id(booking_id)
            if not booking:
                logger.warning(f"Бронирование {booking_id} не найдено при pre-checkout")
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Бронирование не найдено"
                )
                return

            # Проверяем, что платит тот же пользователь
            user = await user_repo.get_by_telegram_id(user_id)
            if not user or booking.adult_user_id != user.id:
                logger.warning(
                    f"Пользователь {user_id} пытается оплатить чужое бронирование {booking_id}"
                )
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="У вас нет прав на оплату этого бронирования"
                )
                return

            # Проверяем статус брони
            if booking.booking_status != BookingStatus.active:
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Бронирование уже неактивно"
                )
                return

            # Проверяем, не оплачено ли уже
            if booking.payment_status == PaymentStatus.paid:
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Бронирование уже оплачено"
                )
                return

            # Проверяем, что сумма совпадает
            expected_amount = booking.total_price * 100
            if pre_checkout_q.total_amount != expected_amount:
                logger.error(
                    f"Несоответствие суммы: ожидалось {expected_amount}, получено {pre_checkout_q.total_amount}"
                )
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Ошибка: неверная сумма платежа"
                )
                return

            # Проверяем запись платежа
            payment = await payment_repo.get_by_id(payment_id)
            if not payment or payment.booking_id != booking_id:
                logger.error(f"Запись платежа {payment_id} не найдена или не соответствует бронированию")
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Ошибка: платеж не найден"
                )
                return

            # Проверяем статус платежа
            if payment.status != YooKassaStatus.pending:
                logger.error(f"Платеж {payment_id} имеет неверный статус: {payment.status}")
                await pre_checkout_q.bot.answer_pre_checkout_query(
                    pre_checkout_q.id,
                    ok=False,
                    error_message="Ошибка: неверный статус платежа"
                )
                return

            # Если все проверки пройдены, подтверждаем платеж
            await pre_checkout_q.bot.answer_pre_checkout_query(
                pre_checkout_q.id,
                ok=True
            )
            logger.info(f"Pre-checkout запрос подтвержден для бронирования {booking_id}")

    except ValueError as e:
        logger.error(f"Ошибка парсинга payload {payload}: {e}")
        await pre_checkout_q.bot.answer_pre_checkout_query(
            pre_checkout_q.id,
            ok=False,
            error_message="Ошибка обработки платежа"
        )
    except Exception as e:
        logger.error(f"Ошибка обработки pre-checkout запроса: {e}", exc_info=True)
        try:
            await pre_checkout_q.bot.answer_pre_checkout_query(
                pre_checkout_q.id,
                ok=False,
                error_message="Произошла ошибка при обработке платежа"
            )
        except Exception as inner_e:
            logger.error(f"Ошибка при отправке отказа pre-checkout: {inner_e}")


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: Message):
    """
    Обработка успешного платежа.
    Обновляет статус брони и платежа в базе данных.
    """
    user_id = message.from_user.id
    logger.info(f"Успешный платеж от пользователя {user_id}")

    try:
        # Получаем информацию о платеже
        payment_info = message.successful_payment.to_python()
        payload = payment_info.get('invoice_payload', '')

        logger.info("Детали платежа:")
        logger.info(f"  Telegram Payment ID: {payment_info.get('telegram_payment_charge_id')}")
        logger.info(f"  Сумма: {payment_info.get('total_amount') // 100} {payment_info.get('currency')}")
        logger.info(f"  Провайдер Payment ID: {payment_info.get('provider_payment_charge_id')}")
        logger.info(f"  Payload: {payload}")

        # Парсим payload
        if not payload.startswith("booking:"):
            logger.error(f"Неверный формат payload в успешном платеже: {payload}")
            await message.answer(
                "Платеж прошел успешно, но произошла ошибка при обработке.\n"
                "Пожалуйста, свяжитесь с администратором и сообщите код ошибки: PAYLOAD_INVALID",
                reply_markup=main_menu()
            )
            return

        _, booking_id_str, payment_id_str = payload.split(':')
        booking_id = int(booking_id_str)
        payment_id = int(payment_id_str)

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_repo = BookingRepository(uow.session)
                payment_repo = PaymentRepository(uow.session)

                # Получаем запись платежа
                payment = await payment_repo.get_by_id(payment_id)
                if not payment:
                    logger.error(f"Запись платежа {payment_id} не найдена")
                    await message.answer(
                        "Платеж прошел успешно, но запись о платеже не найдена.\n"
                        "Пожалуйста, свяжитесь с администратором.",
                        reply_markup=main_menu()
                    )
                    return

                # Проверяем, что платеж еще в статусе pending
                if payment.status != YooKassaStatus.pending:
                    logger.warning(f"Платеж {payment_id} уже обработан (статус: {payment.status})")
                    await message.answer(
                        "Платеж уже был обработан ранее.",
                        reply_markup=booking_detail_keyboard(booking_id, show_pay=False)
                    )
                    return

                # Обновляем статус платежа
                await payment_repo.update(
                    payment_id,
                    status=YooKassaStatus.succeeded,
                    yookassa_payment_id=payment_info.get('provider_payment_charge_id')
                )
                logger.info(f"Платеж {payment_id} обновлен: статус succeeded")

                # Обновляем статус бронирования
                await booking_repo.update(
                    booking_id,
                    payment_status=PaymentStatus.paid
                )
                logger.info(f"Бронирование {booking_id} обновлено: статус paid")

            # Отправляем подтверждение пользователю
            amount_rub = payment_info.get('total_amount') // 100
            currency = payment_info.get('currency')

            success_text = (
                f"Оплата прошла успешно!\n\n"
                f"Сумма: {amount_rub} {currency}\n"
                f"Бронирование #{booking_id} подтверждено.\n\n"
                f"Вы можете посмотреть детали в разделе 'Мои бронирования'."
            )

            await message.answer(
                success_text,
                reply_markup=booking_detail_keyboard(booking_id, show_pay=False)
            )

            logger.info(f"Подтверждение оплаты отправлено пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка обработки успешного платежа: {e}", exc_info=True)
        try:
            await message.answer(
                "Платеж прошел успешно, но произошла ошибка при обновлении статуса.\n"
                "Пожалуйста, свяжитесь с администратором.",
                reply_markup=main_menu()
            )
        except Exception as inner_e:
            logger.error(f"Не удалось уведомить пользователя об ошибке: {inner_e}")


@router.message(F.successful_payment.is_(None) & F.content_type == 'invoice')
async def payment_error_handler(message: Message):
    """
    Обработка ошибок или отмены платежа пользователем.
    """
    user_id = message.from_user.id
    logger.warning(f"Проблема с платежом у пользователя {user_id}")

    try:
        # Здесь можно добавить логику поиска последнего pending платежа
        # и его отмены, если потребуется

        await message.answer(
            "Платеж не прошел или был отменен.\n\n"
            "Вы можете попробовать снова в разделе 'Мои бронирования'.",
            reply_markup=main_menu()
        )
        logger.debug(f"Сообщение об ошибке платежа отправлено пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения об ошибке платежа: {e}")


@router.callback_query(F.data.startswith('payment_cancel:'))
async def cancel_payment_handler(callback: CallbackQuery):
    """
    Обработка отмены платежа пользователем.
    """
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} отменил платеж")

    try:
        # Парсим ID платежа
        payment_id = int(callback.data.split(':')[1])

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                payment_repo = PaymentRepository(uow.session)

                # Получаем платеж
                payment = await payment_repo.get_by_id(payment_id)
                if not payment:
                    logger.error(f"Платеж {payment_id} не найден")
                    await callback.answer("Платеж не найден", show_alert=True)
                    return

                # Обновляем статус платежа на canceled
                await payment_repo.update(
                    payment_id,
                    status=YooKassaStatus.canceled
                )
                logger.info(f"Платеж {payment_id} отменен пользователем")

        await callback.answer("Платеж отменен")
        await callback.message.edit_text(
            "Платеж отменен. Вы можете оплатить позже в разделе 'Мои бронирования'.",
            reply_markup=booking_detail_keyboard(payment.booking_id, show_pay=True)
        )

    except ValueError:
        logger.error(f"Ошибка парсинга payment_id для пользователя {user_id}")
        await callback.answer("Ошибка: некорректный идентификатор платежа", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка отмены платежа: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)
import os

from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, ContentType
from dotenv import load_dotenv

import app.user_panel.keyboards as kb
from app.utils.logging_config import get_logger

router = Router(name="payment")

logger = get_logger(__name__)

PRICE = LabeledPrice(label="Подписка на 1 месяц", amount=500*100)
load_dotenv()
pay_token = os.getenv('PAYMENTS_TOKEN')

# https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing#test-bank-card-data тестовые карты
# https://yookassa.ru/my/payments Основная страница
# https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram Инструкция для разработчика

@router.message(F.text == 'Тест оплаты')
async def test_buy(message: Message):
    """Тестовая оплата - отправка инвойса"""
    logger.info(f"Пользователь {message.from_user.id} начал тестовую оплату")

    try:
        if not pay_token:
            logger.error("PAYMENTS_TOKEN не установлен в переменных окружения")
            await message.answer("Ошибка: платежный токен не настроен. Обратитесь к администратору.")
            return

        logger.debug(f"Создание инвойса для пользователя {message.from_user.id}")

        await message.bot.send_invoice(
            message.chat.id,
            title="Часовая экскурсия по Ангаре",
            description="Один час покататься по Ангаре на лодке",
            provider_token=pay_token,
            currency="rub",
            photo_url="https://30.img.avito.st/image/1/1.UMv31baD_CKZfRwo24Rzsp13_iRJfiYro37-IE9o_ChjesboQHY.AdaQSqv1BE_1ZOcNm7PnNYY4yHqXBwWwMfAyNW06wDk?cqp=2.eQ7GyW4UBJx8BvWWQQ-RFjPk788J3t_horXcMcYcMY7U59sECGqeA6iJLtVrer-5mlLnIfWeR8XAC34B8vse-6Bno_Y4nZlfvwg=",
            photo_width=748,
            photo_height=561,
            is_flexible=False,
            prices=[PRICE],
            start_parameter="one-hour-Angara",
            payload="test-invoice-payload"
        )

        logger.info(f"Инвойс успешно отправлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка отправки инвойса пользователю {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при создании платежа. Попробуйте позже.", reply_markup=kb.main)


@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    """Обработка предварительного запроса на оплату"""
    logger.info(
        f"Pre-checkout запрос: пользователь={pre_checkout_q.from_user.id}, "
        f"сумма={pre_checkout_q.total_amount // 100} {pre_checkout_q.currency}, "
        f"payload={pre_checkout_q.invoice_payload}"
    )

    try:
        # Здесь можно добавить дополнительную проверку платежа
        # Например, проверить доступность товара, валидность пользователя и т.д.

        logger.debug(f"Подтверждение pre-checkout для пользователя {pre_checkout_q.from_user.id}")

        await pre_checkout_q.bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

        logger.info(f"Pre-checkout запрос от пользователя {pre_checkout_q.from_user.id} подтвержден")

    except Exception as e:
        logger.error(f"Ошибка обработки pre-checkout запроса {pre_checkout_q.id}: {e}", exc_info=True)

        try:
            # Отвечаем отказом в случае ошибки
            await pre_checkout_q.bot.answer_pre_checkout_query(
                pre_checkout_q.id,
                ok=False,
                error_message="Произошла ошибка при обработке платежа"
            )
            logger.warning(f"Pre-checkout запрос {pre_checkout_q.id} отклонен из-за ошибки")
        except Exception as inner_e:
            logger.error(f"Ошибка при отправке отказа pre-checkout: {inner_e}")


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    """Обработка успешного платежа"""
    logger.info(f"УСПЕШНЫЙ ПЛАТЕЖ от пользователя {message.from_user.id}")

    try:
        payment_info = message.successful_payment.to_python()

        # Логируем детали платежа
        logger.info("Детали платежа:")
        logger.info(f"  Telegram Payment ID: {payment_info.get('telegram_payment_charge_id')}")
        logger.info(f"  Сумма: {payment_info.get('total_amount') // 100} {payment_info.get('currency')}")
        logger.info(f"  Провайдер Payment ID: {payment_info.get('provider_payment_charge_id')}")
        logger.info(f"  Invoice Payload: {payment_info.get('invoice_payload')}")

        # Можно также вывести в консоль для отладки (по желанию)
        print("SUCCESSFUL PAYMENT:")
        for k, v in payment_info.items():
            print(f"{k} = {v}")
            logger.debug(f"Платеж - {k}: {v}")

        # Отправляем подтверждение пользователю
        amount_rub = message.successful_payment.total_amount // 100
        currency = message.successful_payment.currency

        await message.bot.send_message(
            message.chat.id,
            f"✅ Платеж на сумму {amount_rub} {currency} прошел успешно!"
        )
        logger.info(f"Подтверждение платежа отправлено пользователю {message.from_user.id}")

        # Здесь должна быть логика регистрации на экскурсию
        # Пока просто отправляем сообщение
        await message.bot.send_message(
            message.chat.id,
            f"Вы успешно зарегистрированы на часовую поездку по Ангаре!",
            reply_markup=kb.main
        )
        logger.info(f"Пользователь {message.from_user.id} зарегистрирован на экскурсию после оплаты")

        # TODO: Добавить запись в базу данных о бронировании
        # TODO: Отправить уведомление администратору
        # TODO: Обновить статус пользователя

    except Exception as e:
        logger.error(f"Ошибка обработки успешного платежа от пользователя {message.from_user.id}: {e}", exc_info=True)

        try:
            # Пытаемся хотя бы уведомить пользователя об ошибке
            await message.answer(
                "✅ Платеж прошел успешно, но произошла ошибка при обработке. "
                "Пожалуйста, свяжитесь с администратором.",
                reply_markup=kb.main
            )
        except Exception as inner_e:
            logger.error(f"Не удалось уведомить пользователя об ошибке: {inner_e}")


@router.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_data(message: Message):
    """Обработка данных от веб-приложения (например, для платежей через виджет)"""
    logger.info(f"Данные веб-приложения от пользователя {message.from_user.id}")

    try:
        web_app_data = message.web_app_data
        logger.debug(f"WebApp data: {web_app_data.data}")

        # Здесь можно обработать данные от веб-приложения
        # Например, данные о выбранной экскурсии, количестве людей и т.д.

        await message.answer(
            "Данные от веб-приложения получены. Функция в разработке.",
            reply_markup=kb.main
        )

    except Exception as e:
        logger.error(f"Ошибка обработки данных веб-приложения: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке данных. Попробуйте позже.",
            reply_markup=kb.main
        )


# Можно добавить обработку ошибок платежей
@router.message(F.successful_payment.is_(None) & F.content_type == 'invoice')
async def payment_error(message: Message):
    """Обработка ошибок платежей"""
    logger.warning(f"Проблема с платежом у пользователя {message.from_user.id}")

    try:
        await message.answer(
            "Произошла ошибка при обработке платежа. "
            "Пожалуйста, попробуйте еще раз или свяжитесь с администратором.",
            reply_markup=kb.main
        )
        logger.debug(f"Сообщение об ошибке платежа отправлено пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения об ошибке платежа: {e}")


# Обработка других платежных событий (если нужно)
async def handle_payment_status_update(update: dict):
    """Обработка обновлений статуса платежа от платежного провайдера"""
    # Этот метод может быть вызван из вебхука или другой асинхронной задачи
    logger.info(f"Обновление статуса платежа: {update}")

    try:
        # TODO: Реализовать обработку обновлений статуса от YooKassa
        # Например, обработку уведомлений о возвратах, ошибках и т.д.

        payment_id = update.get('object', {}).get('id')
        status = update.get('object', {}).get('status')

        if payment_id and status:
            logger.info(f"Платеж {payment_id} обновил статус на: {status}")

            # Здесь можно обновить статус в базе данных
            # отправить уведомления и т.д.

    except Exception as e:
        logger.error(f"Ошибка обработки обновления статуса платежа: {e}", exc_info=True)
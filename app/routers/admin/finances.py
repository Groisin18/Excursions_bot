
import os
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import PaymentRepository, BookingRepository
from app.database.models import PaymentStatus, YooKassaStatus
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.admin_panel.keyboards_adm import (
    finances_submenu, refunds_admin_menu, finances_summary_menu
)
from app.routers.admin.refunds import refunds_menu
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_payment")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== ФИНАНСЫ =====

@router.message(F.text == "Сегодняшние платежи")
async def show_online_payments(message: Message):
    """Показать онлайн-оплаты"""
    logger.info(f"Администратор {message.from_user.id} запросил онлайн-оплаты")

    try:
        async with async_session() as session:
            payment_repo = PaymentRepository(session)
            payments = await payment_repo.get_today_online_payments()

            if not payments:
                logger.debug("Онлайн-оплат за сегодня не найдено")
                await message.answer("Онлайн-оплат за сегодня нет")
                return

            logger.info(f"Найдено онлайн-платежей: {len(payments)}")
            response = "Онлайн-оплаты за сегодня:\n\n"
            total_amount = 0

            for payment in payments:
                status = "Успешно" if payment.status == YooKassaStatus.succeeded else "Ожидание"
                client_name = payment.booking.adult_user.full_name if payment.booking.adult_user else "Неизвестный клиент"
                response += (
                    f"Клиент: {client_name}\n"
                    f"Сумма: {payment.amount} руб.\n"
                    f"Статус: {status}\n"
                    f"---\n"
                )
                if payment.status == YooKassaStatus.succeeded:
                    total_amount += payment.amount

            response += f"\nИтого: {total_amount} руб."
            logger.debug(f"Общая сумма онлайн-платежей за сегодня: {total_amount} руб.")

            await message.answer(response)
            logger.debug(f"Онлайн-оплаты отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения онлайн-платежей: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка платежей", reply_markup=finances_submenu())


@router.message(F.text == "Сводка и текущие платежи")
async def finances_summary(message: Message):
    """Сводка по финансам и текущие платежи"""
    logger.info(f"Администратор {message.from_user.id} запросил финансовую сводку")

    try:
        text = (
            "Сводка по финансам и текущие платежи\n\n"
            "Выберите нужный раздел:"
        )
        await message.answer(text, reply_markup=finances_summary_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=finances_submenu())


@router.message(F.text == "Возвраты и проблемные операции")
async def finances_refunds(message: Message):
    """
    Возвраты и проблемные операции.
    Переход в меню управления возвратами.
    """
    logger.info(f"Администратор {message.from_user.id} запросил управление возвратами")

    try:
        text = (
            "Управление возвратами\n\n"
            "Здесь можно просмотреть и обработать возвраты, "
            "которые не удалось выполнить автоматически, "
            "а также выполнить возврат по любому оплаченному бронированию."
        )
        await message.answer(text, reply_markup=refunds_admin_menu())

    except Exception as e:
        logger.error(f"Ошибка при открытии меню возвратов: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при открытии раздела возвратов.\n"
            "Пожалуйста, попробуйте позже.",
            reply_markup=finances_submenu()
        )


@router.message(F.text == "ЮКасса: подключение и магазин")
async def yookassa_connection_info(message: Message):
    """Информация о подключении к Юкассе и магазине"""
    logger.info(f"Администратор {message.from_user.id} запросил информацию о подключении к Юкассе")

    try:
        shop_id = os.getenv('YOOKASSA_SHOP_ID', 'не задан')
        payments_token = os.getenv('PAYMENTS_TOKEN', '')

        if payments_token and payments_token != 'скрыто' and len(payments_token) > 10:
            connection_status = "Подключено"
        else:
            connection_status = "Не подключено или токен не настроен"

        text = (
            f"Информация о подключении к ЮKassa\n\n"
            f"Shop ID: {shop_id}\n"
            f"Статус: {connection_status}\n\n"
            f"Для настройки интеграции проверьте переменные окружения:\n"
            f"- YOOKASSA_SHOP_ID\n"
            f"- PAYMENTS_TOKEN"
        )

        await message.answer(text, reply_markup=finances_submenu())

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=finances_submenu())


@router.message(F.text == "Статистика платежей")
async def yookassa_payments_stats(message: Message):
    """Статистика платежей через Юкассу"""
    logger.info(f"Администратор {message.from_user.id} запросил статистику платежей Юкассы")

    try:
        current_date = datetime.now()

        # Сегодня
        today_start = datetime(current_date.year, current_date.month, current_date.day)
        today_end = today_start + timedelta(days=1) - timedelta(seconds=1)

        # Текущий месяц
        month_start = datetime(current_date.year, current_date.month, 1)
        next_month = current_date.replace(day=28) + timedelta(days=4)
        month_end = datetime(next_month.year, next_month.month, 1) - timedelta(seconds=1)

        # Прошлый месяц
        if current_date.month == 1:
            prev_month_start = datetime(current_date.year - 1, 12, 1)
            prev_month_end = datetime(current_date.year - 1, 12, 31, 23, 59, 59)
        else:
            prev_month_start = datetime(current_date.year, current_date.month - 1, 1)
            prev_month_end = datetime(current_date.year, current_date.month, 1) - timedelta(seconds=1)

        async with async_session() as session:
            payment_repo = PaymentRepository(session)

            today_stats = await payment_repo.get_successful_payments_stats(today_start, today_end)
            month_stats = await payment_repo.get_successful_payments_stats(month_start, month_end)
            prev_month_stats = await payment_repo.get_successful_payments_stats(prev_month_start, prev_month_end)

        text = (
            f"Статистика успешных платежей через ЮKassa\n\n"
            f"Сегодня:\n"
            f"Сумма: {today_stats['total_amount']} руб.\n"
            f"Количество платежей: {today_stats['count']}\n\n"
            f"Текущий месяц ({month_start.strftime('%B %Y')}):\n"
            f"Сумма: {month_stats['total_amount']} руб.\n"
            f"Количество платежей: {month_stats['count']}\n\n"
            f"Прошлый месяц ({prev_month_start.strftime('%B %Y')}):\n"
            f"Сумма: {prev_month_stats['total_amount']} руб.\n"
            f"Количество платежей: {prev_month_stats['count']}"
        )

        await message.answer(text, reply_markup=finances_summary_menu())

    except Exception as e:
        logger.error(f"Ошибка при получении статистики платежей: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении статистики", reply_markup=finances_submenu())


@router.callback_query(F.data == "finances_refunds")
async def finances_refunds_callback(callback: CallbackQuery):
    """Переход в меню управления возвратами из раздела финансов (callback)"""
    await callback.answer()
    await refunds_menu(callback)


@router.message(F.text == "В меню финансов")
async def back_from_yookassa(message: Message):
    """Возврат в меню финансов"""
    await message.answer("Выберите раздел:", reply_markup=finances_submenu())


@router.callback_query(F.data.startswith("paid:"))
async def mark_paid(callback: CallbackQuery):
    """Отметить оплату"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} отмечает оплату для бронирования {booking_id}")

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_repo = BookingRepository(uow.session)
                success = await booking_repo.update_status(
                    booking_id,
                    payment_status=PaymentStatus.paid
                )

                if success:
                    logger.info(f"Бронирование {booking_id} отмечено как оплаченное")
                    await callback.message.edit_text("Оплата подтверждена")
                else:
                    logger.warning(f"Не удалось отметить оплату для бронирования {booking_id}")
                    await callback.message.edit_text("Ошибка при обновлении статуса", reply_markup=finances_submenu())

    except Exception as e:
        logger.error(f"Ошибка при отметке оплаты для бронирования {booking_id}: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка", reply_markup=finances_submenu())

    await callback.answer()


@router.message(F.text == "Платежи в статусе pending")
async def pending_payments(message: Message):
    """Платежи в статусе pending (зависшие)"""
    logger.info(f"Администратор {message.from_user.id} запросил платежи в статусе pending")

    try:
        from app.database.models import YooKassaStatus

        async with async_session() as session:
            payment_repo = PaymentRepository(session)
            pending_payments = await payment_repo.get_payments_by_status(YooKassaStatus.pending)

        if not pending_payments:
            await message.answer(
                "Нет платежей в статусе pending",
                reply_markup=finances_summary_menu()
            )
            return

        text = f"Платежи в статусе pending (всего: {len(pending_payments)}):\n\n"

        for payment in pending_payments[:20]:  # Ограничиваем 20 платежами
            created_at = payment.created_at.strftime('%d.%m.%Y %H:%M') if payment.created_at else "дата неизвестна"
            text += (
                f"ID: {payment.id}\n"
                f"Бронирование: {payment.booking_id}\n"
                f"Сумма: {payment.amount} руб.\n"
                f"Создан: {created_at}\n"
                f"---\n"
            )

        if len(pending_payments) > 20:
            text += f"\nПоказано 20 из {len(pending_payments)} платежей"

        await message.answer(text, reply_markup=finances_summary_menu())

    except Exception as e:
        logger.error(f"Ошибка при получении pending платежей: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка платежей", reply_markup=finances_summary_menu())


@router.callback_query(F.data == "finances_menu")
async def finances_menu_callback(callback: CallbackQuery):
    """Возврат в меню финансов из callback"""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "Финансовый раздел. Выберите нужный пункт:",
        reply_markup=finances_submenu()
    )
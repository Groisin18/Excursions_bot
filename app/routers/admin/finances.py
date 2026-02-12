from aiogram import F, Router
from aiogram.types import Message, CallbackQuery

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import PaymentRepository, BookingRepository
from app.database.models import PaymentStatus, YooKassaStatus
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.admin_panel.keyboards_adm import admin_main_menu, finances_submenu
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_payment")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== ФИНАНСЫ =====

@router.message(F.text == "Онлайн-оплаты")
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
                response += (
                    f"Клиент: {payment.booking.client.full_name}\n"
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
        await message.answer("Функция 'Сводка и текущие платежи' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Аналитика и отчеты")
async def finances_analytics(message: Message):
    """Финансовая аналитика и отчеты"""
    logger.info(f"Администратор {message.from_user.id} запросил финансовую аналитику")

    try:
        await message.answer("Функция 'Аналитика и отчеты' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Возвраты и проблемные операции")
async def finances_refunds(message: Message):
    """Возвраты и проблемные операции"""
    logger.info(f"Администратор {message.from_user.id} запросил информацию о возвратах")

    try:
        await message.answer("Функция 'Возвраты и проблемные операции' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Интеграция с Ю-кассой")
async def yookassa_integration(message: Message):
    """Интеграция с Ю-кассой"""
    logger.info(f"Администратор {message.from_user.id} запросил информацию по интеграции с Ю-кассой")

    try:
        await message.answer("Функция 'Интеграция с Ю-кассой' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)




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
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.requests import DatabaseManager
from app.database.models import (
    Booking, ExcursionSlot,
    BookingStatus, PaymentStatus
)
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_bookings")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())



# ===== УПРАВЛЕНИЕ ЗАПИСЯМИ =====

@router.message(F.text == "Активные записи")
async def show_active_bookings(message: Message):
    """Показать все активные записи"""
    logger.info(f"Администратор {message.from_user.id} запросил активные записи")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Получаем все активные бронирования
            result = await session.execute(
                select(Booking)
                .options(selectinload(Booking.slot).selectinload(ExcursionSlot.excursion))
                .options(selectinload(Booking.slot).selectinload(ExcursionSlot.captain))
                .options(selectinload(Booking.adult_user))  # Изменено с client на adult_user
                .where(Booking.booking_status == BookingStatus.active)
                .order_by(Booking.created_at.desc())
            )
            bookings = result.scalars().all()

            if not bookings:
                logger.debug("Активных записей не найдено")
                await message.answer("Активных записей нет")
                return

            logger.info(f"Найдено активных записей: {len(bookings)}")
            response = "Активные записи:\n\n"
            for booking in bookings[:10]:  # Ограничиваем вывод
                response += (
                    f"ID: {booking.id}\n"
                    f"Клиент: {booking.adult_user.full_name}\n"
                    f"Экскурсия: {booking.slot.excursion.name}\n"
                    f"Время: {booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Капитан: {booking.slot.captain.full_name}\n"
                    f"Людей: {booking.people_count}\n"
                    f"Оплата: {'Оплачено' if booking.payment_status == PaymentStatus.paid else 'Не оплачено'}\n"
                    f"---\n"
                )

            if len(bookings) > 10:
                response += f"\n... и еще {len(bookings) - 10} записей"

            await message.answer(response)
            logger.debug(f"Активные записи отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения активных записей: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка записей")


@router.message(F.text == "Неоплаченные")
async def show_unpaid_bookings(message: Message):
    """Показать неоплаченные записи"""
    logger.info(f"Администратор {message.from_user.id} запросил неоплаченные бронирования")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            result = await session.execute(
                select(Booking)
                .options(selectinload(Booking.adult_user))
                .options(selectinload(Booking.slot).selectinload(ExcursionSlot.excursion))
                .where(Booking.payment_status != PaymentStatus.paid)
                .where(Booking.booking_status == BookingStatus.active)
            )
            bookings = result.scalars().all()

            if not bookings:
                logger.debug("Неоплаченных записей не найдено")
                await message.answer("Неоплаченных записей нет")
                return

            logger.info(f"Найдено неоплаченных записей: {len(bookings)}")
            response = "Неоплаченные записи:\n\n"
            for booking in bookings:
                response += (
                    f"ID: {booking.id}\n"
                    f"Клиент: {booking.adult_user.full_name} ({booking.adult_user.phone_number})\n"
                    f"Экскурсия: {booking.slot.excursion.name}\n"
                    f"Сумма: {booking.total_price} руб.\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список неоплаченных отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения неоплаченных записей: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка неоплаченных записей")


@router.message(F.text == "Создать запись")
async def create_booking(message: Message):
    """Создание новой записи"""
    logger.info(f"Администратор {message.from_user.id} хочет создать запись")

    try:
        await message.answer("Функция 'Создать запись' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Изменить запись")
async def edit_booking(message: Message):
    """Изменение существующей записи"""
    logger.info(f"Администратор {message.from_user.id} хочет изменить запись")

    try:
        await message.answer("Функция 'Изменить запись' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Отменить запись")
async def cancel_booking(message: Message):
    """Отмена существующей записи"""
    logger.info(f"Администратор {message.from_user.id} хочет отменить запись")

    try:
        await message.answer("Функция 'Отменить запись' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Перенести запись")
async def reschedule_booking(message: Message):
    """Перенос существующей записи"""
    logger.info(f"Администратор {message.from_user.id} хочет перенести запись")

    try:
        await message.answer("Функция 'Перенести запись' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Отметить прибытие")
async def mark_arrival_booking(message: Message):
    """Отметить прибытие клиента"""
    logger.info(f"Администратор {message.from_user.id} хочет отметить прибытие")

    try:
        await message.answer("Функция 'Отметить прибытие' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)



@router.callback_query(F.data.startswith("edit_booking:"))
async def edit_booking_callback(callback: CallbackQuery):
    """Редактирование бронирования (inline)"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет редактировать бронирование {booking_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Редактирование бронирования #{booking_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking_callback(callback: CallbackQuery):
    """Отмена бронирования (inline)"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет отменить бронирование {booking_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Отмена бронирования #{booking_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.callback_query(F.data.startswith("reschedule:"))
async def reschedule_booking_callback(callback: CallbackQuery):
    """Перенос бронирования (inline)"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} хочет перенести бронирование {booking_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Перенос бронирования #{booking_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.callback_query(F.data.startswith("booking_info:"))
async def booking_info_callback(callback: CallbackQuery):
    """Информация о бронировании (inline)"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} запросил информацию о бронировании {booking_id}")

    try:
        await callback.answer("Функция в разработке")
        await callback.message.edit_text(f"Информация о бронировании #{booking_id} в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

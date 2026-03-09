from datetime import datetime

from .bot_instance import get_bot_instance

from app.services.redis import redis_client
from app.database.unit_of_work import UnitOfWork
from app.database.managers import BookingManager, SlotManager
from app.database.models import SlotStatus
from app.database.session import async_session
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def auto_cancel_unpaid_bookings():
    """Автоотмена неоплаченных бронирований"""
    logger.info("Запуск автоотмены неоплаченных бронирований")

    lock_key = "scheduler:lock:cancel_unpaid"
    token = await redis_client.acquire_lock(lock_key, timeout=300)

    if not token:
        logger.warning("Не удалось получить блокировку для автоотмены")
        return

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            try:
                booking_manager = BookingManager(session)
                bookings = await booking_manager.get_expired_unpaid_bookings()

                if not bookings:
                    logger.debug("Нет просроченных неоплаченных бронирований")
                    return

                logger.info(f"Найдено бронирований для отмены: {len(bookings)}")

                for booking in bookings:
                    success, message, refund_data = await booking_manager.cancel_booking(
                        booking_id=booking.id,
                        auto_refund=False
                    )

                    if success:
                        logger.info(f"Отменено бронирование #{booking.id}")
                        _bot_instance = get_bot_instance()
                        if booking.adult_user.telegram_id and _bot_instance:
                            try:
                                await _bot_instance.send_message(
                                    chat_id=booking.adult_user.telegram_id,
                                    text=(
                                        f"Бронирование отменено\n\n"
                                        f"Ваше бронирование на экскурсию "
                                        f"{booking.slot.excursion.name} "
                                        f"{booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')} "
                                        f"было автоматически отменено, так как не было оплачено "
                                        f"в течение 24 часов."
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки уведомления: {e}")
                        else:
                            logger.info(f"Ошибка отправки уведомления:"
                                        f"Клиент с номером телефона {booking.adult_user.phone_number} "
                                        f"не имеет TelegramID в базе данных")
                    else:
                        logger.error(f"Не удалось отменить бронирование #{booking.id}: {message}")

                logger.info(f"Автоотмена неоплаченных бронирований завершена, обработано: {len(bookings)}")

            except Exception as e:
                logger.error(f"Ошибка при автоотмене: {e}", exc_info=True)
                raise
            finally:
                await redis_client.release_lock(lock_key, token)

async def send_payment_reminder():
    """Напоминание об оплате за час до дедлайна"""
    logger.info("Запуск напоминаний об оплате")

    lock_key = "scheduler:lock:payment_reminder"
    token = await redis_client.acquire_lock(lock_key, timeout=300)

    if not token:
        logger.warning("Не удалось получить блокировку для напоминаний об оплате")
        return

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            try:
                booking_manager = BookingManager(session)
                bookings_with_deadline = await booking_manager.get_bookings_for_payment_reminder()

                if not bookings_with_deadline:
                    logger.debug("Нет бронирований для напоминания об оплате")
                    return

                logger.info(f"Найдено бронирований для напоминания: {len(bookings_with_deadline)}")

                for booking, deadline in bookings_with_deadline:
                    # Проверяем, не отправляли ли уже напоминание для этого бронирования
                    reminder_key = f"reminder:payment:{booking.id}"
                    already_sent = await redis_client.client.get(reminder_key)

                    if already_sent:
                        logger.debug(f"Напоминание об оплате #{booking.id} уже отправлено ранее")
                        continue
                    _bot_instance = get_bot_instance()
                    if booking.adult_user.telegram_id and _bot_instance:
                        try:
                            minutes_until_deadline = int((deadline - datetime.now()).total_seconds() / 60)

                            await _bot_instance.send_message(
                                chat_id=booking.adult_user.telegram_id,
                                text=(
                                    f"Напоминание об оплате\n\n"
                                    f"У вас осталось {minutes_until_deadline} минут на оплату экскурсии "
                                    f"{booking.slot.excursion.name} "
                                    f"{booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')}.\n\n"
                                    f"Если не оплатить вовремя, бронь будет автоматически отменена."
                                )
                            )

                            # Сохраняем флаг отправки на 24 часа
                            await redis_client.client.setex(reminder_key, 86400, "1")
                            logger.info(f"Напоминание об оплате отправлено #{booking.id}")

                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания: {e}")

            except Exception as e:
                logger.error(f"Ошибка при отправке напоминаний об оплате: {e}", exc_info=True)
            finally:
                await redis_client.release_lock(lock_key, token)


async def send_excursion_reminder():
    """Напоминание об экскурсии за 24 часа"""
    logger.info("Запуск напоминаний об экскурсиях")

    lock_key = "scheduler:lock:excursion_reminder"
    token = await redis_client.acquire_lock(lock_key, timeout=300)

    if not token:
        logger.warning("Не удалось получить блокировку для напоминаний об экскурсиях")
        return

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            try:
                booking_manager = BookingManager(session)
                bookings = await booking_manager.get_paid_bookings_for_reminder(hours_before=24)

                if not bookings:
                    logger.debug("Нет бронирований для напоминания об экскурсиях")
                    return

                logger.info(f"Найдено бронирований для напоминания: {len(bookings)}")

                for booking in bookings:
                    # Проверяем, не отправляли ли уже напоминание
                    reminder_key = f"reminder:excursion:{booking.id}"
                    already_sent = await redis_client.client.get(reminder_key)

                    if already_sent:
                        logger.debug(f"Напоминание об экскурсии #{booking.id} уже отправлено ранее")
                        continue

                    _bot_instance = get_bot_instance()
                    if booking.adult_user.telegram_id and _bot_instance:
                        try:
                            excursion_time = booking.slot.start_datetime.strftime('%d.%m.%Y %H:%M')

                            await _bot_instance.send_message(
                                chat_id=booking.adult_user.telegram_id,
                                text=(
                                    f"Напоминание об экскурсии\n\n"
                                    f"Завтра в {excursion_time} у вас запланирована экскурсия "
                                    f"{booking.slot.excursion.name}.\n\n"
                                    f"Не забудьте прийти вовремя!"
                                )
                            )

                            # Сохраняем флаг отправки на 24 часа
                            await redis_client.client.setex(reminder_key, 86400, "1")
                            logger.info(f"Напоминание об экскурсии отправлено #{booking.id}")

                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания: {e}")

            except Exception as e:
                logger.error(f"Ошибка при отправке напоминаний об экскурсиях: {e}", exc_info=True)
            finally:
                await redis_client.release_lock(lock_key, token)


async def auto_complete_excursions():
    """Автозавершение слотов"""
    logger.info("Запуск автозавершения слотов")

    lock_key = "scheduler:lock:auto_complete"
    token = await redis_client.acquire_lock(lock_key, timeout=300)

    if not token:
        logger.warning("Не удалось получить блокировку для автозавершения слотов")
        return

    async with async_session() as session:
        async with UnitOfWork(session) as uow:
            try:
                slot_manager = SlotManager(session)

                # Слоты для перевода в in_progress
                slots_to_start = await slot_manager.get_slots_to_start()
                for slot in slots_to_start:
                    await slot_manager.slot_repo.update_status(slot.id, SlotStatus.in_progress)
                    logger.info(f"Слот #{slot.id} переведен в статус in_progress")

                # Слоты для перевода в completed
                slots_to_complete = await slot_manager.get_slots_to_complete()
                for slot in slots_to_complete:
                    old_status = slot.status
                    await slot_manager.slot_repo.update_status(slot.id, SlotStatus.completed)
                    logger.info(f"Слот #{slot.id} переведен из {old_status} в completed")

                if slots_to_start or slots_to_complete:
                    logger.info(f"Автозавершение слотов выполнено: {len(slots_to_start)} в in_progress, {len(slots_to_complete)} в completed")
                else:
                    logger.debug("Нет слотов для обновления статуса")

            except Exception as e:
                logger.error(f"Ошибка при автозавершении слотов: {e}", exc_info=True)
                raise
            finally:
                await redis_client.release_lock(lock_key, token)
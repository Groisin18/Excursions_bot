from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from sqlalchemy import select

from app.admin_panel.states_adm import AdminStates
from app.admin_panel.keyboards_adm import (
    admin_main_menu, clients_submenu, cancel_button
)
from app.database.requests import DatabaseManager
from app.database.models import (
    engine, async_session, UserRole, User, ClientStatus
)

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_clients")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УПРАВЛЕНИЕ КЛИЕНТАМИ =====

@router.message(F.text == "Поиск клиента")
async def search_client_start(message: Message, state: FSMContext):
    """Начало поиска клиента"""
    logger.info(f"Администратор {message.from_user.id} начал поиск клиента")

    try:
        await message.answer(
            "Введите Фамилию и имя клиента или номер телефона клиента:",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminStates.waiting_for_client_search)
        logger.debug(f"Пользователь {message.from_user.id} перешел в состояние поиска клиента")
    except Exception as e:
        logger.error(f"Ошибка начала поиска клиента: {e}", exc_info=True)


@router.message(AdminStates.waiting_for_client_search)
async def search_client_process(message: Message, state: FSMContext):
    """Обработка поиска клиента"""
    search_query = message.text
    logger.info(f"Администратор {message.from_user.id} ищет клиента по запросу: '{search_query}'")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Поиск по имени или телефону
            result = await session.execute(
                select(User)
                .where(User.role == UserRole.client)
                .where(
                    (User.full_name.ilike(f"%{search_query}%")) |
                    (User.phone_number.ilike(f"%{search_query}%"))
                )
            )
            clients = result.scalars().all()

            if not clients:
                logger.debug(f"Клиенты по запросу '{search_query}' не найдены")
                await message.answer("Клиенты не найдены", reply_markup=clients_submenu())
                await state.clear()
                return

            logger.info(f"Найдено клиентов по запросу '{search_query}': {len(clients)}")
            response = f"Найдено клиентов: {len(clients)}\n\n"
            for client in clients[:5]:  # Ограничиваем вывод
                response += (
                    f"Имя: {client.full_name}\n"
                    f"Телефон: {client.phone_number}\n"
                    f"Telegram ID: {client.telegram_id}\n"
                    f"---\n"
                )

            if len(clients) > 5:
                response += f"\n... и еще {len(clients) - 5} клиентов"

            await message.answer(response, reply_markup=clients_submenu())
            logger.debug(f"Результаты поиска отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка поиска клиента по запросу '{search_query}': {e}", exc_info=True)
        await message.answer("Ошибка при поиске клиента", reply_markup=clients_submenu())

    await state.clear()
    logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")


@router.message(F.text == "Отмена", AdminStates.waiting_for_client_search)
async def cancel_client_search(message: Message, state: FSMContext):
    """Отмена поиска клиента"""
    logger.info(f"Администратор {message.from_user.id} отменил поиск клиента")

    try:
        await state.clear()
        await message.answer(
            "Поиск клиента отменен",
            reply_markup=clients_submenu()
        )
        logger.debug(f"Поиск клиента отменен для пользователя {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отмены поиска клиента: {e}", exc_info=True)
        await message.answer("Ошибка при отмене", reply_markup=admin_main_menu())

@router.message(F.text == "Новые клиенты")
async def show_new_clients(message: Message):
    """Показать новых клиентов"""
    logger.info(f"Администратор {message.from_user.id} запросил новых клиентов")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            week_ago = datetime.now() - timedelta(days=7)
            logger.debug(f"Поиск клиентов зарегистрированных после {week_ago}")

            result = await session.execute(
                select(User)
                .where(User.role == UserRole.client)
                .where(User.created_at >= week_ago)
                .order_by(User.created_at.desc())
            )
            new_clients = result.scalars().all()

            if not new_clients:
                logger.debug("Новых клиентов за последнюю неделю не найдено")
                await message.answer("Новых клиентов за последнюю неделю нет")
                return

            logger.info(f"Найдено новых клиентов: {len(new_clients)}")
            response = "Новые клиенты (последние 7 дней):\n\n"
            for client in new_clients:
                response += (
                    f"Имя: {client.full_name}\n"
                    f"Телефон: {client.phone_number}\n"
                    f"Дата регистрации: {client.created_at.strftime('%d.%m.%Y')}\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Новые клиенты отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения новых клиентов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка клиентов")


@router.message(F.text == "Добавить клиента")
async def add_client(message: Message):
    """Добавление нового клиента"""
    logger.info(f"Администратор {message.from_user.id} хочет добавить клиента")

    try:
        await message.answer("Функция 'Добавить клиента' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Редактировать клиента")
async def edit_client(message: Message):
    """Редактирование данных клиента"""
    logger.info(f"Администратор {message.from_user.id} хочет редактировать клиента")

    try:
        await message.answer("Функция 'Редактировать клиента' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)




@router.callback_query(F.data.startswith("arrived:"))
async def mark_arrived(callback: CallbackQuery):
    """Отметить прибытие клиента"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} отмечает прибытие для бронирования {booking_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_booking_status(
                booking_id,
                client_status=ClientStatus.arrived
            )

            if success:
                logger.info(f"Бронирование {booking_id} отмечено как прибывшее")
                await callback.message.edit_text("Клиент отмечен как прибывший")
            else:
                logger.warning(f"Не удалось отметить прибытие для бронирования {booking_id}")
                await callback.message.edit_text("Ошибка при обновлении статуса")

    except Exception as e:
        logger.error(f"Ошибка при отметке прибытия для бронирования {booking_id}: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")

    await callback.answer()

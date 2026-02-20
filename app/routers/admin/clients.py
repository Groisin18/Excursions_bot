import re
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.admin_panel.states_adm import AdminStates, AdminEditClient
from app.admin_panel.keyboards_adm import (
    clients_submenu, cancel_button, client_actions_keyboard,
    client_list_keyboard, client_role_change_keyboard,
    back_to_client_actions_keyboard, client_virtual_actions_keyboard,
    client_or_child_selection_menu
)
from app.routers.admin.client_redaction import show_client_edit_menu
from app.database.unit_of_work import UnitOfWork
from app.database.managers import UserManager, BookingManager
from app.database.repositories import UserRepository
from app.database.models import UserRole
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_clients")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

async def show_client_details(message_or_callback, client_id: int, session, edit: bool = False):
    """
    Показать детальную информацию о клиенте

    Args:
        message_or_callback: Message или CallbackQuery
        client_id: ID клиента
        session: сессия БД
        edit: True если нужно редактировать существующее сообщение, False если отвечать новым
    """
    user_manager = UserManager(session)
    client = await user_manager.user_repo.get_by_id(client_id)

    if not client:
        text = "Клиент не найден"
        if isinstance(message_or_callback, CallbackQuery):
            if edit:
                await message_or_callback.message.edit_text(text)
            else:
                await message_or_callback.message.answer(text)
        else:
            await message_or_callback.answer(text)
        return

    # Получаем детей, если есть
    children = await user_manager.user_repo.get_children_users(client.id)
    children_info = ""
    if children:
        children_info = "\nДети:\n"
        for child in children:
            child_age = f"{child.age} лет" if child.age else "возраст неизвестен"
            children_info += f"  - {child.full_name} (ID: {child.id}, возраст: {child_age})\n"

    # Определяем тип аккаунта
    account_type = "Виртуальный" if client.is_virtual else "Полноценный"
    if client.telegram_id is None and not client.is_virtual:
        account_type = "Без Telegram"

    # Определяем роль
    role_display = {
        "client": "Клиент",
        "captain": "Капитан",
        "admin": "Администратор"
    }.get(client.role.value, client.role.value)

    response = (
        f"Клиент найден:\n\n"
        f"ID: {client.id}\n"
        f"Имя: {client.full_name}\n"
        f"Телефон: {client.phone_number}\n"
        f"Дата рождения: {client.date_of_birth.strftime('%d.%m.%Y') if client.date_of_birth else 'не указана'}\n"
    )

    if client.age:
        response += f"Возраст: {client.age} лет\n"
    if client.weight:
        response += f"Вес: {client.weight} кг\n"

    response += (
        f"Тип аккаунта: {account_type}\n"
        f"Роль: {role_display}\n"
        f"Telegram ID: {client.telegram_id or 'не привязан'}\n"
        f"Токен: {client.verification_token or 'отсутствует'}\n"
        f"Зарегистрирован: {client.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    )
    response += children_info

    # Выбираем клавиатуру в зависимости от типа аккаунта
    if client.is_virtual:
        reply_markup = client_virtual_actions_keyboard(client.id)
    else:
        reply_markup = client_actions_keyboard(client.id)

    if isinstance(message_or_callback, CallbackQuery):
        if edit:
            await message_or_callback.message.edit_text(
                response,
                reply_markup=reply_markup
            )
        else:
            await message_or_callback.message.answer(
                response,
                reply_markup=reply_markup
            )
            # Удаляем старое сообщение с инлайн-кнопками
            try:
                await message_or_callback.message.delete()
            except:
                pass
    else:
        await message_or_callback.answer(
            response,
            reply_markup=reply_markup
        )

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
        await message.answer("Ошибка начала поиска клиента", reply_markup=clients_submenu())


@router.message(AdminStates.waiting_for_client_search)
async def search_client_process(message: Message, state: FSMContext):
    """Обработка поиска клиента"""
    search_query = message.text
    logger.info(f"Администратор {message.from_user.id} ищет клиента по запросу: '{search_query}'")

    try:
        # Нормализация номера телефона, если запрос похож на номер
        if search_query.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            # Убираем все нецифровые символы для проверки
            digits_only = re.sub(r'\D', '', search_query)

            # Если это номер в формате 8XXXXXXXXXX
            if len(digits_only) == 11 and digits_only[0] == '8':
                normalized = '+7' + digits_only[1:]
                logger.debug(f"Нормализован номер телефона: {search_query} -> {normalized}")
                search_query = normalized
            # Если это номер в формате 7XXXXXXXXXX (без +)
            elif len(digits_only) == 11 and digits_only[0] == '7':
                normalized = '+' + digits_only
                logger.debug(f"Нормализован номер телефона: {search_query} -> {normalized}")
                search_query = normalized
        async with async_session() as session:
            user_manager = UserManager(session)
            users = await user_manager.search_users(search_query, limit=10)

            if not users:
                logger.debug(f"Пользователи по запросу '{search_query}' не найдены")
                await message.answer(
                    "Пользователи не найдены",
                    reply_markup=clients_submenu()
                )
                await state.clear()
                return

            # Отделяем клиентов от остальных
            clients = [u for u in users if u.role.value == "client"]
            non_clients = [u for u in users if u.role.value != "client"]

            # Формируем базовое сообщение
            response_parts = [f"Найдено пользователей: {len(users)}"]

            # Если есть неклиенты, добавляем информацию о них в сообщение
            if non_clients:
                non_clients_info = "\n\nНайдены пользователи с другими ролями:"
                for user in non_clients:
                    role_display = {
                        "captain": "Капитан",
                        "admin": "Администратор"
                    }.get(user.role.value, user.role.value)

                    phone = user.phone_number if user.phone_number else "нет телефона"
                    non_clients_info += f"\n• {user.full_name} ({role_display}) - {phone}"

                response_parts.append(non_clients_info)

            # Если нет клиентов
            if not clients:
                response_parts.append("\nКлиенты с таким запросом не найдены")
                await message.answer(
                    "\n".join(response_parts),
                    reply_markup=clients_submenu()
                )
                await state.clear()
                return

            # Если есть один клиент
            if len(clients) == 1:
                response_parts.append(f"\nНайден 1 клиент")
                await message.answer("\n".join(response_parts))
                await show_client_details(message, clients[0].id, session, edit=False)
                await state.clear()
                return

            # Если несколько клиентов
            if len(clients) > 1:
                response_parts.append(f"\nНайдено клиентов: {len(clients)}")
                await message.answer("\n".join(response_parts))

                # Сохраняем ID найденных клиентов в состояние
                client_ids = [client.id for client in clients]
                await state.update_data(found_clients=client_ids)
                await state.set_state(AdminStates.waiting_for_client_selection)

                # Показываем список только клиентов для выбора
                await message.answer(
                    "Выберите клиента:",
                    reply_markup=client_list_keyboard(clients)  # передаем только клиентов
                )

    except Exception as e:
        logger.error(f"Ошибка поиска по запросу '{search_query}': {e}", exc_info=True)
        await message.answer(
            "Ошибка при поиске",
            reply_markup=clients_submenu()
        )
        await state.clear()


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
        await message.answer("Ошибка при отмене", reply_markup=clients_submenu())
        await state.clear()


@router.callback_query(F.data == "back_to_clients_menu")
async def back_to_clients_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в подменю клиентов"""
    logger.info(f"Администратор {callback.from_user.id} вернулся в меню клиентов")

    await callback.answer()
    await state.clear()

    await callback.message.answer(
        "Меню управления клиентами:",
        reply_markup=clients_submenu()
    )

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass


@router.callback_query(F.data.startswith("edit_client:"))
async def edit_client_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на редактирование клиента"""
    client_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} переходит к редактированию клиента {client_id}")

    await callback.answer()
    await state.clear()

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            client = await user_repo.get_by_id(client_id)

            if not client:
                await callback.message.edit_text("Клиент не найден")
                return

            if client.role == UserRole.admin:
                await callback.message.edit_text(
                    "Нельзя редактировать администратора через этот раздел.\n"
                    "Используйте раздел Настройки -> Управление администраторами.\n\n"
                    "Редактировать детей администратора может только он сам через свой личный кабинет",
                    reply_markup=clients_submenu()
                )
                return

            # Сохраняем ID клиента в состояние
            await state.update_data(client_id=client_id)

            # Получаем детей
            children = await user_repo.get_children_users(client_id)

            if children:
                # Если есть дети, показываем меню выбора: клиент или ребенок
                birth_date = client.date_of_birth.strftime('%d.%m.%Y') if client.date_of_birth else 'не указана'

                await callback.message.edit_text(
                    f"Выбран клиент: {client.full_name}\n"
                    f"Дата рождения: {birth_date}\n"
                    f"Телефон: {client.phone_number}\n\n"
                    f"У клиента есть дети. Кого редактируем?",
                    reply_markup=client_or_child_selection_menu(client, children)
                )
                await state.set_state(AdminEditClient.waiting_for_target_selection)
            else:
                # Если детей нет, сразу показываем меню выбора поля для клиента
                await show_client_edit_menu(callback.message, client_id, "client", state)

    except Exception as e:
        logger.error(f"Ошибка при переходе к редактированию клиента {client_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при переходе к редактированию",
            reply_markup=clients_submenu()
        )
        await state.clear()

@router.message(F.text == "Новые клиенты")
async def show_new_clients(message: Message):
    """Показать новых клиентов"""
    logger.info(f"Администратор {message.from_user.id} запросил новых клиентов")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            new_clients = await user_manager.get_new_clients(days_ago=7)

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
        await message.answer("Ошибка при получении списка клиентов", reply_markup=clients_submenu())


# ===== ОБРАБОТКА ВЫБОРА КЛИЕНТА ИЗ СПИСКА =====

@router.callback_query(F.data.startswith("select_client:"), AdminStates.waiting_for_client_selection)
async def select_client_from_list(callback: CallbackQuery, state: FSMContext):
    """Выбор клиента из списка найденных"""
    client_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            await show_client_details(callback, client_id, session, edit=False)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при показе клиента {client_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при загрузке данных клиента")
        await state.clear()


@router.callback_query(F.data == "new_client_search")
async def new_client_search(callback: CallbackQuery, state: FSMContext):
    """Новый поиск клиента"""
    await callback.answer()
    await state.clear()

    await callback.message.answer(
        "Введите Фамилию и имя клиента или номер телефона:",
        reply_markup=cancel_button()
    )
    await state.set_state(AdminStates.waiting_for_client_search)

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass


@router.callback_query(F.data == "cancel_client_search")
async def cancel_client_search_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена поиска клиента"""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "Поиск клиента отменен",
        reply_markup=clients_submenu()
    )


# ===== ДЕЙСТВИЯ С КЛИЕНТОМ =====

@router.callback_query(F.data.startswith("client_actions:"))
async def back_to_client_actions(callback: CallbackQuery):
    """Возврат к действиям с клиентом"""
    client_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            await show_client_details(callback, client_id, session, edit=True)
    except Exception as e:
        logger.error(f"Ошибка при показе клиента {client_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при загрузке данных клиента")


@router.callback_query(F.data.startswith("change_client_role:"))
async def change_client_role_start(callback: CallbackQuery):
    """Начало изменения роли клиента"""
    client_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            client = await user_manager.user_repo.get_by_id(client_id)

            if not client:
                await callback.message.edit_text("Клиент не найден")
                return

            await callback.message.edit_text(
                f"Выберите новую роль для клиента {client.full_name}:",
                reply_markup=client_role_change_keyboard(client_id, client.role.value)
            )
    except Exception as e:
        logger.error(f"Ошибка при изменении роли клиента {client_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при загрузке данных")


@router.callback_query(F.data.startswith("set_client_role:"))
async def set_client_role(callback: CallbackQuery):
    """Установка новой роли клиенту"""
    _, client_id, new_role = callback.data.split(":")
    client_id = int(client_id)
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(session)
                client = await user_repo.get_by_id(client_id)

                if not client:
                    await callback.message.edit_text("Пользователь не найден")
                    return

                # Обновляем роль
                role_map = {
                    "client": UserRole.client,
                    "captain": UserRole.captain,
                    "admin": UserRole.admin
                }

                await user_repo.update(client_id, role=role_map[new_role])

                role_display = {
                    "client": "Клиент",
                    "captain": "Капитан",
                    "admin": "Администратор"
                }.get(new_role, new_role)

                await callback.message.edit_text(
                    f"Роль пользователя {client.full_name} изменена на {role_display}",
                    reply_markup=back_to_client_actions_keyboard(client_id)
                )

                logger.info(f"Администратор {callback.from_user.id} изменил роль пользователя {client_id} на {new_role}")

    except Exception as e:
        logger.error(f"Ошибка при установке роли клиенту {client_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при сохранении роли")


@router.callback_query(F.data.startswith("send_message_to_client:"))
async def send_message_to_client_start(callback: CallbackQuery, state: FSMContext):
    """Начало отправки сообщения клиенту (заглушка)"""
    client_id = int(callback.data.split(":")[1])
    await callback.answer("Функция в разработке")

    # Здесь можно будет потом реализовать отправку сообщений
    # await callback.message.answer("Введите сообщение для клиента...")
    # await state.set_state(AdminStates.waiting_for_client_message)
    # await state.update_data(target_client_id=client_id)


@router.callback_query(F.data.startswith("show_client_children:"))
async def show_client_children(callback: CallbackQuery):
    """Показать детей клиента"""
    client_id = int(callback.data.split(":")[1])
    await callback.answer()

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            client = await user_manager.user_repo.get_by_id(client_id)
            children = await user_manager.user_repo.get_children_users(client_id)

            if not children:
                await callback.message.edit_text(
                    f"У клиента {client.full_name} нет детей",
                    reply_markup=back_to_client_actions_keyboard(client_id)
                )
                return

            response = f"Дети клиента {client.full_name}:\n\n"
            for child in children:
                child_age = f"{child.age} лет" if child.age else "возраст неизвестен"
                response += (
                    f"ID: {child.id}\n"
                    f"Имя: {child.full_name}\n"
                    f"Дата рождения: {child.date_of_birth.strftime('%d.%m.%Y') if child.date_of_birth else 'не указана'}\n"
                    f"Возраст: {child_age}\n"
                    f"Вес: {child.weight} кг\n" if child.weight else ""
                    f"Токен: {child.verification_token or 'отсутствует'}\n"
                    f"---\n"
                )

            await callback.message.edit_text(
                response,
                reply_markup=back_to_client_actions_keyboard(client_id)
            )

    except Exception as e:
        logger.error(f"Ошибка при показе детей клиента {client_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при загрузке данных")


# ===== ОТМЕТКА ПРИБЫТИЯ =====

@router.callback_query(F.data.startswith("arrived:"))
async def mark_arrived(callback: CallbackQuery):
    """Отметить прибытие клиента"""
    await callback.answer()
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} отмечает прибытие для бронирования {booking_id}")

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_manager = BookingManager(uow.session)
                success = await booking_manager.mark_client_arrived(booking_id)

                if success:
                    logger.info(f"Бронирование {booking_id} отмечено как прибывшее")
                    await callback.message.edit_text("Клиент отмечен как прибывший")
                else:
                    logger.warning(f"Не удалось отметить прибытие для бронирования {booking_id}")
                    await callback.message.edit_text("Ошибка при обновлении статуса")

    except Exception as e:
        logger.error(f"Ошибка при отметке прибытия для бронирования {booking_id}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=clients_submenu())
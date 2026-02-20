from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.admin_panel.states_adm import AdminEditClient
from app.admin_panel.keyboards_adm import (
    admin_main_menu, clients_submenu, cancel_button,
    client_selection_menu, client_or_child_selection_menu,
    client_edit_fields_menu, cancel_inline_button
)
from app.database.models import UserRole
from app.database.session import async_session
from app.database.repositories import UserRepository
from app.database.managers import UserManager
from app.middlewares import AdminMiddleware
from app.utils.validation import (
    validate_name, validate_surname, validate_phone,
    validate_birthdate, validate_email, validate_address,
    validate_weight
)
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_client_redaction")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.message(F.text == "Редактировать клиента")
async def start_client_edit(message: Message, state: FSMContext):
    """Начало процесса редактирования клиента"""
    logger.info(f"Администратор {message.from_user.id} начал редактирование клиента")

    try:
        await message.answer(
            "Для поиска введите Фамилию и имя клиента через пробел; или номер телефона:",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminEditClient.waiting_for_client_selection)
        logger.debug(f"Администратор {message.from_user.id} перешел в состояние поиска клиента")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования клиента: {e}", exc_info=True)
        await message.answer(
            "Ошибка при начале редактирования",
            reply_markup=clients_submenu()
        )
        await state.clear()


@router.message(AdminEditClient.waiting_for_client_selection)
async def search_client_for_edit(message: Message, state: FSMContext):
    """Поиск клиента для редактирования"""
    search_query = message.text
    logger.info(f"Администратор {message.from_user.id} ищет клиента для редактирования по запросу: '{search_query}'")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            all_clients = await user_manager.search_clients(search_query, limit=10)

            clients = [
                client for client in all_clients
                if client.role == UserRole.client and client.linked_to_parent_id is None
            ]

            if not clients:
                logger.debug(f"Клиенты по запросу '{search_query}' не найдены")
                await message.answer(
                    "Клиенты не найдены. Попробуйте другой запрос (фамилию и имя через пробел; или номер телефона) или нажмите Отмена",
                    reply_markup=cancel_inline_button()
                )
                return

            response = f"Найдено клиентов: {len(clients)}\n\n"
            for client in clients:
                birth_date = client.date_of_birth.strftime('%d.%m.%Y') if client.date_of_birth else 'не указана'
                telegram_id = client.telegram_id if client.telegram_id else 'не привязан'

                response += (
                    f"Имя: {client.full_name}\n"
                    f"Дата рождения: {birth_date}\n"
                    f"Телефон: {client.phone_number}\n"
                    f"Telegram ID: {telegram_id}\n"
                    f"---\n"
                )

            await message.answer(
                response,
                reply_markup=client_selection_menu(clients)
            )

    except Exception as e:
        logger.error(f"Ошибка поиска клиента для редактирования: {e}", exc_info=True)
        await message.answer(
            "Ошибка при поиске клиента. Попробуйте снова или нажмите Отмена",
            reply_markup=cancel_button()
        )


@router.callback_query(F.data.startswith("select_client_for_edit:"))
async def select_client_for_edit(callback: CallbackQuery, state: FSMContext):
    """Выбор клиента из результатов поиска"""
    await callback.answer()

    client_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал клиента ID {client_id} для редактирования")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            client = await user_repo.get_by_id(client_id)

            if not client:
                logger.warning(f"Клиент ID {client_id} не найден")
                await callback.message.edit_text(
                    "Клиент не найден. Возможно, он был удален."
                )
                await state.clear()
                return

            # Проверяем, что выбранный пользователь - не администратор
            if client.role == UserRole.admin:
                logger.warning(f"Администратор {callback.from_user.id} попытался редактировать администратора ID {client_id}")
                await callback.message.edit_text(
                    "Нельзя редактировать администратора через этот раздел.\n"
                    "Используйте раздел Настройки -> Управление администраторами.\n\n",
                    "Редактировать детей администратора может только он сам через свой личный кабинет",
                    reply_markup=clients_submenu()
                )
                await state.clear()
                return

            await state.update_data(client_id=client_id)
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
        logger.error(f"Ошибка при выборе клиента: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=clients_submenu()
        )
        await state.clear()


async def show_client_edit_menu(message: Message, target_id: int, target_type: str, state: FSMContext):
    """Показать меню выбора поля для редактирования"""

    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(target_id)

        if not user:
            await message.answer("Пользователь не найден")
            await state.clear()
            return

        # Сохраняем target_id и target_type в состоянии
        await state.update_data(
            target_id=target_id,
            target_type=target_type
        )

        # Формируем сообщение с текущими данными
        birth_date = user.date_of_birth.strftime('%d.%m.%Y') if user.date_of_birth else 'не указана'
        email = user.email if user.email else 'не указан'
        address = user.address if user.address else 'не указан'
        weight = f"{user.weight} кг" if user.weight else 'не указан'

        # Для ребенка не показываем телефон
        if target_type == "client":
            phone = user.phone_number if user.phone_number else 'не указан'
            response = (
                f"Редактирование клиента: {user.full_name}\n\n"
                f"Текущие данные:\n"
                f"Фамилия, имя: {user.full_name}\n"
                f"Телефон: {phone}\n"
                f"Дата рождения: {birth_date}\n"
                f"Email: {email}\n"
                f"Адрес: {address}\n"
                f"Вес: {weight}\n\n"
                f"Выберите поле для редактирования:"
            )
            has_phone = True
        else:
            response = (
                f"Редактирование ребенка: {user.full_name}\n\n"
                f"Текущие данные:\n"
                f"Фамилия, имя: {user.full_name}\n"
                f"Дата рождения: {birth_date}\n"
                f"Email: {email}\n"
                f"Адрес: {address}\n"
                f"Вес: {weight}\n\n"
                f"Выберите поле для редактирования:"
            )
            has_phone = False

        await message.answer(
            response,
            reply_markup=client_edit_fields_menu(target_id, target_type, has_phone)
        )
        await state.set_state(AdminEditClient.waiting_for_field_selection)


@router.callback_query(F.data.startswith("edit_target:"))
async def select_edit_target(callback: CallbackQuery, state: FSMContext):
    """Выбор цели для редактирования (клиент или ребенок)"""
    await callback.answer()

    _, target_type, target_id = callback.data.split(":")
    target_id = int(target_id)

    logger.info(f"Администратор {callback.from_user.id} выбрал для редактирования {target_type} ID {target_id}")

    try:
        await show_client_edit_menu(callback.message, target_id, target_type, state)

    except Exception as e:
        logger.error(f"Ошибка при выборе цели редактирования: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=clients_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("edit_field:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    """Выбор поля для редактирования"""
    await callback.answer()

    # Парсим callback_data: edit_field:target_id:target_type:field_name
    _, target_id, target_type, field_name = callback.data.split(":")
    target_id = int(target_id)

    logger.info(f"Администратор {callback.from_user.id} выбрал поле '{field_name}' для {target_type} ID {target_id}")

    # Сохраняем выбранное поле в состоянии
    await state.update_data(
        current_field=field_name,
        target_id=target_id,
        target_type=target_type
    )

    # Словарь с подсказками для каждого поля
    field_prompts = {
        "surname": "Введите новую фамилию:",
        "name": "Введите новое имя:",
        "phone": "Введите новый номер телефона (в формате +7XXXXXXXXXX или 8XXXXXXXXXX):",
        "birth_date": "Введите новую дату рождения в формате ДД.ММ.ГГГГ:",
        "email": "Введите новый email адрес:",
        "address": "Введите новый адрес:",
        "weight": "Введите новый вес (в кг, целое число):"
    }

    prompt = field_prompts.get(field_name, "Введите новое значение:")

    # Устанавливаем соответствующее состояние в зависимости от поля
    state_mapping = {
        "surname": AdminEditClient.waiting_for_new_surname,
        "name": AdminEditClient.waiting_for_new_name,
        "phone": AdminEditClient.waiting_for_new_phone,
        "birth_date": AdminEditClient.waiting_for_new_birth_date,
        "email": AdminEditClient.waiting_for_new_email,
        "address": AdminEditClient.waiting_for_new_address,
        "weight": AdminEditClient.waiting_for_new_weight
    }

    await callback.message.edit_text(
        prompt,
        reply_markup=cancel_inline_button()
    )
    await state.set_state(state_mapping[field_name])


@router.message(AdminEditClient.waiting_for_new_surname)
async def process_new_surname(message: Message, state: FSMContext):
    """Обработка ввода новой фамилии"""
    logger.info(f"Администратор {message.from_user.id} ввел новую фамилию: '{message.text}'")

    try:
        validated_surname = validate_surname(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(target_id)

            if not user:
                logger.warning(f"Пользователь {target_id} не найден при обновлении фамилии")
                await message.answer("Пользователь не найден", reply_markup=clients_submenu())
                await state.clear()
                return

            name_parts = user.full_name.split()
            if len(name_parts) >= 2:
                current_name = name_parts[1]  # Имя
            else:
                current_name = ""

            new_full_name = f"{validated_surname} {current_name}".strip()
            updated = await user_repo.update(user.id, full_name=new_full_name)

            if updated:
                logger.info(f"Фамилия пользователя {target_id} обновлена на '{validated_surname}'")
                await message.answer(
                    "Фамилия успешно обновлена!",
                    reply_markup=cancel_button()
                )
                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить фамилию пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении фамилии",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидная фамилия: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении фамилии: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )

@router.message(AdminEditClient.waiting_for_new_name)
async def process_new_name(message: Message, state: FSMContext):
    """Обработка ввода нового имени"""
    logger.info(f"Администратор {message.from_user.id} ввел новое имя: '{message.text}'")

    try:
        validated_name = validate_name(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(target_id)

            if not user:
                logger.warning(f"Пользователь {target_id} не найден при обновлении имени")
                await message.answer("Пользователь не найден", reply_markup=clients_submenu())
                await state.clear()
                return

            name_parts = user.full_name.split()
            if len(name_parts) >= 1:
                current_surname = name_parts[0]  # Фамилия
            else:
                current_surname = ""

            new_full_name = f"{current_surname} {validated_name}".strip()
            updated = await user_repo.update(user.id, full_name=new_full_name)

            if updated:
                logger.info(f"Имя пользователя {target_id} обновлено на '{validated_name}'")
                await message.answer(
                    "Имя успешно обновлено!",
                    reply_markup=cancel_button()
                )

                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить имя пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении имени",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидное имя: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )

@router.message(AdminEditClient.waiting_for_new_phone)
async def process_new_phone(message: Message, state: FSMContext):
    """Обработка ввода нового телефона"""
    logger.info(f"Администратор {message.from_user.id} ввел новый телефон: '{message.text}'")

    try:
        validated_phone = validate_phone(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        if target_type != "client":
            logger.warning(f"Попытка редактировать телефон у ребенка {target_id}")
            await message.answer("У детей нельзя редактировать телефон")
            await show_client_edit_menu(message, target_id, target_type, state)
            return

        async with async_session() as session:
            user_repo = UserRepository(session)
            existing_user = await user_repo.get_by_phone(validated_phone)
            if existing_user and existing_user.id != target_id:
                logger.warning(f"Телефон {validated_phone} уже используется пользователем {existing_user.id}")
                await message.answer(
                    "Этот номер телефона уже зарегистрирован другим пользователем",
                    reply_markup=cancel_button()
                )
                return

            updated = await user_repo.update(target_id, phone_number=validated_phone)

            if updated:
                logger.info(f"Телефон пользователя {target_id} обновлен")
                await message.answer("Телефон успешно обновлен!")
                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить телефон пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении телефона",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидный телефон: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении телефона: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )

@router.message(AdminEditClient.waiting_for_new_birth_date)
async def process_new_birth_date(message: Message, state: FSMContext):
    """Обработка ввода новой даты рождения"""
    logger.info(f"Администратор {message.from_user.id} ввел новую дату рождения: '{message.text}'")

    try:
        validated_date = validate_birthdate(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            updated = await user_repo.update(target_id, date_of_birth=validated_date)

            if updated:
                logger.info(f"Дата рождения пользователя {target_id} обновлена")
                await message.answer(
                    "Дата рождения успешно обновлена!",
                    reply_markup=cancel_button()
                )

                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить дату рождения пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении даты рождения",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении даты рождения: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )


@router.message(AdminEditClient.waiting_for_new_email)
async def process_new_email(message: Message, state: FSMContext):
    """Обработка ввода нового email"""
    logger.info(f"Администратор {message.from_user.id} ввел новый email: '{message.text}'")

    try:
        validated_email = validate_email(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            updated = await user_repo.update(target_id, email=validated_email)

            if updated:
                logger.info(f"Email пользователя {target_id} обновлен")
                await message.answer(
                    "Email успешно обновлен!",
                    reply_markup=cancel_button()
                )

                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить email пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении email",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидный email: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении email: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )


@router.message(AdminEditClient.waiting_for_new_address)
async def process_new_address(message: Message, state: FSMContext):
    """Обработка ввода нового адреса"""
    logger.info(f"Администратор {message.from_user.id} ввел новый адрес: '{message.text}'")

    try:
        validated_address = validate_address(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            updated = await user_repo.update(target_id, address=validated_address)

            if updated:
                logger.info(f"Адрес пользователя {target_id} обновлен")
                await message.answer(
                    "Адрес успешно обновлен!",
                    reply_markup=cancel_button()
                )

                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить адрес пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении адреса",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидный адрес: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении адреса: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )

@router.message(AdminEditClient.waiting_for_new_weight)
async def process_new_weight(message: Message, state: FSMContext):
    """Обработка ввода нового веса"""
    logger.info(f"Администратор {message.from_user.id} ввел новый вес: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        data = await state.get_data()
        target_id = data.get('target_id')
        target_type = data.get('target_type')

        async with async_session() as session:
            user_repo = UserRepository(session)
            updated = await user_repo.update(target_id, weight=validated_weight)

            if updated:
                logger.info(f"Вес пользователя {target_id} обновлен")
                await message.answer(
                    "Вес успешно обновлен!",
                    reply_markup=cancel_button()
                )

                await show_client_edit_menu(message, target_id, target_type, state)
            else:
                logger.warning(f"Не удалось обновить вес пользователя {target_id}")
                await message.answer(
                    "Ошибка при обновлении веса",
                    reply_markup=cancel_button()
                )

    except ValueError as e:
        logger.warning(f"Невалидный вес: {message.text}")
        await message.answer(str(e), reply_markup=cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при обновлении веса: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=cancel_button()
        )

@router.callback_query(F.data == "search_client_again")
async def search_client_again(callback: CallbackQuery, state: FSMContext):
    """Начать новый поиск клиента"""
    try:
        await callback.answer()
        logger.info(f"Администратор {callback.from_user.id} начал новый поиск клиента")

        await callback.message.edit_text(
            "Введите Фамилию и имя клиента или номер телефона для поиска:",
            reply_markup=cancel_inline_button()
        )
        await state.set_state(AdminEditClient.waiting_for_client_selection)
    except Exception as e:
        logger.error(f"Ошибка при обновлении веса: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=admin_main_menu()
        )

@router.callback_query(F.data == "cancel_client_edit")
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_client_selection)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_surname)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_name)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_phone)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_birth_date)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_email)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_address)
@router.message(F.text == "Отмена", AdminEditClient.waiting_for_new_weight)
async def cancel_client_edit(message: Message | CallbackQuery, state: FSMContext):
    """Отмена редактирования клиента"""

    if isinstance(message, CallbackQuery):
        await message.answer()
        user_id = message.from_user.id
        msg = message.message
    else:
        user_id = message.from_user.id
        msg = message

    logger.info(f"Администратор {user_id} отменил редактирование клиента")

    await state.clear()
    await msg.answer(
        "Редактирование клиента отменено",
        reply_markup=clients_submenu()
    )

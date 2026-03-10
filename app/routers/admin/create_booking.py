"""
Роутер для создания записи администратором
Позволяет выбрать клиента, экскурсию, дату, время и создать бронирование
"""

import re
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import date

from app.database.unit_of_work import UnitOfWork
from app.database.managers import BookingManager, SlotManager, UserManager
from app.database.repositories import (
    ExcursionRepository, SlotRepository, UserRepository, BookingRepository
)
from app.database.session import async_session

from app.admin_panel.states_adm import AdminCreateBooking
from app.admin_panel.keyboards_adm import (
    bookings_submenu, cancel_button, admin_confirm_virtual_child_keyboard,
    create_booking_client_choice_keyboard, client_list_for_booking_keyboard,
    excursion_list_for_booking_keyboard, slot_list_for_booking_keyboard,
    admin_children_selection_keyboard, create_virtual_child,
    cancel_create_virtual_child, confirm_booking,
    continue_booking_with_excess_weight, slot_already_booked_keyboard
)
from app.user_panel.keyboards import bookings_main_menu_keyboard
from app.middlewares import AdminMiddleware
from app.utils.calculators import PriceCalculator, WeightCalculator
from app.utils.logging_config import get_logger
from app.utils.validation import validate_slot_date


logger = get_logger(__name__)

router = Router(name="admin_create_booking")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== НАЧАЛО СОЗДАНИЯ ЗАПИСИ =====

@router.message(F.text == "Создать запись")
async def start_create_booking(message: Message, state: FSMContext):
    """Начало создания записи администратором"""
    logger.info(f"Администратор {message.from_user.id} начал создание записи")

    try:
        await message.answer(
            "Создание новой записи на экскурсию.\n\n"
            "Для начала необходимо выбрать клиента:",
            reply_markup=create_booking_client_choice_keyboard()
        )
        await state.set_state(AdminCreateBooking.waiting_for_client_choice)
        logger.debug(f"Пользователь {message.from_user.id} перешел в состояние выбора клиента")

    except Exception as e:
        logger.error(f"Ошибка начала создания записи: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()


# ===== ОБРАБОТКА ВЫБОРА ТИПА КЛИЕНТА =====

@router.message(AdminCreateBooking.waiting_for_client_choice, F.text == "Найти существующего")
async def client_choice_search(message: Message, state: FSMContext):
    """Выбран поиск существующего клиента"""
    logger.info(f"Администратор {message.from_user.id} выбрал поиск клиента для записи")

    try:
        await message.answer(
            "Введите фамилию и имя клиента или номер телефона:",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminCreateBooking.waiting_for_client_search)

    except Exception as e:
        logger.error(f"Ошибка при выборе поиска клиента: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_client_choice, F.text == "Создать нового")
async def client_choice_new(message: Message, state: FSMContext):
    """Выбрано создание нового клиента - перенаправляем в процесс добавления клиента"""
    logger.info(f"Администратор {message.from_user.id} выбрал создание нового клиента")

    try:
        # Сохраняем, что мы пришли из процесса создания бронирования
        await state.update_data(return_to_booking=True)

        # Перенаправляем в процесс создания клиента
        from app.admin_panel.states_adm import AdminAddClient
        await state.set_state(AdminAddClient.waiting_for_name)
        await message.answer(
            'Вы добавляете нового клиента.\n'
            'Этот клиент не будет привязан к Telegram и сможет записываться на экскурсии только через администратора.\n\n'
            'Введите имя клиента:',
            reply_markup=cancel_button()
        )

    except Exception as e:
        logger.error(f"Ошибка при выборе создания клиента: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_client_choice, F.text == "Последние клиенты")
async def client_choice_recent(message: Message, state: FSMContext):
    """Выбраны последние клиенты"""
    logger.info(f"Администратор {message.from_user.id} запросил последних клиентов")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            recent_clients = await user_manager.get_new_clients(days_ago=10)

            if not recent_clients:
                await message.answer(
                    "Нет недавних клиентов",
                    reply_markup=create_booking_client_choice_keyboard()
                )
                return

            await message.answer(
                "Выберите клиента из списка:",
                reply_markup=client_list_for_booking_keyboard(recent_clients)
            )
            # Оставляем состояние - выбор будет обработан в callback

    except Exception as e:
        logger.error(f"Ошибка при получении последних клиентов: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_client_choice, F.text == "Отмена")
async def client_choice_cancel(message: Message, state: FSMContext):
    """Отмена создания записи"""
    logger.info(f"Администратор {message.from_user.id} отменил создание записи")

    try:
        await state.clear()
        await message.answer(
            "Создание записи отменено",
            reply_markup=bookings_submenu()
        )

    except Exception as e:
        logger.error(f"Ошибка при отмене: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка",
            reply_markup=bookings_submenu()
        )
        await state.clear()


# ===== ПОИСК КЛИЕНТА =====

@router.message(AdminCreateBooking.waiting_for_client_search)
async def process_client_search(message: Message, state: FSMContext):
    """Обработка поиска клиента для создания записи"""
    search_query = message.text
    logger.info(f"Администратор {message.from_user.id} ищет клиента по запросу: '{search_query}' для записи")

    try:
        # Проверка на отмену
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Поиск отменен",
                reply_markup=create_booking_client_choice_keyboard()
            )
            return

        if search_query.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            digits_only = re.sub(r'\D', '', search_query)

            if len(digits_only) == 11 and digits_only[0] == '8':
                search_query = '+7' + digits_only[1:]
                logger.debug(f"Нормализован номер телефона: {message.text} -> {search_query}")
            elif len(digits_only) == 11 and digits_only[0] == '7':
                search_query = '+' + digits_only
                logger.debug(f"Нормализован номер телефона: {message.text} -> {search_query}")

        async with async_session() as session:
            user_manager = UserManager(session)
            excursion_repo = ExcursionRepository(session)
            users = await user_manager.search_users(search_query, limit=10)

            if not users:
                logger.debug(f"Пользователи по запросу '{search_query}' не найдены")
                await message.answer(
                    "Пользователи не найдены. Попробуйте другой запрос:",
                    reply_markup=cancel_button()
                )
                return

            # Отделяем клиентов от остальных
            clients = [u for u in users if u.role.value == "client"]

            if not clients:
                non_clients = [u for u in users if u.role.value != "client"]
                if non_clients:
                    non_clients_info = "Найдены пользователи с другими ролями:\n"
                    for user in non_clients:
                        role_display = {
                            "captain": "Капитан",
                            "admin": "Администратор"
                        }.get(user.role.value, user.role.value)
                        non_clients_info += f"• {user.full_name} ({role_display})\n"

                    await message.answer(
                        f"{non_clients_info}\nКлиенты с таким запросом не найдены. Попробуйте другой запрос:",
                        reply_markup=cancel_button()
                    )
                else:
                    await message.answer(
                        "Клиенты с таким запросом не найдены. Попробуйте другой запрос:",
                        reply_markup=cancel_button()
                    )
                return

            # Если один клиент - сразу сохраняем и идем дальше
            if len(clients) == 1:
                client = clients[0]
                await state.update_data(client_id=client.id)
                await state.set_state(AdminCreateBooking.waiting_for_excursion)

                excursions = await excursion_repo.get_all(active_only=True)

                if not excursions:
                    await message.answer(
                        "Нет доступных экскурсий. Сначала создайте экскурсию.",
                        reply_markup=bookings_submenu()
                    )
                    await state.clear()
                    return

                await message.answer(
                    f"Выбран клиент: {client.full_name}\n"
                    f"Телефон: {client.phone_number}\n\n"
                    f"Выберите экскурсию:",
                    reply_markup=excursion_list_for_booking_keyboard(excursions)
                )
                return

            # Если несколько - показываем список для выбора
            await message.answer(
                f"Найдено клиентов: {len(clients)}\nВыберите нужного:",
                reply_markup=client_list_for_booking_keyboard(clients)
            )

    except Exception as e:
        logger.error(f"Ошибка поиска клиента: {e}", exc_info=True)
        await message.answer(
            "Ошибка при поиске. Попробуйте позже.",
            reply_markup=create_booking_client_choice_keyboard()
        )
        await state.clear()


# ===== ОБРАБОТКА ВЫБОРА КЛИЕНТА ИЗ СПИСКА =====

@router.callback_query(F.data.startswith("select_client_for_booking:"), AdminCreateBooking.waiting_for_client_search)
async def select_client_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбор клиента из списка найденных для создания записи"""
    client_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал клиента {client_id} для создания записи")

    try:
        await callback.answer()
        await state.update_data(client_id=client_id)
        await state.set_state(AdminCreateBooking.waiting_for_excursion)

        # Получаем данные клиента для подтверждения
        async with async_session() as session:
            user_repo = UserRepository(session)
            client = await user_repo.get_by_id(client_id)

            # Получаем список активных экскурсий
            excursion_repo = ExcursionRepository(session)
            excursions = await excursion_repo.get_all(active_only=True)

            if not excursions:
                await callback.message.edit_text(
                    "Нет доступных экскурсий. Сначала создайте экскурсию.",
                    reply_markup=bookings_submenu()
                )
                await state.clear()
                return

            if client:
                await callback.message.edit_text(
                    f"Выбран клиент: {client.full_name}\n"
                    f"Телефон: {client.phone_number}\n\n"
                    f"Выберите экскурсию:",
                    reply_markup=excursion_list_for_booking_keyboard(excursions)
                )
            else:
                await callback.message.edit_text(
                    "Клиент выбран. Выберите экскурсию:",
                    reply_markup=excursion_list_for_booking_keyboard(excursions)
                )

    except Exception as e:
        logger.error(f"Ошибка выбора клиента для записи: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "new_client_search_for_booking", AdminCreateBooking.waiting_for_client_search)
async def new_client_search_for_booking(callback: CallbackQuery, state: FSMContext):
    """Новый поиск клиента при создании записи"""
    logger.info(f"Администратор {callback.from_user.id} начал новый поиск клиента")

    try:
        await callback.answer()
        await callback.message.edit_text(
            "Введите фамилию и имя клиента или номер телефона:",
            reply_markup=cancel_button()
        )
        # Состояние остается waiting_for_client_search

    except Exception as e:
        logger.error(f"Ошибка нового поиска: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "cancel_booking_creation", AdminCreateBooking.waiting_for_client_search)
async def cancel_booking_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания записи"""
    logger.info(f"Администратор {callback.from_user.id} отменил создание записи")

    try:
        await callback.answer()
        await state.clear()
        await callback.message.edit_text(
            "Создание записи отменено",
            reply_markup=bookings_submenu()
        )

    except Exception as e:
        logger.error(f"Ошибка отмены: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()


# ===== ВЫБОР ЭКСКУРСИИ =====

@router.message(AdminCreateBooking.waiting_for_excursion)
async def show_excursions_for_booking(message: Message, state: FSMContext):
    """Показать список доступных экскурсий для выбора"""
    logger.info(f"Администратор {message.from_user.id} перешел к выбору экскурсии")

    try:
        async with async_session() as session:
            excursion_repo = ExcursionRepository(session)
            # Получаем только активные экскурсии
            excursions = await excursion_repo.get_all(active_only=True)

            if not excursions:
                await message.answer(
                    "Нет доступных экскурсий. Сначала создайте экскурсию.",
                    reply_markup=bookings_submenu()
                )
                await state.clear()
                return

            await message.answer(
                "Выберите экскурсию:",
                reply_markup=excursion_list_for_booking_keyboard(excursions)
            )

    except Exception as e:
        logger.error(f"Ошибка загрузки экскурсий: {e}", exc_info=True)
        await message.answer(
            "Ошибка при загрузке экскурсий",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("select_excursion_for_booking:"), AdminCreateBooking.waiting_for_excursion)
async def select_excursion_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбор экскурсии для создания записи"""
    excursion_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал экскурсию {excursion_id}")

    try:
        await callback.answer()
        await state.update_data(excursion_id=excursion_id)
        await state.set_state(AdminCreateBooking.waiting_for_date)

        async with async_session() as session:
            excursion_repo = ExcursionRepository(session)
            excursion = await excursion_repo.get_by_id(excursion_id)

            if excursion:
                await callback.message.answer(
                    f"Выбрана экскурсия: {excursion.name}\n\n"
                    f"Теперь введите дату в формате ДД.ММ.ГГГГ\n"
                    f"Например: 15.01.2024",
                    reply_markup=cancel_button()
                )
                await callback.message.delete()
            else:
                await callback.message.edit_text(
                    "Экскурсия выбрана. Теперь введите дату в формате ДД.ММ.ГГГГ",
                    reply_markup=cancel_button()
                )

    except Exception as e:
        logger.error(f"Ошибка выбора экскурсии: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()


# ===== ВЫБОР ДАТЫ И СЛОТА =====

@router.message(AdminCreateBooking.waiting_for_date)
async def process_date_for_booking(message: Message, state: FSMContext):
    """Обработка ввода даты и показ доступных слотов"""
    logger.info(f"Администратор {message.from_user.id} ввел дату: '{message.text}'")

    try:
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Создание записи отменено",
                reply_markup=bookings_submenu()
            )
            return

        try:
            target_date = validate_slot_date(message.text)
        except ValueError as e:
            await message.answer(
                f"{str(e)}\n\nПожалуйста, введите дату в формате ДД.ММ.ГГГГ:",
                reply_markup=cancel_button()
            )
            return

        data = await state.get_data()
        client_id = data.get('client_id')
        excursion_id = data.get('excursion_id')

        if not client_id or not excursion_id:
            logger.error("Не найдены client_id или excursion_id в state")
            await message.answer(
                "Ошибка: данные не найдены. Начните создание записи заново.",
                reply_markup=bookings_submenu()
            )
            await state.clear()
            return

        async with async_session() as session:
            # Получаем слоты на выбранную дату для этой экскурсии
            slot_manager = SlotManager(session)
            excursion, text, slots = await slot_manager.get_excursion_slots_for_date(
                exc_id=excursion_id,
                target_date=target_date
            )

            if not slots:
                # Нет слотов на эту дату
                await message.answer(
                    f"На {target_date.strftime('%d.%m.%Y')} нет доступных слотов для этой экскурсии.\n\n"
                    f"Выберите другую дату:",
                    reply_markup=cancel_button()
                )
                return

            await state.update_data(selected_date=target_date)

            # Показываем список слотов
            await message.answer(
                f"Доступные слоты на {target_date.strftime('%d.%m.%Y')}:\n\n"
                f"Выберите время:",
                reply_markup=slot_list_for_booking_keyboard(slots, excursion_id)
            )
            await state.set_state(AdminCreateBooking.waiting_for_slot)

    except Exception as e:
        logger.error(f"Ошибка обработки даты: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.callback_query(F.data.startswith("select_slot_for_booking:"), AdminCreateBooking.waiting_for_slot)
async def select_slot_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного слота для записи"""
    slot_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал слот {slot_id}")

    try:
        await callback.answer()
        await state.update_data(slot_id=slot_id)
        data = await state.get_data()
        client_id = data.get('client_id')

        if not client_id:
            logger.error("Не найден client_id в state")
            await callback.message.edit_text(
                "Ошибка: клиент не выбран. Начните создание записи заново.",
                reply_markup=bookings_submenu()
            )
            await state.clear()
            return


        async with async_session() as session:
            # ПРОВЕРКА: есть ли уже бронь у клиента на этот слот
            booking_repo = BookingRepository(session)
            existing_booking = await booking_repo.get_user_active_for_slot(client_id, slot_id)

            if existing_booking:
                await callback.message.edit_text(
                    f"У этого клиента уже есть активная бронь на данный слот!\n\n"
                    f"ID брони: {existing_booking.id}\n"
                    f"Статус: {existing_booking.booking_status.value}\n"
                    f"Оплата: {'оплачено' if existing_booking.payment_status == 'paid' else 'не оплачено'}\n\n"
                    f"Выберите другой слот или отмените создание записи.",
                    reply_markup=slot_already_booked_keyboard(data.get('excursion_id'))
                )
                return

            # Получаем информацию о слоте
            slot_manager = SlotManager(session)
            slot_info = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info:
                await callback.message.edit_text(
                    "Слот не найден. Попробуйте выбрать другой.",
                    reply_markup=bookings_submenu()
                )
                await state.clear()
                return

            slot = slot_info['slot']
            available_places = slot_info['available_places']
            available_weight = slot_info['available_weight']

            # Получаем детей клиента
            user_repo = UserRepository(session)
            children = await user_repo.get_children_users(client_id)

            # Сохраняем информацию о слоте в state
            await state.update_data(
                slot_info={
                    'date': slot.start_datetime.strftime('%d.%m.%Y'),
                    'time': slot.start_datetime.strftime('%H:%M'),
                    'excursion': slot.excursion.name,
                    'captain': slot.captain.full_name if slot.captain else 'не назначен',
                    'available_places': available_places,
                    'available_weight': available_weight
                }
            )

            # Формируем сообщение
            text = (
                f"Слот выбран:\n\n"
                f"Дата: {slot.start_datetime.strftime('%d.%m.%Y')}\n"
                f"Время: {slot.start_datetime.strftime('%H:%M')}\n"
                f"Экскурсия: {slot.excursion.name}\n"
                f"Капитан: {slot.captain.full_name if slot.captain else 'не назначен'}\n\n"
                f"Доступно мест: {available_places}\n"
                f"Доступный вес: {available_weight} кг\n\n"
            )

            if children:
                text += f"У клиента есть дети ({len(children)}). Выберите, кто поедет:"
                await callback.message.edit_text(
                    text,
                    reply_markup=admin_children_selection_keyboard(children, [])
                )
            else:
                text += "У клиента нет зарегистрированных детей. Вы можете создать виртуальных детей."
                await callback.message.edit_text(
                    text,
                    reply_markup=create_virtual_child()
                )

            await state.set_state(AdminCreateBooking.waiting_for_children_selection)

    except Exception as e:
        logger.error(f"Ошибка выбора слота: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data.startswith("another_date_for_booking:"), AdminCreateBooking.waiting_for_slot)
async def another_date_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбор другой даты"""
    excursion_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} запросил другую дату")

    try:
        await callback.answer()
        await state.update_data(excursion_id=excursion_id)
        await state.set_state(AdminCreateBooking.waiting_for_date)

        await callback.message.answer(
            "Введите другую дату в формате ДД.ММ.ГГГГ:",
            reply_markup=cancel_button()
        )
        await callback.message.delete()

    except Exception as e:
        logger.error(f"Ошибка при выборе другой даты: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data.startswith("admin_toggle_child:"), AdminCreateBooking.waiting_for_children_selection)
async def admin_toggle_child(callback: CallbackQuery, state: FSMContext):
    """Выбор/отмена выбора существующего ребенка"""
    child_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} выбрал ребенка {child_id}")

    try:
        await callback.answer()

        # Получаем текущие данные
        data = await state.get_data()
        selected_children = data.get('selected_children', [])
        client_id = data.get('client_id')
        slot_info = data.get('slot_info', {})

        # Переключаем выбор
        if child_id in selected_children:
            selected_children.remove(child_id)
        else:
            selected_children.append(child_id)

        await state.update_data(selected_children=selected_children)

        # Обновляем клавиатуру
        async with async_session() as session:
            user_repo = UserRepository(session)
            children = await user_repo.get_children_users(client_id)

            # Формируем текст
            text = (
                f"Слот выбран:\n\n"
                f"Дата: {slot_info.get('date')}\n"
                f"Время: {slot_info.get('time')}\n"
                f"Экскурсия: {slot_info.get('excursion')}\n"
                f"Капитан: {slot_info.get('captain')}\n\n"
                f"Выбрано детей: {len(selected_children)}\n"
                f"Выберите детей:"
            )

            await callback.message.edit_text(
                text,
                reply_markup=admin_children_selection_keyboard(children, selected_children)
            )

    except Exception as e:
        logger.error(f"Ошибка выбора ребенка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "admin_finish_children_selection", AdminCreateBooking.waiting_for_children_selection)
async def admin_finish_children_selection(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора детей"""
    logger.info(f"Администратор {callback.from_user.id} завершил выбор детей")

    try:
        await callback.answer()

        data = await state.get_data()
        client_id = data.get('client_id')
        selected_children = data.get('selected_children', [])
        virtual_children = data.get('virtual_children', [])

        total_children = len(selected_children) + len(virtual_children)
        await state.update_data(total_children=total_children)

        # Проверяем, есть ли вес у клиента в БД
        async with async_session() as session:
            user_repo = UserRepository(session)
            client = await user_repo.get_by_id(client_id)

            if client and client.weight:
                # Вес уже есть в БД - используем его
                logger.info(f"Вес клиента {client_id} найден в БД: {client.weight} кг")
                await state.update_data(adult_weight=client.weight)

                # Сразу показываем подтверждение
                await callback.message.edit_text(
                    f"Выбрано детей: {total_children}\n"
                    f"Вес взрослого: {client.weight} кг (из профиля)",
                    reply_markup=None
                )
                await show_booking_confirmation(callback.message, state)
            else:
                # Веса нет - запрашиваем
                await callback.message.edit_text(
                    f"Выбрано детей: {total_children}\n\n"
                    f"Вес взрослого не указан в профиле.\n",
                    reply_markup=None
                )
                await callback.message.answer(
                    "Введите вес в кг (только цифры, например: 75):",
                    reply_markup=cancel_button()
                )
                await state.set_state(AdminCreateBooking.waiting_for_adult_weight)

    except Exception as e:
        logger.error(f"Ошибка завершения выбора детей: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "admin_no_children", AdminCreateBooking.waiting_for_children_selection)
async def admin_no_children(callback: CallbackQuery, state: FSMContext):
    """Выбрано 'Только взрослый (без детей)' - пропускаем выбор детей"""
    logger.info(f"Администратор {callback.from_user.id} выбрал 'Только взрослый (без детей)'")

    try:
        await callback.answer()

        data = await state.get_data()
        client_id = data.get('client_id')
        slot_id = data.get('slot_id')
        slot_info = data.get('slot_info', {})

        await state.update_data(
            selected_children=[],
            virtual_children=[],
            total_children=0
        )

        # Проверяем, есть ли вес у клиента в БД
        async with async_session() as session:
            user_repo = UserRepository(session)
            client = await user_repo.get_by_id(client_id)

            if client and client.weight:
                # Вес уже есть в БД - используем его
                logger.info(f"Вес клиента {client_id} найден в БД: {client.weight} кг")
                await state.update_data(adult_weight=client.weight)
                await state.update_data(total_weight=client.weight)
                await callback.message.delete()
                await show_booking_confirmation(callback.message, state)
            else:
                # Веса нет - запрашиваем
                await callback.message.delete()
                await callback.message.answer(
                    "Вес взрослого не указан в профиле.\n"
                    "Введите вес в кг (только цифры, например: 75):",
                    reply_markup=cancel_button()
                )
                await state.set_state(AdminCreateBooking.waiting_for_adult_weight)

    except Exception as e:
        logger.error(f"Ошибка при выборе 'Только взрослый': {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Начните создание записи заново.",
            reply_markup=bookings_submenu()
        )
        await state.clear()


# ===== СОЗДАНИЕ ВИРТУАЛЬНОГО РЕБЕНКА =====

@router.callback_query(F.data == "admin_cancel_virtual_child", AdminCreateBooking.waiting_for_virtual_child_name)
@router.callback_query(F.data == "admin_cancel_virtual_child", AdminCreateBooking.waiting_for_virtual_child_age)
@router.callback_query(F.data == "admin_cancel_virtual_child", AdminCreateBooking.waiting_for_virtual_child_weight)
async def admin_cancel_virtual_child(callback: CallbackQuery, state: FSMContext):
    """Отмена создания виртуального ребенка"""
    logger.info(f"Администратор {callback.from_user.id} отменил создание виртуального ребенка")

    try:
        await callback.answer()

        data = await state.get_data()
        client_id = data.get('client_id')
        slot_info = data.get('slot_info', {})

        async with async_session() as session:
            user_repo = UserRepository(session)
            children = await user_repo.get_children_users(client_id)
            selected_children = data.get('selected_children', [])
            virtual_children = data.get('virtual_children', [])

            text = (
                f"Слот выбран:\n\n"
                f"Дата: {slot_info.get('date')}\n"
                f"Время: {slot_info.get('time')}\n"
                f"Экскурсия: {slot_info.get('excursion')}\n"
                f"Капитан: {slot_info.get('captain')}\n\n"
                f"Выбрано детей: {len(selected_children) + len(virtual_children)} "
                f"(реальных: {len(selected_children)}, виртуальных: {len(virtual_children)})\n"
                f"Выберите детей:"
            )

            await callback.message.edit_text(
                text,
                reply_markup=admin_children_selection_keyboard(children, selected_children)
            )
            await state.set_state(AdminCreateBooking.waiting_for_children_selection)

    except Exception as e:
        logger.error(f"Ошибка отмены создания ребенка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "admin_create_virtual_child", AdminCreateBooking.waiting_for_children_selection)
async def admin_create_virtual_child_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания виртуального ребенка"""
    logger.info(f"Администратор {callback.from_user.id} начал создание виртуального ребенка")

    try:
        await callback.answer()

        await callback.message.edit_text(
            "Создание виртуального ребенка.\n\n"
            "Введите фамилию и имя ребенка через пробел (например: Иванов Петр):",
            reply_markup=cancel_create_virtual_child()
        )
        await state.set_state(AdminCreateBooking.waiting_for_virtual_child_name)

    except Exception as e:
        logger.error(f"Ошибка начала создания виртуального ребенка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_virtual_child_name)
async def admin_process_virtual_child_name(message: Message, state: FSMContext):
    """Обработка имени виртуального ребенка"""
    logger.info(f"Администратор {message.from_user.id} ввел имя ребенка: '{message.text}'")

    try:
        # Проверка на отмену
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Создание записи отменено",
                reply_markup=bookings_submenu()
            )
            return

        # Разбиваем на фамилию и имя
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.answer(
                "Введите фамилию и имя через пробел (например: Иванов Петр):",
                reply_markup=cancel_button()
            )
            return

        surname = parts[0]
        name = " ".join(parts[1:])

        # Валидация
        try:
            from app.utils.validation import validate_surname, validate_name
            validated_surname = validate_surname(surname)
            validated_name = validate_name(name)
        except ValueError as e:
            await message.answer(
                f"Ошибка валидации: {str(e)}\n\nПопробуйте еще раз:",
                reply_markup=cancel_button()
            )
            return

        await state.update_data(
            virtual_child_surname=validated_surname,
            virtual_child_name=validated_name
        )

        await message.answer(
            f"Фамилия: {validated_surname}\n"
            f"Имя: {validated_name}\n\n"
            f"Введите возраст ребенка (целое число лет, например: 7):",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminCreateBooking.waiting_for_virtual_child_age)

    except Exception as e:
        logger.error(f"Ошибка обработки имени ребенка: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_virtual_child_age)
async def admin_process_virtual_child_age(message: Message, state: FSMContext):
    """Обработка возраста виртуального ребенка"""
    logger.info(f"Администратор {message.from_user.id} ввел возраст: '{message.text}'")

    try:
        # Проверка на отмену
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Создание записи отменено",
                reply_markup=bookings_submenu()
            )
            return

        # Валидация возраста
        try:
            age = int(message.text.strip())
            if age < 0 or age > 18:
                await message.answer(
                    "Возраст должен быть от 0 до 18 лет. Введите корректный возраст:",
                    reply_markup=cancel_button()
                )
                return
        except ValueError:
            await message.answer(
                "Введите возраст целым числом (например: 7):",
                reply_markup=cancel_button()
            )
            return

        # Рассчитываем примерную дату рождения
        today = date.today()
        birth_date = date(today.year - age, today.month, today.day)

        await state.update_data(
            virtual_child_age=age,
            virtual_child_birth_date=birth_date
        )

        await message.answer(
            f"Возраст: {age} лет\n\n"
            f"Введите вес ребенка в кг (целое число, например: 25):\n"
            f"Или нажмите /skip чтобы назначить автоматически",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminCreateBooking.waiting_for_virtual_child_weight)

    except Exception as e:
        logger.error(f"Ошибка обработки возраста ребенка: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.message(AdminCreateBooking.waiting_for_virtual_child_weight)
async def admin_process_virtual_child_weight(message: Message, state: FSMContext):
    """Обработка веса виртуального ребенка"""
    logger.info(f"Администратор {message.from_user.id} ввел вес: '{message.text}'")

    try:
        # Проверка на отмену
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Создание записи отменено",
                reply_markup=bookings_submenu()
            )
            return

        weight = None
        if message.text.lower() != "/skip":
            try:
                from app.utils.validation import validate_weight
                weight = validate_weight(message.text.strip())
            except ValueError as e:
                await message.answer(
                    f"Ошибка валидации: {str(e)}\n\n"
                    f"Введите вес целым числом или /skip:",
                    reply_markup=cancel_button()
                )
                return
        if message.text.lower() == "/skip":
            try:
                data = await state.get_data()
                age = data.get('virtual_child_age')
                weight = WeightCalculator.calculate_average_child_weight(age)
            except ValueError as e:
                await message.answer(
                    f"Ошибка автоматического назначения веса: {str(e)}\n\n"
                    f"Введите вес целым числом",
                    reply_markup=cancel_button()
                )
                return
        await state.update_data(virtual_child_weight=weight)

        # Показываем данные для подтверждения
        data = await state.get_data()

        text = (
            "Проверьте данные виртуального ребенка:\n\n"
            f"Фамилия: {data.get('virtual_child_surname')}\n"
            f"Имя: {data.get('virtual_child_name')}\n"
            f"Возраст: {data.get('virtual_child_age')} лет\n"
            f"Вес: {weight} кг\n"
        )

        await message.answer(
            text,
            reply_markup=admin_confirm_virtual_child_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка обработки веса ребенка: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.callback_query(F.data == "admin_confirm_virtual_child", AdminCreateBooking.waiting_for_virtual_child_weight)
async def admin_confirm_virtual_child(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания виртуального ребенка"""
    logger.info(f"Администратор {callback.from_user.id} подтвердил создание виртуального ребенка")

    try:
        await callback.answer()

        data = await state.get_data()
        client_id = data.get('client_id')
        virtual_children = data.get('virtual_children', [])

        # Создаем запись о виртуальном ребенке (пока только в state, не в БД)
        new_child = {
            'id': f"temp_{len(virtual_children)}",  # временный ID
            'surname': data.get('virtual_child_surname'),
            'name': data.get('virtual_child_name'),
            'full_name': f"{data.get('virtual_child_surname')} {data.get('virtual_child_name')}",
            'birth_date': data.get('virtual_child_birth_date'),
            'age': data.get('virtual_child_age'),
            'weight': data.get('virtual_child_weight'),
            'is_virtual': True
        }

        virtual_children.append(new_child)

        # Очищаем временные данные
        await state.update_data(
            virtual_children=virtual_children,
            virtual_child_surname=None,
            virtual_child_name=None,
            virtual_child_age=None,
            virtual_child_birth_date=None,
            virtual_child_weight=None
        )

        # Возвращаемся к выбору детей
        async with async_session() as session:
            user_repo = UserRepository(session)
            children = await user_repo.get_children_users(client_id)
            selected_children = data.get('selected_children', [])
            slot_info = data.get('slot_info', {})

            text = (
                f"Слот выбран:\n\n"
                f"Дата: {slot_info.get('date')}\n"
                f"Время: {slot_info.get('time')}\n"
                f"Экскурсия: {slot_info.get('excursion')}\n"
                f"Капитан: {slot_info.get('captain')}\n\n"
                f"Выбрано детей: {len(selected_children) + len(virtual_children)} "
                f"(реальных: {len(selected_children)}, виртуальных: {len(virtual_children)})\n"
                f"Выберите детей:"
            )

            await callback.message.edit_text(
                text,
                reply_markup=admin_children_selection_keyboard(children, selected_children)
            )
            await state.set_state(AdminCreateBooking.waiting_for_children_selection)

    except Exception as e:
        logger.error(f"Ошибка подтверждения создания ребенка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "admin_edit_virtual_child", AdminCreateBooking.waiting_for_virtual_child_weight)
async def admin_edit_virtual_child(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных виртуального ребенка"""
    logger.info(f"Администратор {callback.from_user.id} решил редактировать данные ребенка")

    try:
        await callback.answer()

        await callback.message.edit_text(
            "Введите фамилию и имя ребенка через пробел (например: Иванов Петр):",
            reply_markup=cancel_create_virtual_child()
        )
        await state.set_state(AdminCreateBooking.waiting_for_virtual_child_name)

    except Exception as e:
        logger.error(f"Ошибка редактирования ребенка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()


# ===== ВВОД ВЕСА ВЗРОСЛОГО =====

@router.message(AdminCreateBooking.waiting_for_adult_weight)
async def process_adult_weight(message: Message, state: FSMContext):
    """Обработка ввода веса взрослого"""
    logger.info(f"Администратор {message.from_user.id} ввел вес взрослого: '{message.text}'")

    try:
        # Проверка на отмену
        if message.text.lower() == "/cancel" or message.text == "Отмена":
            await state.clear()
            await message.answer(
                "Создание записи отменено",
                reply_markup=bookings_submenu()
            )
            return

        # Валидация веса
        try:
            from app.utils.validation import validate_weight
            adult_weight = validate_weight(message.text.strip())
        except ValueError as e:
            await message.answer(
                f"Ошибка валидации: {str(e)}\n\nВведите вес целым числом:",
                reply_markup=cancel_button()
            )
            return

        # Получаем данные из state
        data = await state.get_data()
        slot_id = data.get('slot_id')
        client_id = data.get('client_id')
        selected_children = data.get('selected_children', [])
        virtual_children = data.get('virtual_children', [])
        slot_info = data.get('slot_info', {})

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                await user_repo.update(client_id, weight=adult_weight)
                logger.info(f"Вес клиента {client_id} обновлен: {adult_weight} кг")

        # Проверяем доступный вес в слоте
        async with async_session() as session:
            slot_manager = SlotManager(session)
            slot_info_db = await slot_manager.get_slot_full_info(slot_id)

            if not slot_info_db:
                await message.answer(
                    "Слот не найден. Начните создание записи заново.",
                    reply_markup=bookings_submenu()
                )
                await state.clear()
                return

            available_weight = slot_info_db['available_weight']

            # Считаем общий вес детей (у реальных детей вес берем из БД)
            children_weight = 0

            # Вес реальных детей
            if selected_children:
                user_repo = UserRepository(session)
                for child_id in selected_children:
                    child = await user_repo.get_by_id(child_id)
                    if child and child.weight:
                        children_weight += child.weight

            # Вес виртуальных детей
            for child in virtual_children:
                if child.get('weight'):
                    children_weight += child['weight']

            total_weight = adult_weight + children_weight

            if total_weight > available_weight:
                await message.answer(
                    f"Превышение допустимого веса!\n\n"
                    f"Доступный вес в слоте: {available_weight} кг\n"
                    f"Ваш вес: {adult_weight} кг\n"
                    f"Вес детей: {children_weight} кг\n"
                    f"Общий вес: {total_weight} кг\n\n"
                    f"Превышение: {total_weight - available_weight} кг\n\n"
                    f"Вы можете:\n"
                    f"1. Уменьшить количество детей\n"
                    f"2. Выбрать другой слот\n"
                    f"3. Продолжить (информационно, бронь все равно создастся)",
                    reply_markup=continue_booking_with_excess_weight()
                )
                await state.update_data(
                    adult_weight=adult_weight,
                    total_weight=total_weight,
                    weight_warning=True
                )
                return

            # Если вес в порядке, сохраняем и показываем подтверждение
            await state.update_data(
                adult_weight=adult_weight,
                total_weight=total_weight,
                weight_warning=False
            )

            await show_booking_confirmation(message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки веса взрослого: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.callback_query(F.data == "admin_continue_booking", AdminCreateBooking.waiting_for_adult_weight)
async def continue_booking_with_weight_warning(callback: CallbackQuery, state: FSMContext):
    """Продолжить бронирование несмотря на превышение веса"""
    logger.info(f"Администратор {callback.from_user.id} решил продолжить с превышением веса")

    try:
        await callback.answer()
        await show_booking_confirmation(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка при продолжении бронирования: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()

@router.callback_query(F.data == "admin_back_to_children_selection", AdminCreateBooking.waiting_for_adult_weight)
async def back_to_children_selection(callback: CallbackQuery, state: FSMContext):
    """Вернуться к выбору детей"""
    logger.info(f"Администратор {callback.from_user.id} вернулся к выбору детей")

    try:
        await callback.answer()

        data = await state.get_data()
        client_id = data.get('client_id')
        slot_info = data.get('slot_info', {})

        async with async_session() as session:
            user_repo = UserRepository(session)
            children = await user_repo.get_children_users(client_id)
            selected_children = data.get('selected_children', [])
            virtual_children = data.get('virtual_children', [])

            text = (
                f"Слот выбран:\n\n"
                f"Дата: {slot_info.get('date')}\n"
                f"Время: {slot_info.get('time')}\n"
                f"Экскурсия: {slot_info.get('excursion')}\n"
                f"Капитан: {slot_info.get('captain')}\n\n"
                f"Выбрано детей: {len(selected_children) + len(virtual_children)} "
                f"(реальных: {len(selected_children)}, виртуальных: {len(virtual_children)})\n"
                f"Выберите детей:"
            )

            await callback.message.edit_text(
                text,
                reply_markup=admin_children_selection_keyboard(children, selected_children)
            )
            await state.set_state(AdminCreateBooking.waiting_for_children_selection)

    except Exception as e:
        logger.error(f"Ошибка возврата к выбору детей: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка")
        await state.clear()


# ===== ПОДТВЕРЖДЕНИЕ И СОЗДАНИЕ БРОНИРОВАНИЯ =====

async def show_booking_confirmation(message: Message, state: FSMContext):
    """Показать подтверждение бронирования"""

    data = await state.get_data()

    client_id = data.get('client_id')
    slot_id = data.get('slot_id')
    slot_info = data.get('slot_info', {})
    selected_children = data.get('selected_children', [])
    virtual_children = data.get('virtual_children', [])
    adult_weight = data.get('adult_weight')
    total_weight = data.get('total_weight')
    weight_warning = data.get('weight_warning', False)

    async with async_session() as session:
        user_repo = UserRepository(session)
        client = await user_repo.get_by_id(client_id)

        if not client:
            await message.answer(
                "Клиент не найден. Начните создание записи заново.",
                reply_markup=bookings_submenu()
            )
            await state.clear()
            return

        # Формируем текст подтверждения
        text = [
            "Проверьте данные бронирования:",
            "",
            f"Клиент: {client.full_name}",
            f"Телефон: {client.phone_number}",
            f"Вес взрослого: {adult_weight} кг",
            "",
            f"Экскурсия: {slot_info.get('excursion')}",
            f"Дата: {slot_info.get('date')}",
            f"Время: {slot_info.get('time')}",
            f"Капитан: {slot_info.get('captain')}",
        ]

        if selected_children or virtual_children:
            text.append(f"")
            text.append(f"Дети ({len(selected_children) + len(virtual_children)}):")

            # Реальные дети
            if selected_children:
                text.append("  Зарегистрированные:")
                for child_id in selected_children:
                    child = await user_repo.get_by_id(child_id)
                    if child:
                        weight_info = f", вес: {child.weight} кг" if child.weight else ""
                        text.append(f"  • {child.full_name}{weight_info}")

            # Виртуальные дети
            if virtual_children:
                text.append("  Виртуальные:")
                for child in virtual_children:
                    weight_info = f", вес: {child.get('weight')} кг" if child.get('weight') else ""
                    text.append(f"  • {child.get('full_name')} ({child.get('age')} лет){weight_info}")

        text.append(f"")
        text.append(f"Общий вес участников: {total_weight} кг")

        if weight_warning:
            text.append("")
            text.append("ВНИМАНИЕ: превышение допустимого веса!")

        # Получаем стоимость
        slot_repo = SlotRepository(session)
        slot = await slot_repo.get_by_id(slot_id)
        base_price = slot.excursion.base_price if slot and slot.excursion else 0

        # Расчет стоимости
        total_price = base_price  # взрослый

        # Дети (реальные)
        for child_id in selected_children:
            child = await user_repo.get_by_id(child_id)
            if child and child.date_of_birth:
                child_price, _ = PriceCalculator.calculate_child_price(base_price, child.date_of_birth)
                total_price += child_price

        # Виртуальные дети (считаем по возрасту)
        for child in virtual_children:
            if child.get('birth_date'):
                child_price, _ = PriceCalculator.calculate_child_price(base_price, child['birth_date'])
                total_price += child_price

        text.append(f"")
        text.append(f"Сумма к оплате: {total_price} руб.")

        await state.update_data(
            total_price=total_price,
            client_name=client.full_name,
            client_phone=client.phone_number
        )

        await message.answer("\n".join(text), reply_markup=confirm_booking())
        await state.set_state(AdminCreateBooking.waiting_for_confirmation)

@router.callback_query(F.data == "admin_confirm_booking_final", AdminCreateBooking.waiting_for_confirmation)
async def admin_confirm_booking_final(callback: CallbackQuery, state: FSMContext):
    """Финальное подтверждение и создание бронирования"""
    logger.info(f"Администратор {callback.from_user.id} подтверждает создание бронирования")

    try:
        await callback.answer()

        data = await state.get_data()

        client_id = data.get('client_id')
        slot_id = data.get('slot_id')
        admin_telegram_id = callback.from_user.id
        selected_children = data.get('selected_children', [])
        virtual_children = data.get('virtual_children', [])
        adult_weight = data.get('adult_weight')
        total_price = data.get('total_price')
        payment_method = data.get('payment_method', 'cash')  # cash или card

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                booking_manager = BookingManager(uow.session)
                user_manager = UserManager(uow.session)
                slot_repo = SlotRepository(uow.session)

                # Получаем админа для creator_id
                admin = await user_manager.user_repo.get_by_telegram_id(admin_telegram_id)

                # Получаем слот для базовой цены
                slot = await slot_repo.get_by_id(slot_id)
                base_price = slot.excursion.base_price if slot and slot.excursion else 0

                # Создаем виртуальных детей в БД
                created_virtual_ids = []
                children_data = []

                for v_child in virtual_children:
                    # Рассчитываем цену для ребенка
                    child_price, age_category = PriceCalculator.calculate_child_price(
                        base_price, v_child['birth_date']
                    )

                    # Создаем виртуального ребенка
                    child_user = await user_manager.create_virtual_child(
                        parent_id=client_id,
                        full_name=v_child['full_name'],
                        date_of_birth=v_child['birth_date'],
                        weight=v_child.get('weight')
                    )

                    if child_user:
                        created_virtual_ids.append(child_user.id)
                        children_data.append({
                            'child_id': child_user.id,
                            'age_category': age_category,
                            'price': child_price
                        })
                        logger.info(f"Создан виртуальный ребенок {child_user.id} для родителя {client_id}")

                # Добавляем реальных детей
                if selected_children:
                    for child_id in selected_children:
                        child = await user_manager.user_repo.get_by_id(child_id)
                        if child and child.date_of_birth:
                            child_price, age_category = PriceCalculator.calculate_child_price(
                                base_price, child.date_of_birth
                            )
                            children_data.append({
                                'child_id': child_id,
                                'age_category': age_category,
                                'price': child_price
                            })

                # Создаем бронирование
                booking, error_msg = await booking_manager.create_booking(
                    slot_id=slot_id,
                    adult_user_id=client_id,
                    children_count=len(selected_children) + len(virtual_children),
                    total_price=total_price,
                    admin_creator_id=admin.id if admin else None,
                    children_data=children_data,
                    total_weight=adult_weight + sum([c.get('weight', 0) for c in virtual_children])
                )

                if not booking:
                    # Если не удалось создать бронь, удаляем созданных виртуальных детей
                    for child_id in created_virtual_ids:
                        try:
                            await user_manager.user_repo.delete(child_id)
                        except:
                            pass

                    await callback.message.edit_text(
                        f"Ошибка при создании бронирования: {error_msg}",
                        reply_markup=bookings_submenu()
                    )
                    await state.clear()
                    return

                # Получаем полную информацию о клиенте
                client = await user_manager.user_repo.get_by_id(client_id)

                # Отправляем уведомление клиенту, если у него есть telegram_id
                if client and client.telegram_id:
                    try:
                        bot = callback.bot

                        # Формируем текст уведомления
                        notification_text = [
                            f"Администратор {admin.full_name} зарегистрировал вас на экскурсию",
                            "",
                            f"Экскурсия: {data.get('slot_info', {}).get('excursion')}",
                            f"Дата: {data.get('slot_info', {}).get('date')}",
                            f"Время: {data.get('slot_info', {}).get('time')}",
                            "",
                            f"Взрослых: 1"
                        ]

                        if selected_children:
                            notification_text.append(f"Детей (зарегистрированных): {len(selected_children)}")
                        if virtual_children:
                            notification_text.append(f"Детей (новых): {len(virtual_children)}")

                        notification_text.append("")

                        if payment_method == 'cash':
                            notification_text.append(
                                f"Сумма к оплате: {total_price} руб. (наличными при посадке)"
                            )
                        else:
                            # Для оплаты картой можно добавить ссылку на оплату
                            notification_text.append(
                                f"Сумма к оплате: {total_price} руб."
                            )
                            notification_text.append(
                                "Для оплаты перейдите в раздел 'Мои бронирования'"
                            )

                        await bot.send_message(
                            chat_id=client.telegram_id,
                            text="\n".join(notification_text),
                            reply_markup=bookings_main_menu_keyboard()
                        )

                        logger.info(f"Уведомление о бронировании #{booking.id} отправлено клиенту {client.telegram_id}")

                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления клиенту {client.telegram_id}: {e}", exc_info=True)

                # Формируем сообщение об успехе для администратора
                success_text = [
                    f"Бронирование #{booking.id} успешно создано!",
                    f"",
                    f"Клиент: {data.get('client_name')}",
                    f"Телефон: {data.get('client_phone')}",
                    f"Экскурсия: {data.get('slot_info', {}).get('excursion')}",
                    f"Дата: {data.get('slot_info', {}).get('date')}",
                    f"Время: {data.get('slot_info', {}).get('time')}",
                    f"",
                    f"Сумма к оплате: {total_price} руб.",
                    f"Способ оплаты: {'наличные' if payment_method == 'cash' else 'уточнить'}",
                ]

                if virtual_children:
                    success_text.append(f"\nСоздано виртуальных детей: {len(virtual_children)}")

                if client and client.telegram_id:
                    success_text.append(f"\nУведомление клиенту отправлено")
                elif client and not client.telegram_id:
                    success_text.append(f"\nУ клиента нет Telegram ID для уведомления")

                await callback.message.edit_text(
                    "\n".join(success_text),
                    reply_markup=None
                )

                await callback.message.answer(
                    "Возврат в меню записей",
                    reply_markup=bookings_submenu()
                )

                logger.info(f"Бронирование {booking.id} создано администратором {admin_telegram_id}")
                await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания бронирования: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при создании бронирования",
            reply_markup=bookings_submenu()
        )
        await state.clear()

@router.callback_query(F.data == "cancel_booking_creation")
async def cancel_booking_creation_universal(callback: CallbackQuery, state: FSMContext):
    """Универсальная отмена создания записи (работает в любом состоянии)"""
    logger.info(f"Администратор {callback.from_user.id} отменил создание записи (универсальный)")

    try:
        await callback.answer()
        await state.clear()

        # Пробуем отредактировать сообщение
        try:
            await callback.message.edit_text(
                "Создание записи отменено",
                reply_markup=None
            )
        except:
            pass

        # Отправляем новое сообщение с клавиатурой
        await callback.message.answer(
            "Создание записи отменено",
            reply_markup=bookings_submenu()
        )

    except Exception as e:
        logger.error(f"Ошибка при отмене: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=bookings_submenu()
        )
        await state.clear()
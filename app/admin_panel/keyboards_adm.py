from typing import Optional
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from datetime import date

from app.database.models import (
    SlotStatus, TelegramFile, FileType, User, DiscountType
    )


# ===== ГЛАВНОЕ МЕНЮ =====

def admin_main_menu():
    """Главное меню администратора"""
    builder = ReplyKeyboardBuilder()

    categories = [
        "Экскурсии",
        "Записи",
        "Статистика",
        "Капитаны",
        "Клиенты",
        "Промокоды",
        "Финансы",
        "Уведомления",
        "Настройки",
        "Выход"
    ]

    for text in categories:
        builder.add(KeyboardButton(text=text))

    builder.adjust(3, 3, 2, 2)

    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите категорию..."
    )


# ===== ПОДМЕНЮ ДЛЯ КАЖДОЙ КАТЕГОРИИ =====

def excursions_submenu():
    """Подменю управления экскурсиями"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Список видов экскурсий",
        "Новый вид экскурсии",
        "Расписание экскурсий",
        "Добавить экскурсию в расписание",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def captains_submenu():
    """Подменю управления капитанами"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Список капитанов",
        "График работы",
        "Расчет зарплаты",
        "Добавить капитана",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def clients_submenu():
    """Подменю управления клиентами"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Поиск клиента",
        "Новые клиенты",
        "Добавить клиента",
        "Редактировать клиента",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def bookings_submenu():
    """Подменю управления записями"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Активные записи",
        "Неоплаченные",
        "Создать запись",
        "Отменить запись",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def statistics_submenu():
    """Подменю статистики"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Сегодня",
        "За месяц",
        "За период",
        "По экскурсиям",
        "По капитанам (за месяц)",
        "Отказы и неявки",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def finances_submenu():
    """Подменю финансов"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Сводка и текущие платежи",
        "Возвраты и проблемные операции",
        "ЮКасса: подключение и магазин",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def notifications_submenu():
    """Подменю уведомлений"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Отправить уведомление",
        "Напоминания",
        "Шаблоны сообщений",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def settings_submenu():
    """Подменю настроек"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Управление администраторами",
        "Файлы согласия на обработку ПД",
        "Настройки чеков 54-ФЗ",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, )
    return builder.as_markup(resize_keyboard=True)


# ===== ОБЩИЕ КНОПКИ =====

def back_button():
    """Кнопка Назад"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True
    )

def cancel_button():
    """Кнопка Отмена"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )


# ===== УПРАВЛЕНИЕ КАПИТАНАМИ =====

def find_client_for_captains() -> InlineKeyboardMarkup:
    """Инлайн-кнопка перехода к поиску клиента для произведения в капитаны"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Найти клиента", callback_data="new_client_search")
    return builder.as_markup()

def captains_list_keyboard(captains: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком капитанов"""
    builder = InlineKeyboardBuilder()

    for captain in captains:
        name = captain.full_name or captain.username or f"ID {captain.id}"
        builder.button(
            text=name,
            callback_data=f"captain_schedule_menu:{captain.id}"
        )

    builder.button(text="Назад", callback_data="back_to_captains_menu")
    builder.adjust(1)
    return builder.as_markup()

def captain_period_menu(captain_id: int, captain_name: str) -> InlineKeyboardMarkup:
    """Меню выбора периода для капитана"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Прошлый месяц", callback_data=f"captain_schedule:{captain_id}:last_month")
    builder.button(text="Текущий месяц", callback_data=f"captain_schedule:{captain_id}:current_month")
    builder.button(text="Все назначенные экскурсии", callback_data=f"captain_schedule:{captain_id}:all_assigned")
    builder.button(text="Назад к списку капитанов", callback_data="back_to_captains_list")
    builder.adjust(1)
    return builder.as_markup()

def back_to_captains_list_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата к списку капитанов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад к списку капитанов", callback_data="back_to_captains_list")
    builder.adjust(1)
    return builder.as_markup()


# ===== ДОБАВЛЕНИЕ КЛИЕНТА =====

def add_client_confirmation(client_data: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения данных клиента перед сохранением

    Args:
        client_data: Словарь с данными клиента (имя, фамилия, телефон, дата рождения, вес)
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Подтвердить",
        callback_data="confirm_add_client"
    )
    builder.button(
        text="Изменить данные",
        callback_data="edit_client_data"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_add_client"
    )

    builder.adjust(2, 1)
    return builder.as_markup()


# ===== РЕДАКТИРОВАНИЕ КЛИЕНТА =====

def client_selection_menu(clients: list) -> InlineKeyboardMarkup:
    """
    Меню выбора клиента из результатов поиска

    Args:
        clients: Список объектов User (найденные клиенты)
    """
    builder = InlineKeyboardBuilder()

    for client in clients:
        # Текст кнопки: ID и имя (обрезаем если слишком длинное)
        name = client.full_name
        if len(name) > 25:
            name = name[:22] + "..."

        builder.button(
            text=f"{client.id}: {name}",
            callback_data=f"select_client_for_edit:{client.id}"
        )

    builder.button(
        text="Новый поиск",
        callback_data="search_client_again"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_client_edit"
    )

    builder.adjust(1)
    return builder.as_markup()

def client_or_child_selection_menu(client: User, children: list) -> InlineKeyboardMarkup:
    """
    Меню выбора: редактировать самого клиента или его ребенка

    Args:
        client: Объект User (клиент)
        children: Список объектов User (дети клиента)
    """
    builder = InlineKeyboardBuilder()

    # Кнопка для редактирования самого клиента
    client_name = client.full_name
    if len(client_name) > 30:
        client_name = client_name[:27] + "..."

    builder.button(
        text=f"Самого клиента: {client_name}",
        callback_data=f"edit_target:client:{client.id}"
    )

    # Кнопки для каждого ребенка
    for child in children:
        child_name = child.full_name
        if len(child_name) > 25:
            child_name = child_name[:22] + "..."

        age_text = f"{child.age} лет" if child.age else "возраст неизвестен"
        builder.button(
            text=f"Ребенок: {child_name} ({age_text})",
            callback_data=f"edit_target:child:{child.id}"
        )

    builder.button(
        text="Отмена",
        callback_data="cancel_client_edit"
    )

    builder.adjust(1)
    return builder.as_markup()

def client_edit_fields_menu(target_id: int, target_type: str, has_phone: bool = True) -> InlineKeyboardMarkup:
    """
    Меню выбора поля для редактирования

    Args:
        target_id: ID пользователя (клиента или ребенка)
        target_type: Тип цели ("client" или "child")
        has_phone: Есть ли поле телефона (для клиентов есть, для детей нет)
    """
    builder = InlineKeyboardBuilder()

    # Базовые поля для всех
    fields = [
        ("Фамилия", f"edit_field:{target_id}:{target_type}:surname"),
        ("Имя", f"edit_field:{target_id}:{target_type}:name"),
        ("Дата рождения", f"edit_field:{target_id}:{target_type}:birth_date"),
        ("Email", f"edit_field:{target_id}:{target_type}:email"),
        ("Адрес", f"edit_field:{target_id}:{target_type}:address"),
        ("Вес", f"edit_field:{target_id}:{target_type}:weight")
    ]

    # Добавляем телефон только для клиентов
    if has_phone:
        fields.insert(2, ("Телефон", f"edit_field:{target_id}:{target_type}:phone"))

    for text, callback in fields:
        builder.button(text=text, callback_data=callback)

    builder.button(
        text="Отмена",
        callback_data="cancel_client_edit"
    )

    builder.adjust(2)
    return builder.as_markup()

def cancel_inline_button() -> InlineKeyboardMarkup:
    """Инлайн-кнопка Отмена"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="cancel_client_edit")
    return builder.as_markup()


# ===== РАБОТА С КЛИЕНТАМИ =====

def client_actions(client_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура действий с выбранным клиентом

    Args:
        client_id: ID клиента
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Изменить статус (повысить/понизить)",
        callback_data=f"change_client_role:{client_id}"
    )
    builder.button(
        text="Редактировать данные",
        callback_data=f"edit_client:{client_id}"
    )
    builder.button(
        text="Отправить сообщение",
        callback_data=f"send_message_to_client:{client_id}"
    )
    builder.button(
        text="Показать детей",
        callback_data=f"show_client_children:{client_id}"
    )
    builder.button(
        text="Назад в меню",
        callback_data="back_to_clients_menu"
    )

    builder.adjust(1)  # Все кнопки в столбик
    return builder.as_markup()

def client_list(clients: list) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора клиента из списка

    Args:
        clients: Список объектов User (только с ролью client)
    """
    builder = InlineKeyboardBuilder()

    for client in clients:
        name = client.full_name
        if len(name) > 25:
            name = name[:22] + "..."

        phone = client.phone_number
        if len(phone) > 15:
            phone = phone[:12] + "..."

        button_text = f"{client.id}: {name} ({phone})"
        builder.button(
            text=button_text,
            callback_data=f"select_client:{client.id}"
        )

    builder.button(
        text="Новый поиск",
        callback_data="new_client_search"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_client_search"
    )

    # Каждая кнопка клиента в отдельном ряду, управляющие кнопки вместе
    rows = [1] * len(clients) + [2]
    builder.adjust(*rows)

    return builder.as_markup()

def client_role_change(client_id: int, current_role: str) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора новой роли для клиента

    Args:
        client_id: ID клиента
        current_role: Текущая роль (client, captain, admin)
    """
    builder = InlineKeyboardBuilder()

    # Доступные роли
    roles = [
        ("Клиент", "client"),
        ("Капитан", "captain"),
        ("Администратор", "admin")
    ]

    for role_name, role_value in roles:
        # Отмечаем текущую роль
        if role_value == current_role:
            text = f"✓ {role_name} (текущая)"
        else:
            text = role_name

        builder.button(
            text=text,
            callback_data=f"set_client_role:{client_id}:{role_value}"
        )

    builder.button(
        text="Отмена",
        callback_data=f"client_actions:{client_id}"
    )

    builder.adjust(1)
    return builder.as_markup()

def back_to_client_actions(client_id: int) -> InlineKeyboardMarkup:
    """
    Кнопка возврата к действиям с клиентом

    Args:
        client_id: ID клиента
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Назад к действиям",
        callback_data=f"client_actions:{client_id}"
    )
    return builder.as_markup()

def client_virtual_actions(client_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура действий с виртуальным клиентом

    Args:
        client_id: ID клиента
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Редактировать данные",
        callback_data=f"edit_client:{client_id}"
    )
    builder.button(
        text="Назад в меню клиентов",
        callback_data="back_to_clients_menu"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== УПРАВЛЕНИЕ ВИДАМИ ЭКСКУРСИЙ =====

def excursions_list(all_excursions: list, active_only: bool) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру со списком всех экскурсий.
    Сначала активные, затем неактивные.
    """
    keyboard = InlineKeyboardBuilder()

    # Разделяем экскурсии на активные и неактивные
    active_excursions = [exc for exc in all_excursions if exc.is_active]
    inactive_excursions = [exc for exc in all_excursions if not exc.is_active]

    # Добавляем заголовок для активных экскурсий, если они есть
    if active_excursions:
        if not active_only:
            keyboard.button(text="АКТИВНЫЕ ЭКСКУРСИИ", callback_data="no_action")

        # Добавляем кнопки активных экскурсий
        for excursion in active_excursions:
            cell_text = f"{excursion.id}: {excursion.name}"
            callback_data = f"excursion_actions:{excursion.id}"
            keyboard.button(text=cell_text, callback_data=callback_data)

    # Добавляем заголовок для неактивных экскурсий, если они есть и не фильтруем по active_only
    if inactive_excursions and not active_only:
        keyboard.button(text="НЕАКТИВНЫЕ ЭКСКУРСИИ", callback_data="no_action")

        # Добавляем кнопки неактивных экскурсий
        for excursion in inactive_excursions:
            cell_text = f"(x) {excursion.id}: {excursion.name}"
            callback_data = f"excursion_actions:{excursion.id}"
            keyboard.button(text=cell_text, callback_data=callback_data)

    # Добавляем управляющие кнопки
    keyboard.button(text="Добавить новую экскурсию", callback_data="create_excursion")
    keyboard.button(text="Назад", callback_data="back_to_exc_menu")

    # Настраиваем расположение:
    # Заголовки - по 1 в ряду, экскурсии - по 2 в ряду, управляющие кнопки - по 1 или 2
    # Сначала считаем количество рядов для правильной настройки
    rows = []

    # Добавляем заголовок активных
    if active_excursions and not active_only:
        rows.append(1)

    # Добавляем активные экскурсии
    if active_excursions:
        rows.append(len(active_excursions))

    # Добавляем заголовок неактивных
    if inactive_excursions and not active_only:
        rows.append(1)

    # Добавляем неактивные экскурсии
    if inactive_excursions and not active_only:
        rows.append(len(inactive_excursions))

    # Добавляем управляющие кнопки
    keyboard.adjust(*[1 if i == 0 else 2 for i in range(len(rows))], 2, 1)

    return keyboard.as_markup()

def excursion_actions_menu(excursion_id: int):
    """Действия с экскурсией"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Редактировать", callback_data=f"redact_exc_data:{excursion_id}"),
        InlineKeyboardButton(text="Статистика", callback_data=f"excursion_stats:{excursion_id}"),
        InlineKeyboardButton(text="Изменить статус", callback_data=f"toggle_excursion:{excursion_id}")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def excursion_redaction(exc_id:int):
    redact_reg_cell_list = (
    'Название',
    'Описание',
    'Продолжительность',
    'Стоимость',
    )

    redact_reg_collback_list = (
    f'redact_exc_name:{exc_id}',
    f'redact_exc_description:{exc_id}',
    f'redact_exc_duration:{exc_id}',
    f'redact_exc_price:{exc_id}',
    )
    keyboard = InlineKeyboardBuilder()

    for cell, callback in zip(redact_reg_cell_list, redact_reg_collback_list):
        keyboard.add(InlineKeyboardButton(text=cell, callback_data=callback))
    return keyboard.adjust(2).as_markup()

def end_add_excursion(exc_id:int):
    return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Отредактировать данные', callback_data=f'redact_exc_data:{exc_id}'),
     InlineKeyboardButton(text='В главное админ-меню', callback_data='back_to_admin_panel')],
])

def error_add_excursion():
    return ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Новая экскурсия')],
    [KeyboardButton(text='Главное меню')]],
    resize_keyboard=True
)

def excursion_management(excursion_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретной экскурсией

    Args:
        excursion_id: ID экскурсии
        is_active: Флаг активности экскурсии (True - активна, False - неактивна)
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Редактировать",
        callback_data=f"admin_excursion_edit:{excursion_id}"
    )
    builder.button(
        text="Просмотр",
        callback_data=f"admin_excursion_view:{excursion_id}"
    )
    builder.button(
        text="Расписание",
        callback_data=f"admin_excursion_schedule:{excursion_id}"
    )
    builder.button(
        text="Статистика",
        callback_data=f"admin_excursion_stats:{excursion_id}"
    )
    builder.button(
        text="Деактивировать" if is_active else "Активировать",
        callback_data=f"admin_excursion_toggle:{excursion_id}"
    )
    builder.button(
        text="Удалить",
        callback_data=f"admin_excursion_delete:{excursion_id}"
    )

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


# ===== ВРЕМЕННЫЕ СЛОТЫ =====

def slot_actions_menu(slot_id: int) -> InlineKeyboardMarkup:
    """Действия с конкретным слотом"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Просмотреть детали", callback_data=f"slot_details:{slot_id}"),
        InlineKeyboardButton(text="Назначить капитана", callback_data=f"assign_captain:{slot_id}"),
        InlineKeyboardButton(text="Перенести", callback_data=f"reschedule_slot:{slot_id}"),
        InlineKeyboardButton(text="Отменить", callback_data=f"cancel_slot:{slot_id}"),
        InlineKeyboardButton(text="Назад к расписанию", callback_data="back_to_schedule_menu")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def slot_confirmation_menu(slot_id: int, action: str) -> InlineKeyboardMarkup:
    """Меню подтверждения действий со слотом"""
    builder = InlineKeyboardBuilder()

    action_texts = {
        "cancel": ("Отменить слот", "confirm_cancel_slot"),
        "complete": ("Завершить экскурсию", "confirm_complete_slot"),
        "reschedule": ("Перенести", "confirm_reschedule_slot")
    }

    if action not in action_texts:
        return back_button()

    button_text, callback_prefix = action_texts[action]

    builder.add(
        InlineKeyboardButton(text=button_text, callback_data=f"{callback_prefix}:{slot_id}"),
        InlineKeyboardButton(text="Вернуться", callback_data=f"manage_slot:{slot_id}")
    )

    builder.adjust(1)
    return builder.as_markup()

def excursions_selection_menu_for_schedule(
    excursions: list,
    back_callback: str = "back_to_schedule_menu",
    button_callback_prefix: str = "schedule_select_exc"
) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора экскурсий для назначения в расписание

    Args:
        excursions: Список объектов Excursion
        back_callback: Callback_data для кнопки "Назад"
        button_callback_prefix: Префикс для callback_data кнопок выбора экскурсии
    """
    builder = InlineKeyboardBuilder()

    for excursion in excursions:
        builder.button(
            text=f"{excursion.name} ({excursion.base_duration_minutes} мин.)",
            callback_data=f"{button_callback_prefix}:{excursion.id}"
        )

    builder.button(
        text="Назад",
        callback_data=back_callback
    )

    builder.adjust(1)
    return builder.as_markup()

def schedule_exc_management_menu() -> InlineKeyboardMarkup:
    """Меню управления расписанием"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Расписание на неделю", callback_data="schedule_week"),
        InlineKeyboardButton(text="Расписание конкретной даты", callback_data="view_schedule_by_date"),
        InlineKeyboardButton(text="Добавить в расписание", callback_data="add_to_schedule"),
        InlineKeyboardButton(text="Назад в меню экскурсий", callback_data="back_to_exc_menu")
    )

    builder.adjust(2, 2)
    return builder.as_markup()

def time_slot_menu(slot_date: str, excursion_id: int) -> InlineKeyboardMarkup:
    """Меню выбора времени для слота"""
    builder = InlineKeyboardBuilder()

    # Стандартные временные слоты
    time_slots = [
        "09:00", "10:00", "11:00", "12:00",
        "13:00", "14:00", "15:00", "16:00",
        "17:00", "18:00", "19:00", "20:00"
    ]

    for time_slot in time_slots:
        builder.add(
            InlineKeyboardButton(
                text=time_slot,
                callback_data=f"select_time;{slot_date};{excursion_id};{time_slot}"
            )
        )

    builder.add(
        InlineKeyboardButton(text="Другое время", callback_data=f"custom_time:{slot_date}:{excursion_id}"),
        InlineKeyboardButton(text="Назад", callback_data="add_to_schedule")
    )

    builder.adjust(3, 3, 3, 3, 1, 1)
    return builder.as_markup()

def slot_action_confirmation_menu(
    slot_id: int,
    action: str,
    action_text: str = None,
    back_callback: str = None
) -> InlineKeyboardMarkup:
    """
    Универсальное меню подтверждения действий со слотом

    Args:
        slot_id: ID слота
        action: Тип действия (cancel, complete, reschedule)
        action_text: Текст для кнопки подтверждения (если не указан, используется стандартный)
        back_callback: Callback_data для кнопки возврата (если не указан, используется manage_slot)
    """
    builder = InlineKeyboardBuilder()

    # Стандартные тексты для разных действий
    action_texts = {
        "cancel": ("Да, отменить слот", "confirm_cancel_slot"),
        "complete": ("Да, завершить экскурсию", "confirm_complete_slot"),
        "reschedule": ("Да, перенести", "confirm_reschedule_slot")
    }

    # Получаем текст и префикс callback_data
    if action in action_texts and action_text is None:
        button_text, callback_prefix = action_texts[action]
    else:
        button_text = action_text or "Подтвердить"
        callback_prefix = f"confirm_{action}"

    # Кнопка подтверждения
    builder.button(
        text=button_text,
        callback_data=f"{callback_prefix}:{slot_id}"
    )

    # Кнопка возврата
    if back_callback is None:
        back_callback = f"manage_slot:{slot_id}"

    builder.button(
        text="Нет, вернуться",
        callback_data=back_callback
    )

    builder.adjust(1)
    return builder.as_markup()

def captains_selection_menu(
    item_id: int,
    captains: list,
    callback_prefix: str = "select_captain_for_slot",
    include_back: bool = True,
    back_callback: str = None,
    include_remove: bool = False,
    remove_callback: str = None
) -> InlineKeyboardMarkup:
    """
    Универсальное меню выбора капитана

    Args:
        item_id: ID элемента (слота, экскурсии и т.д.)
        captains: Список объектов User (капитанов)
        callback_prefix: Префикс для callback_data
        include_back: Включать ли кнопку "Назад"
        back_callback: Callback_data для кнопки "Назад"
        include_remove: Включать ли кнопку "Снять капитана"
        remove_callback: Callback_data для кнопки "Снять капитана"
    """
    builder = InlineKeyboardBuilder()

    if not captains:
        builder.add(
            InlineKeyboardButton(
                text="Нет доступных капитанов",
                callback_data="no_captains"
            )
        )
    else:
        for captain in captains:
            builder.add(
                InlineKeyboardButton(
                    text=f"{captain.full_name}",
                    callback_data=f"{callback_prefix}:{item_id}:{captain.id}"
                )
            )

    # Кнопка "Снять капитана" (если нужно)
    if include_remove and remove_callback:
        builder.add(
            InlineKeyboardButton(
                text="Снять капитана",
                callback_data=remove_callback
            )
        )

    # Кнопка "Назад" (если нужно)
    if include_back:
        if back_callback is None:
            back_callback = f"manage_slot:{item_id}"

        builder.add(
            InlineKeyboardButton(
                text="Назад",
                callback_data=back_callback
            )
        )

    builder.adjust(1)
    return builder.as_markup()

def no_captains_options_menu(slot_id: int = None, context: str = "create") -> InlineKeyboardMarkup:
    """Меню при отсутствии капитанов"""
    builder = InlineKeyboardBuilder()

    if context == "reschedule" and slot_id:
        # Для переноса слота
        builder.add(
            InlineKeyboardButton(
                text="Перенести без капитана",
                callback_data=f"reschedule_without_captain:{slot_id}"
            ),
            InlineKeyboardButton(
                text="Выбрать другое время",
                callback_data=f"reschedule_new_time:{slot_id}"
            ),
            InlineKeyboardButton(
                text="Отменить перенос",
                callback_data=f"cancel_reschedule:{slot_id}"
            )
        )
    else:
        # Для создания нового слота
        builder.add(
            InlineKeyboardButton(
                text="Создать без капитана",
                callback_data="create_without_captain"
            ),
            InlineKeyboardButton(
                text="Выбрать другое время",
                callback_data="change_time"
            ),
            InlineKeyboardButton(
                text="Отменить создание",
                callback_data="cancel_slot_creation"
            )
        )

    builder.adjust(1)
    return builder.as_markup()

def slots_conflict_keyboard(slot_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для решения конфликта слотов"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="Ввести другое время",
            callback_data=f"reschedule_new_time:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Показать конфликтный слот",
            callback_data=f"show_conflict_slot:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Отменить перенос",
            callback_data=f"cancel_reschedule:{slot_id}"
        )
    )

    builder.adjust(1)
    return builder.as_markup()

def captain_conflict_keyboard(slot_id: int) -> InlineKeyboardMarkup:
    """Клавиатура при занятости капитана"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="Ввести другое время",
            callback_data=f"reschedule_new_time:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Назначить другого капитана",
            callback_data=f"change_captain:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Показать свободных капитанов",
            callback_data=f"show_available_captains:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Отменить перенос",
            callback_data=f"cancel_reschedule:{slot_id}"
        )
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== МЕНЮ РАСПИСАНИЯ =====

def schedule_view_options() -> InlineKeyboardMarkup:
    """Опции просмотра расписания"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="На сегодня", callback_data="schedule_today"),
        InlineKeyboardButton(text="На завтра", callback_data="schedule_tomorrow"),
        InlineKeyboardButton(text="На неделю вперед", callback_data="schedule_week"),
        InlineKeyboardButton(text="На месяц вперед", callback_data="schedule_month"),
        InlineKeyboardButton(text="Выбрать дату", callback_data="view_schedule_by_date"),
        InlineKeyboardButton(text="Назад", callback_data="back_to_schedule_menu")
    )

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def schedule_back_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню расписания"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Назад в меню расписания", callback_data="back_to_schedule_menu"),
        InlineKeyboardButton(text="В меню экскурсий", callback_data="back_to_exc_menu")
    )

    builder.adjust(1)
    return builder.as_markup()

def schedule_date_management_menu(slots: list, target_date: date) -> InlineKeyboardMarkup:
    """
    Клавиатура для управления слотами на конкретную дату

    Args:
        slots: Список объектов ExcursionSlot
        target_date: Дата для которой показывается расписание
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для управления слотами
    for slot in slots:
        if slot.status == SlotStatus.scheduled:
            builder.button(
                text=f"Управлять слотом {slot.id}",
                callback_data=f"manage_slot:{slot.id}"
            )

    # Кнопка для добавления экскурсии на эту дату
    builder.button(
        text="Добавить экскурсию на эту дату",
        callback_data=f"add_to_date:{target_date.strftime('%Y-%m-%d')}"
    )

    # Кнопка возврата
    builder.button(
        text="Назад в меню расписания",
        callback_data="back_to_schedule_menu"
    )

    builder.adjust(1)
    return builder.as_markup()

def schedule_week_management_menu(slots_by_date: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура для управления расписанием на неделю

    Args:
        slots_by_date: Словарь {дата: [слоты]}
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для выбора конкретной даты для управления
    for slot_date in sorted(slots_by_date.keys()):
        date_str = slot_date.strftime('%d.%m.%Y')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"Управлять {date_str} ({slots_count} слотов)",
            callback_data=f"manage_date_slots:{slot_date.strftime('%Y-%m-%d')}"
        )

    # Кнопка добавления экскурсии
    builder.button(
        text="Добавить экскурсию в расписание",
        callback_data="add_to_schedule"
    )

    # Кнопка возврата
    builder.button(
        text="Назад в меню расписания",
        callback_data="back_to_schedule_menu"
    )

    builder.adjust(1)
    return builder.as_markup()

def schedule_month_management_menu(slots_by_date: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура для управления расписанием на месяц

    Args:
        slots_by_date: Словарь {дата: [слоты]}
    """
    builder = InlineKeyboardBuilder()

    # Показываем первые 7 дат для управления
    sorted_dates = sorted(slots_by_date.keys())[:7]

    for slot_date in sorted_dates:
        date_str = slot_date.strftime('%d.%m.%Y')
        weekday = slot_date.strftime('%a')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"{date_str} ({weekday}) - {slots_count} сл.",
            callback_data=f"manage_date_slots:{slot_date.strftime('%Y-%m-%d')}"
        )

    # Если есть еще даты
    if len(slots_by_date) > 7:
        builder.button(
            text=f"Показать еще {len(slots_by_date) - 7} дней...",
            callback_data="show_more_month_dates"
        )

    # Общие кнопки
    builder.button(
        text="Добавить экскурсию в расписание",
        callback_data="add_to_schedule"
    )

    builder.button(
        text="Выбрать конкретную дату",
        callback_data="view_schedule_by_date"
    )

    builder.button(
        text="Назад в меню расписания",
        callback_data="back_to_schedule_menu"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== ПРОМОКОДЫ =====

def promocodes_menu() -> InlineKeyboardMarkup:
    """Меню управления промокодами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Создать промокод", callback_data="create_promocode"),
        InlineKeyboardButton(text="Управление промокодами", callback_data="list_promocodes"),
        InlineKeyboardButton(text="Неактивные промокоды", callback_data="archive_promocodes"),
        InlineKeyboardButton(text="Статистика промокодов", callback_data="promocodes_stats"),
        InlineKeyboardButton(text="В главное админ-меню", callback_data="back_to_admin_panel")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def promo_type_selection_menu() -> InlineKeyboardMarkup:
    """Меню выбора типа скидки для промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Скидка в процентах", callback_data="promo_type:percent"),
        InlineKeyboardButton(text="Скидка точной суммой", callback_data="promo_type:fixed"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel_promo_creation")
    )
    builder.adjust(1)
    return builder.as_markup()

def promo_duration_selection_menu(
    include_cancel: bool = True,
    cancel_callback: str = "cancel_promo_creation",
    include_back: bool = False,
    back_callback: str = "edit_promo_data"
) -> InlineKeyboardMarkup:
    """
    Меню выбора срока действия промокода с гибкими параметрами

    Args:
        include_cancel: Включать ли кнопку отмены
        cancel_callback: Callback_data для кнопки отмены
        include_back: Включать ли кнопку возврата
        back_callback: Callback_data для кнопки возврата
    """
    builder = InlineKeyboardBuilder()

    # Основные кнопки выбора срока
    builder.add(
        InlineKeyboardButton(text="1 день", callback_data="promo_duration:1"),
        InlineKeyboardButton(text="7 дней", callback_data="promo_duration:7"),
        InlineKeyboardButton(text="30 дней", callback_data="promo_duration:30"),
        InlineKeyboardButton(text="90 дней", callback_data="promo_duration:90"),
        InlineKeyboardButton(text="Бессрочно", callback_data="promo_duration:0"),
        InlineKeyboardButton(text="Другой срок", callback_data="promo_custom_duration")
    )

    # Дополнительные кнопки
    if include_back:
        builder.add(InlineKeyboardButton(text="Назад", callback_data=back_callback))

    if include_cancel:
        builder.add(InlineKeyboardButton(text="Отмена", callback_data=cancel_callback))

    # Настраиваем расположение
    if include_back and include_cancel:
        builder.adjust(2, 2, 1, 1, 1, 2)
    elif include_back or include_cancel:
        builder.adjust(2, 2, 1, 1, 1)
    else:
        builder.adjust(2, 2, 1, 1)

    return builder.as_markup()

def promo_creation_confirmation_menu() -> InlineKeyboardMarkup:
    """Меню подтверждения создания промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Да, создать промокод", callback_data="confirm_create_promo"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel_promo_creation")
    )

    builder.adjust(1)
    return builder.as_markup()

def promo_edit_field_menu() -> InlineKeyboardMarkup:
    """Меню выбора поля промокода для редактирования"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Код промокода", callback_data="edit_promo_field:code"),
        InlineKeyboardButton(text="Тип скидки", callback_data="edit_promo_field:type"),
        InlineKeyboardButton(text="Значение скидки", callback_data="edit_promo_field:value"),
        InlineKeyboardButton(text="Описание", callback_data="edit_promo_field:description"),
        InlineKeyboardButton(text="Лимит использований", callback_data="edit_promo_field:limit"),
        InlineKeyboardButton(text="Срок действия", callback_data="edit_promo_field:duration"),
        InlineKeyboardButton(text="Назад к сводке", callback_data="back_to_promo_summary")
    )

    builder.adjust(1)
    return builder.as_markup()

def promo_list(promocodes: list) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком активных промокодов для выбора

    Args:
        promocodes: Список объектов PromoCode
    """
    builder = InlineKeyboardBuilder()

    active_promos = [p for p in promocodes if p.is_valid]

    if active_promos:
        # Заголовок
        builder.button(
            text="АКТИВНЫЕ ПРОМОКОДЫ",
            callback_data="no_action"
        )

        # Активные промокоды
        for promo in active_promos:
            # Определяем тип скидки для отображения
            if promo.discount_type == DiscountType.percent:
                discount_text = f"{promo.discount_value}%"
            else:
                discount_text = f"{promo.discount_value} руб."

            # Формируем текст кнопки
            button_text = f"{promo.code} | {discount_text}"

            # Обрезаем если слишком длинное
            if len(button_text) > 40:
                button_text = button_text[:37] + "..."

            builder.button(
                text=button_text,
                callback_data=f"select_promo:{promo.id}"
            )
    else:
        builder.button(
            text="Нет активных промокодов",
            callback_data="no_action"
        )

    # Кнопка для показа неактивных промокодов
    builder.button(
        text="Показать неактивные промокоды",
        callback_data="archive_promocodes"
    )

    # Управляющие кнопки
    builder.button(
        text="Назад в меню промокодов",
        callback_data="back_to_promo_menu"
    )

    # Настраиваем расположение
    rows = [1]  # заголовок или сообщение об отсутствии
    if active_promos:
        rows.extend([1] * len(active_promos))
    rows.append(1)  # кнопка показа неактивных
    rows.append(1)  # кнопка назад

    builder.adjust(*rows)
    return builder.as_markup()

def promo_actions(promo_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура действий с конкретным промокодом

    Args:
        promo_id: ID промокода
        is_active: Активен ли промокод в данный момент
    """
    builder = InlineKeyboardBuilder()

    # Статистика использования
    builder.button(
        text="Статистика",
        callback_data=f"promo_stats:{promo_id}"
    )

    # Редактирование (только для активных)
    if is_active:
        builder.button(
            text="Редактировать",
            callback_data=f"edit_promo:{promo_id}"
        )

    # Завершение действия (только для активных)
    if is_active:
        builder.button(
            text="Завершить действие",
            callback_data=f"deactivate_promo:{promo_id}"
        )

    # Навигация
    builder.button(
        text="К списку промокодов",
        callback_data="back_to_promo_list"
    )

    builder.button(
        text="В меню промокодов",
        callback_data="back_to_promo_menu"
    )

    # Настраиваем расположение: основные кнопки по 1, навигация вместе
    if is_active:
        builder.adjust(1, 1, 1, 2)
    else:
        builder.adjust(1, 1, 1)

    return builder.as_markup()

def deactivate_promo_confirm(promo_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения деактивации промокода

    Args:
        promo_id: ID промокода
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Да, завершить действие",
        callback_data=f"confirm_deactivate_promo:{promo_id}"
    )

    builder.button(
        text="Нет, отмена",
        callback_data=f"promo_actions:{promo_id}"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== МЕНЮ НАСТРОЕК =====

def concent_files_menu() -> InlineKeyboardMarkup:
    """Меню для управления файлами согласия"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Смотреть имеющиеся файлы",
        callback_data="concent_view_files"
    )
    builder.button(
        text="Информация о всех файлах в БД",
        callback_data="concent_view_all_files"
    )
    builder.button(
        text="Загрузить/заменить файл",
        callback_data="concent_upload_menu"
    )
    builder.button(
        text="Назад в настройки",
        callback_data="admin_settings"
    )

    builder.adjust(1)
    return builder.as_markup()

def concent_upload_menu() -> InlineKeyboardMarkup:
    """Меню выбора типа файла для загрузки"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Согласие для взрослых",
        callback_data="concent_upload_adult"
    )
    builder.button(
        text="Согласие для несовершеннолетних",
        callback_data="concent_upload_minor"
    )
    builder.button(
        text="Другой файл (OTHER)",
        callback_data="concent_upload_other"
    )
    builder.button(
        text="Назад",
        callback_data="concent_files"
    )

    builder.adjust(1)
    return builder.as_markup()

def concent_back_menu() -> InlineKeyboardMarkup:
    """Кнопка назад в меню файлов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="concent_files")
    return builder.as_markup()

def concent_cancel_menu() -> InlineKeyboardMarkup:
    """Кнопка отмены загрузки файла"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="concent_files")
    return builder.as_markup()

def concent_file_selection_menu(
    adult_file: Optional[TelegramFile] = None,
    minor_file: Optional[TelegramFile] = None,
    other_files_count: int = 0
) -> InlineKeyboardMarkup:
    """Меню выбора файла для просмотра"""
    builder = InlineKeyboardBuilder()

    if adult_file:
        # Обрезаем длинное имя файла
        adult_name = adult_file.file_name
        if len(adult_name) > 20:
            adult_name = adult_name[:17] + "..."
        builder.button(
            text=f"Согласие для взрослых ({adult_name})",
            callback_data=f"concent_send_{FileType.CPD.value}"
        )
    else:
        builder.button(
            text="Согласие для взрослых (не загружено)",
            callback_data="concent_no_file_adult"
        )

    if minor_file:
        # Обрезаем длинное имя файла
        minor_name = minor_file.file_name
        if len(minor_name) > 20:
            minor_name = minor_name[:17] + "..."
        builder.button(
            text=f"Согласие для несовершеннолетних ({minor_name})",
            callback_data=f"concent_send_{FileType.CPD_MINOR.value}"
        )
    else:
        builder.button(
            text="Согласие для несовершеннолетних (не загружено)",
            callback_data="concent_no_file_minor"
        )

    # Добавляем другие файлы если есть
    if other_files_count > 0:
        builder.button(
            text=f"Другие файлы ({other_files_count} шт.)",
            callback_data="concent_view_other_files"
        )

    builder.button(text="Назад", callback_data="concent_files")
    builder.adjust(1)

    return builder.as_markup()

def receipt_settings_menu(
    send_receipt: bool,
    vat_rate: int,
    tax_system_code: int
) -> InlineKeyboardMarkup:
    """Меню настроек чеков 54-ФЗ"""
    builder = InlineKeyboardBuilder()

    # Статус отправки чеков
    status_text = "Включена" if send_receipt else "Выключена"
    builder.button(
        text=f"Отправка чеков: {status_text}",
        callback_data="receipt_toggle_send"
    )

    # Ставка НДС
    vat_text = {
        0: "0% (без НДС)",
        5: "5%",
        7: "7%",
        10: "10%",
        22: "22%"
    }.get(vat_rate, f"{vat_rate}%")
    builder.button(
        text=f"Ставка НДС: {vat_text}",
        callback_data="receipt_set_vat"
    )

    # Система налогообложения
    tax_text = {
        1: "ОСН",
        2: "УСН (доходы)",
        3: "УСН (доходы минус расходы)",
        4: "ЕНВД",
        5: "ЕСН",
        6: "Патент"
    }.get(tax_system_code, f"Код {tax_system_code}")
    builder.button(
        text=f"Система налогообложения: {tax_text}",
        callback_data="receipt_set_tax"
    )

    builder.button(text="Назад в настройки", callback_data="admin_settings")
    builder.adjust(1)

    return builder.as_markup()

def vat_rate_selection_menu(current_rate: int) -> InlineKeyboardMarkup:
    """Меню выбора ставки НДС"""
    builder = InlineKeyboardBuilder()

    rates = [0, 5, 7, 10, 22]
    rate_names = {
        0: "0% (без НДС)",
        5: "5%",
        7: "7%",
        10: "10%",
        22: "22%"
    }

    for rate in rates:
        text = rate_names[rate]
        if rate == current_rate:
            text = f"✓ {text}"
        builder.button(
            text=text,
            callback_data=f"receipt_set_vat_{rate}"
        )

    builder.button(text="Назад", callback_data="receipt_settings")
    builder.adjust(1)

    return builder.as_markup()

def tax_system_selection_menu(current_code: int) -> InlineKeyboardMarkup:
    """Меню выбора системы налогообложения"""
    builder = InlineKeyboardBuilder()

    systems = {
        1: "ОСН",
        2: "УСН (доходы)",
        3: "УСН (доходы минус расходы)",
        4: "ЕНВД",
        5: "ЕСН",
        6: "Патент"
    }

    for code, name in systems.items():
        text = name
        if code == current_code:
            text = f"✓ {text}"
        builder.button(
            text=text,
            callback_data=f"receipt_set_tax_{code}"
        )

    builder.button(text="Назад", callback_data="receipt_settings")
    builder.adjust(1)

    return builder.as_markup()


# ===== МЕНЮ СТАТИСТИКИ =====


def dashboard_quick_actions():
    """Быстрые действия для дашборда"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Неоплаченные брони",
        callback_data="show_unpaid_bookings"
    )
    builder.button(
        text="Свободные капитаны",
        callback_data="show_free_captains"
    )
    builder.button(
        text="Ближайшие слоты",
        callback_data="show_near_slots"
    )
    builder.button(
        text="Новые клиенты",
        callback_data="show_new_clients"
    )
    builder.button(
        text="Активные записи",
        callback_data="show_active_bookings"
    )
    builder.button(
        text="Обновить дашборд",
        callback_data="refresh_dashboard"
    )

    builder.adjust(2)  # 2 кнопки в ряд

    return builder.as_markup()


# ===== СОЗДАНИЕ БРОНИРОВАНИЯ НА СЛОТ =====


def create_booking_client_choice() -> ReplyKeyboardMarkup:
    """Клавиатура выбора типа клиента для создания записи"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Найти существующего",
        "Создать нового",
        "Последние клиенты",
        "Отмена"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def client_list_for_booking(clients: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора клиента из списка для создания записи"""
    builder = InlineKeyboardBuilder()

    for client in clients:
        name = client.full_name
        if len(name) > 25:
            name = name[:22] + "..."

        phone = client.phone_number
        if len(phone) > 15:
            phone = phone[:12] + "..."

        button_text = f"{client.id}: {name} ({phone})"
        builder.button(
            text=button_text,
            callback_data=f"select_client_for_booking:{client.id}"
        )

    builder.button(
        text="Новый поиск",
        callback_data="new_client_search_for_booking"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()

def excursion_list_for_booking(excursions: list) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора экскурсии для создания записи

    Args:
        excursions: Список объектов Excursion (только активные)
    """
    builder = InlineKeyboardBuilder()

    for excursion in excursions:
        text = f"{excursion.name} ({excursion.base_price} руб.)"
        builder.button(
            text=text,
            callback_data=f"select_excursion_for_booking:{excursion.id}"
        )

    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()

def slot_list_for_booking(slots: list, excursion_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора слота для создания записи

    Args:
        slots: Список объектов ExcursionSlot
        excursion_id: ID экскурсии для возврата
    """
    builder = InlineKeyboardBuilder()

    for slot in slots:

        # Форматируем время
        time_str = slot.start_datetime.strftime("%H:%M")
        date_str = slot.start_datetime.strftime("%d.%m")

        # Получаем капитана
        captain_name = slot.captain.full_name if slot.captain else "без капитана"

        # Получаем свободные места (будет обновлено позже)
        text = f"{date_str} {time_str} - {captain_name}"

        builder.button(
            text=text,
            callback_data=f"select_slot_for_booking:{slot.id}"
        )

    builder.button(
        text="Другая дата",
        callback_data=f"another_date_for_booking:{excursion_id}"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()

def admin_children_selection(children: list, selected_ids: list = None, max_children: int = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора детей для бронирования (админ-версия)
    Args:
        children: Список объектов User (дети)
        selected_ids: Список уже выбранных ID детей
        max_children: Максимальное количество детей для выбора
    """
    builder = InlineKeyboardBuilder()

    if selected_ids is None:
        selected_ids = []

    # Информация о количестве (если есть ограничение)
    if max_children:
        builder.button(
            text=f"Выбрано детей: {len(selected_ids)}/{max_children}",
            callback_data="no_action"
        )

    # Кнопки существующих детей
    for child in children:
        # Возраст для информации
        age_info = ""
        if child.date_of_birth:
            today = date.today()
            age = today.year - child.date_of_birth.year
            age_info = f" ({age} лет)"

        # Вес если есть
        weight_info = f", вес: {child.weight}кг" if child.weight else ""

        # Отметка выбранного
        prefix = "✓ " if child.id in selected_ids else ""
        button_text = f"{prefix}{child.full_name}{age_info}{weight_info}"

        builder.button(
            text=button_text,
            callback_data=f"admin_toggle_child:{child.id}"
        )

    # Кнопка создания виртуального ребенка
    builder.button(
        text="Создать виртуального ребенка",
        callback_data="admin_create_virtual_child"
    )

    # Кнопка завершения
    builder.button(
        text="Завершить выбор детей",
        callback_data="admin_finish_children_selection"
    )

    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    # Настройка расположения
    if max_children:
        builder.adjust(1, *([1] * len(children)), 1, 1, 1)
    else:
        builder.adjust(*([1] * len(children)), 1, 1, 1)

    return builder.as_markup()

def admin_child_weight(child_index: int, total_children: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для ввода веса ребенка (админ-версия)

    Args:
        child_index: Индекс текущего ребенка (для навигации)
        total_children: Общее количество детей
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Пропустить (вес не указывать)",
        callback_data=f"admin_skip_child_weight:{child_index}"
    )

    if child_index < total_children - 1:
        builder.button(
            text="Далее",
            callback_data=f"admin_next_child_weight:{child_index + 1}"
        )

    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()

def admin_virtual_child_form_navigation() -> InlineKeyboardMarkup:
    """Клавиатура навигации при создании виртуального ребенка"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Отмена",
        callback_data="admin_cancel_virtual_child"
    )

    builder.adjust(1)
    return builder.as_markup()

def admin_confirm_virtual_child() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения создания виртуального ребенка"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Подтвердить",
        callback_data="admin_confirm_virtual_child"
    )
    builder.button(
        text="Изменить данные",
        callback_data="admin_edit_virtual_child"
    )
    builder.button(
        text="Отмена",
        callback_data="admin_cancel_virtual_child"
    )

    builder.adjust(1)
    return builder.as_markup()

def create_virtual_child() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Создать виртуального ребенка",
        callback_data="admin_create_virtual_child"
    )
    builder.button(
        text="Только взрослый (без детей)",
        callback_data="admin_no_children"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()

def cancel_create_virtual_child() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Отмена",
        callback_data="admin_cancel_virtual_child"
    )

    builder.adjust(1)
    return builder.as_markup()

def continue_booking_with_excess_weight() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Продолжить (игнорировать вес)", callback_data="admin_continue_booking")
    builder.button(text="Изменить выбор детей", callback_data="admin_back_to_children_selection")
    builder.button(text="Отмена", callback_data="cancel_booking_creation")
    builder.adjust(1)
    return builder.as_markup()

def confirm_booking() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить и создать запись", callback_data="admin_confirm_booking_final")
    builder.button(text="Изменить данные", callback_data="admin_back_to_children_selection")
    builder.button(text="Отмена", callback_data="cancel_booking_creation")
    builder.adjust(1)
    return builder.as_markup()

def slot_already_booked(excursion_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для случая, когда у клиента уже есть бронь на этот слот

    Args:
        excursion_id: ID экскурсии для возврата к выбору другой даты
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Выбрать другой слот",
        callback_data=f"another_date_for_booking:{excursion_id}"
    )
    builder.button(
        text="Отмена",
        callback_data="cancel_booking_creation"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== ВОЗВРАТ СРЕДСТВ =====

def refunds_admin_menu() -> InlineKeyboardMarkup:
    """Меню управления возвратами"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Неудачные возвраты", callback_data="admin_failed_refunds")
    builder.button(text="Возврат по ID бронирования", callback_data="admin_refund_by_booking")
    builder.button(text="Назад в финансы", callback_data="finances_menu")
    builder.adjust(1)
    return builder.as_markup()

def refunds_list_keyboard(refunds: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком возвратов"""
    builder = InlineKeyboardBuilder()

    for refund in refunds[:10]:
        builder.button(
            text=f"Возврат #{refund.id} (бронь #{refund.booking_id}) - {refund.amount} руб.",
            callback_data=f"admin_refund_detail:{refund.id}"
        )

    builder.button(text="Назад в меню возвратов", callback_data="admin_refunds_menu")
    builder.adjust(1)
    return builder.as_markup()

def refund_detail_actions(refund_id: int, booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для деталей возврата"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Повторить попытку", callback_data=f"admin_retry_refund:{refund_id}")
    builder.button(
        text="Отметить как успешный (ручной возврат)",
        callback_data=f"admin_mark_refund_successful:{refund_id}:{booking_id}"
    )
    builder.button(
        text="Отметить как требующий ручного возврата",
        callback_data=f"admin_mark_refund_failed:{refund_id}"
    )
    builder.button(text="Назад к списку", callback_data="admin_failed_refunds")
    builder.adjust(1)
    return builder.as_markup()

def admin_mark_booking_refunded_menu(booking_id: int) -> InlineKeyboardMarkup:
    """Меню для отметки бронирования как возвращенного вручную"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, отметить возврат как успешный",
        callback_data=f"admin_mark_booking_refunded:{booking_id}"
    )
    builder.button(
        text="Нет, вернуться в меню",
        callback_data="admin_refunds_menu"
    )
    builder.adjust(1)
    return builder.as_markup()

def admin_mark_refund_successful_menu(refund_id: int, booking_id: int) -> InlineKeyboardMarkup:
    """Меню для отметки конкретного возврата как успешного"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Отметить возврат как успешный",
        callback_data=f"admin_mark_refund_successful:{refund_id}:{booking_id}"
    )
    builder.button(
        text="Назад к списку",
        callback_data="admin_failed_refunds"
    )
    builder.adjust(1)
    return builder.as_markup()

def back_to_admin_menu(back_callback: str) -> InlineKeyboardMarkup:
    """Кнопка возврата в админ-меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def admin_cancel_booking_with_refund_menu(booking_id: int) -> InlineKeyboardMarkup:
    """Меню отмены бронирования с возвратом для администратора"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Отменить с обычным возвратом",
        callback_data=f"admin_cancel_booking:{booking_id}:with_refund"
    )
    builder.button(
        text="Отменить с принудительным возвратом",
        callback_data=f"admin_cancel_booking:{booking_id}:with_force_refund"
    )
    builder.button(
        text="Отменить без возврата",
        callback_data=f"admin_cancel_booking:{booking_id}:without_refund"
    )
    builder.button(
        text="Назад",
        callback_data="admin_bookings_menu"
    )
    builder.adjust(1)
    return builder.as_markup()

def admin_cancel_booking_no_refund_menu(booking_id: int) -> InlineKeyboardMarkup:
    """Меню отмены бронирования без возврата для администратора"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить отмену",
        callback_data=f"admin_cancel_booking:{booking_id}:without_refund"
    )
    builder.button(
        text="Назад",
        callback_data="admin_bookings_menu"
    )
    builder.adjust(1)
    return builder.as_markup()

def admin_force_refund_confirmation_menu(booking_id: int) -> InlineKeyboardMarkup:
    """Меню подтверждения принудительного возврата"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, выполнить принудительный возврат",
        callback_data=f"admin_cancel_booking:{booking_id}:with_force_refund"
    )
    builder.button(
        text="Нет, отменить без возврата",
        callback_data=f"admin_cancel_booking:{booking_id}:without_refund"
    )
    builder.button(
        text="Назад",
        callback_data="admin_bookings_menu"
    )
    builder.adjust(1)
    return builder.as_markup()


# ===== ФИНАНСЫ =====

def finances_summary_menu() -> ReplyKeyboardMarkup:
    """Меню сводки по финансам"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Сегодняшние платежи"))
    builder.add(KeyboardButton(text="Статистика платежей"))
    builder.add(KeyboardButton(text="Платежи в статусе pending"))
    builder.add(KeyboardButton(text="В меню финансов"))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)
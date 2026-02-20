from typing import Optional
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from datetime import date

from app.database.models import SlotStatus, TelegramFile, FileType, User


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
        "Финансы",
        "Уведомления",
        "Настройки",
        "Выход"
    ]

    for text in categories:
        builder.add(KeyboardButton(text=text))

    builder.adjust(3, 3, 3)

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
        "Промокоды",
        "Расписание экскурсий",
        "Добавить экскурсию в расписание",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 2)
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
        "Изменить запись",
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
        "Общая статистика",
        "За период",
        "По экскурсиям",
        "По капитанам",
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
        "Аналитика и отчеты",
        "Возвраты и проблемные операции",
        "Интеграция с Ю-кассой",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
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
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 1)
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

def schedule_captains_management_menu():
    """Меню управления графиком"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Назначить смену", "Изменить смену",
        "Отменить смену", "Расписание на неделю",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


# ===== ДОБАВЛЕНИЕ КЛИЕНТА =====

def add_client_confirmation_keyboard(client_data: dict) -> InlineKeyboardMarkup:
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


# ===== УПРАВЛЕНИЕ ВИДАМИ ЭКСКУРСИЙ =====

def excursions_list_keyboard(all_excursions: list, active_only: bool) -> InlineKeyboardMarkup:
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

def exc_redaction_builder(exc_id:int):
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

def inline_end_add_exc(exc_id:int):
    return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Отредактировать данные', callback_data=f'redact_exc_data:{exc_id}'),
     InlineKeyboardButton(text='В меню администратора', callback_data='back_to_admin_panel')],
])

def err_add_exc():
    return ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Новая экскурсия')],
    [KeyboardButton(text='Главное меню')]],
    resize_keyboard=True
)

def create_excursion_management_keyboard(excursion_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
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
        InlineKeyboardButton(text="Архивные промокоды", callback_data="archive_promocodes"),
        InlineKeyboardButton(text="Статистика промокодов", callback_data="promocodes_stats"),
        InlineKeyboardButton(text="Назад", callback_data="back_to_exc_menu")
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
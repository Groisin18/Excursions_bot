from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from datetime import date, datetime
from app.database.models import SlotStatus

# ===== ГЛАВНОЕ МЕНЮ =====

def admin_main_menu():
    """Главное меню администратора"""
    builder = ReplyKeyboardBuilder()

    categories = [
        "Экскурсии",
        "Капитаны",
        "Клиенты",
        "Записи",
        "Статистика",
        "Финансы",
        "Уведомления",
        "Настройки",
        "Выход"
    ]

    for text in categories:
        builder.add(KeyboardButton(text=text))

    builder.adjust(2, 2, 2, 2, 1)

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
        "Настройки базы данных",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 1)
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

def yes_no_keyboard():
    """Клавиатура Да/Нет"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Да", callback_data="yes"),
        InlineKeyboardButton(text="Нет", callback_data="no")
    )

    return builder.as_markup()


# ===== СТАТИСТИКА =====


def statistics_period_menu():
    """Выбор периода для статистики"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Сегодня", "Вчера", "Неделя",
        "Месяц", "Квартал", "Произвольный период",
        "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


# ===== УПРАВЛЕНИЕ ЗАПИСЯМИ =====


def booking_actions_menu(booking_id: int):
    """Действия с конкретной записью"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Прибыл", callback_data=f"arrived:{booking_id}"),
        InlineKeyboardButton(text="Оплачено", callback_data=f"paid:{booking_id}"),
        InlineKeyboardButton(text="Изменить", callback_data=f"edit_booking:{booking_id}"),
        InlineKeyboardButton(text="Отменить", callback_data=f"cancel_booking:{booking_id}"),
        InlineKeyboardButton(text="Перенести", callback_data=f"reschedule:{booking_id}"),
        InlineKeyboardButton(text="Информация", callback_data=f"booking_info:{booking_id}")
    )

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def client_search_options():
    """Клавиатура для выбора способа поиска клиента"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Поиск по телефону",
        callback_data="client_search:phone"
    )
    builder.button(
        text="Поиск по имени",
        callback_data="client_search:name"
    )
    builder.button(
        text="Последние клиенты",
        callback_data="client_search:recent"
    )
    builder.button(
        text="Создать нового",
        callback_data="client_search:new"
    )
    builder.button(
        text="Отмена",
        callback_data="client_search:cancel"
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def recent_clients_keyboard(clients: list):
    """Клавиатура с последними клиентами"""
    builder = InlineKeyboardBuilder()

    for client in clients:
        builder.button(
            text=f"{client.full_name} ({client.phone_number})",
            callback_data=f"select_client:{client.id}"
        )

    builder.button(
        text="Назад к поиску",
        callback_data="client_search:back"
    )

    builder.adjust(1)
    return builder.as_markup()

def client_search_results_keyboard(clients: list):
    """Клавиатура с результатами поиска клиентов"""
    builder = InlineKeyboardBuilder()

    for client in clients:
        builder.button(
            text=f"{client.full_name} - {client.phone_number}",
            callback_data=f"select_client:{client.id}"
        )

    if not clients:
        builder.button(
            text="Ничего не найдено",
            callback_data="no_action"
        )

    builder.button(
        text="Создать нового клиента",
        callback_data="client_search:new"
    )
    builder.button(
        text="Назад к поиску",
        callback_data="client_search:back"
    )

    builder.adjust(1)
    return builder.as_markup()

# ===== УПРАВЛЕНИЕ КЛИЕНТАМИ =====


def client_actions_menu(client_id: int):
    """Действия с клиентом"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="История", callback_data=f"client_history:{client_id}"),
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_client:{client_id}"),
        InlineKeyboardButton(text="Сделать админом", callback_data=f"make_admin:{client_id}"),
        InlineKeyboardButton(text="Позвонить", callback_data=f"call_client:{client_id}"),
        InlineKeyboardButton(text="Написать", callback_data=f"message_client:{client_id}")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()


# ===== УПРАВЛЕНИЕ КАПИТАНАМИ =====


def captain_actions_menu(captain_id: int):
    """Действия с капитаном"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="График", callback_data=f"captain_schedule:{captain_id}"),
        InlineKeyboardButton(text="Зарплата", callback_data=f"captain_salary:{captain_id}"),
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_captain:{captain_id}"),
        InlineKeyboardButton(text="Статистика", callback_data=f"captain_stats:{captain_id}"),
        InlineKeyboardButton(text="Уволить", callback_data=f"remove_captain:{captain_id}")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def schedule_management_menu():
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

# ===== ФИНАНСЫ =====


def payments_filter_menu():
    """Фильтры для платежей"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Все", callback_data="payments:all"),
        InlineKeyboardButton(text="Оплаченные", callback_data="payments:paid"),
        InlineKeyboardButton(text="Ожидание", callback_data="payments:pending"),
        InlineKeyboardButton(text="Отмененные", callback_data="payments:cancelled"),
        InlineKeyboardButton(text="Сегодня", callback_data="payments:today"),
        InlineKeyboardButton(text="Неделя", callback_data="payments:week")
    )

    builder.adjust(2, 2, 2)
    return builder.as_markup()


# ===== УВЕДОМЛЕНИЯ =====


def notification_target_menu():
    """Выбор цели для уведомления"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Все клиенты", callback_data="notify:all"),
        InlineKeyboardButton(text="Завтрашние", callback_data="notify:tomorrow"),
        InlineKeyboardButton(text="Неоплаченные", callback_data="notify:unpaid"),
        InlineKeyboardButton(text="Конкретный клиент", callback_data="notify:specific"),
        InlineKeyboardButton(text="Капитаны", callback_data="notify:captains")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()


# ===== НАСТРОЙКИ =====


def admin_management_menu():
    """Управление администраторами"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Назначить администратора", "Список администраторов",
        "Изменить права", "Назад"
    ]

    for button in buttons:
        builder.add(KeyboardButton(text=button))

    builder.adjust(2, 1, 1)
    return builder.as_markup(resize_keyboard=True)


# ===== ПАГИНАЦИЯ =====

def pagination_keyboard(page: int, total_pages: int, prefix: str):
    """Клавиатура пагинации"""
    builder = InlineKeyboardBuilder()

    if page > 1:
        builder.add(InlineKeyboardButton(text="Назад", callback_data=f"{prefix}:{page-1}"))

    builder.add(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page"))

    if page < total_pages:
        builder.add(InlineKeyboardButton(text="Вперед", callback_data=f"{prefix}:{page+1}"))

    return builder.as_markup()

def list_navigation_keyboard(items: list, current_index: int, prefix: str):
    """Навигация по списку элементов"""
    builder = InlineKeyboardBuilder()

    if current_index > 0:
        builder.add(InlineKeyboardButton(text="Предыдущий", callback_data=f"{prefix}:{current_index-1}"))

    builder.add(InlineKeyboardButton(text=f"{current_index+1}/{len(items)}", callback_data="current_item"))

    if current_index < len(items) - 1:
        builder.add(InlineKeyboardButton(text="Следующий", callback_data=f"{prefix}:{current_index+1}"))

    return builder.as_markup()


# ===== УПРАВЛЕНИЕ ЭКСКУРСИЯМИ =====


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
    'Детская скидка'
    )

    redact_reg_collback_list = (
    f'redact_exc_name:{exc_id}',
    f'redact_exc_description:{exc_id}',
    f'redact_exc_duration:{exc_id}',
    f'redact_exc_price:{exc_id}',
    f'redact_exc_discount:{exc_id}'
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

# ===== МЕНЮ РАСПИСАНИЯ =====


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

def schedule_back_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню расписания"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Назад в меню расписания", callback_data="back_to_schedule_menu"),
        InlineKeyboardButton(text="В меню экскурсий", callback_data="back_to_exc_menu")
    )

    builder.adjust(1)
    return builder.as_markup()

def schedule_slots_management_menu(slots: list, target_date: date) -> InlineKeyboardMarkup:
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

def slot_completion_confirmation_menu(slot_id: int) -> InlineKeyboardMarkup:
    """
    Меню подтверждения завершения экскурсии (слота)

    Args:
        slot_id: ID слота для завершения
    """
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="Да, завершить экскурсию",
            callback_data=f"confirm_complete_slot:{slot_id}"
        ),
        InlineKeyboardButton(
            text="Нет, вернуться",
            callback_data=f"manage_slot:{slot_id}"
        )
    )

    builder.adjust(1)
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

def conflict_resolution_keyboard(slot_id: int) -> InlineKeyboardMarkup:
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

    # Показываем первые 5 дат для управления
    sorted_dates = sorted(slots_by_date.keys())[:5]

    for slot_date in sorted_dates:
        date_str = slot_date.strftime('%d.%m.%Y')
        weekday = slot_date.strftime('%a')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"{date_str} ({weekday}) - {slots_count} сл.",
            callback_data=f"manage_date_slots:{slot_date.strftime('%Y-%m-%d')}"
        )

    # Если есть еще даты
    if len(slots_by_date) > 5:
        builder.button(
            text=f"Показать еще {len(slots_by_date) - 5} дней...",
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

def manage_date_slots_menu(target_date: date, slots: list) -> InlineKeyboardMarkup:
    """
    Меню для управления слотами на конкретную дату

    Args:
        target_date: Дата для управления
        slots: Список слотов на эту дату
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для управления каждым слотом
    for slot in slots:
        if slot.status == SlotStatus.scheduled:
            excursion = slot.excursion if hasattr(slot, 'excursion') else None
            excursion_name = excursion.name if excursion else f"ID:{slot.excursion_id}"

            builder.button(
                text=f"Слот {slot.id}: {excursion_name} ({slot.start_datetime.strftime('%H:%M')})",
                callback_data=f"manage_slot:{slot.id}"
            )

    # Кнопка добавления экскурсии на эту дату
    builder.button(
        text=f"Добавить экскурсию на {target_date.strftime('%d.%m.%Y')}",
        callback_data=f"add_to_date:{target_date.strftime('%Y-%m-%d')}"
    )

    # Кнопка возврата
    builder.button(
        text="Назад к просмотру расписания",
        callback_data="schedule_week"  # Или другой подходящий callback
    )

    builder.adjust(1)
    return builder.as_markup()

# ===== ПРОМОКОДЫ =====


def promocodes_menu() -> InlineKeyboardMarkup:
    """Меню управления промокодами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Создать промокод", callback_data="create_promocode"),
        InlineKeyboardButton(text="Список промокодов", callback_data="list_promocodes"),
        InlineKeyboardButton(text="Архивные промокоды", callback_data="archive_promocodes"),
        InlineKeyboardButton(text="Статистика промокодов", callback_data="promocodes_stats"),
        InlineKeyboardButton(text="Назад", callback_data="back_to_exc_menu")
    )

    builder.adjust(2, 2, 1)
    return builder.as_markup()

def promocode_actions_menu(promocode_id: int) -> InlineKeyboardMarkup:
    """Действия с конкретным промокодом"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Просмотреть детали", callback_data=f"promocode_details:{promocode_id}"),
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_promocode:{promocode_id}"),
        InlineKeyboardButton(text="Деактивировать", callback_data=f"deactivate_promocode:{promocode_id}"),
        InlineKeyboardButton(text="Активировать", callback_data=f"activate_promocode:{promocode_id}"),
        InlineKeyboardButton(text="Статистика использования", callback_data=f"promocode_stats:{promocode_id}"),
        InlineKeyboardButton(text="Назад к списку", callback_data="list_promocodes")
    )

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def promocode_type_menu() -> InlineKeyboardMarkup:
    """Выбор типа промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Процентная скидка", callback_data="promo_type:percentage"),
        InlineKeyboardButton(text="Фиксированная сумма", callback_data="promo_type:fixed"),
        InlineKeyboardButton(text="Назад", callback_data="promocodes_menu")
    )

    builder.adjust(1)
    return builder.as_markup()

def promocode_duration_menu() -> InlineKeyboardMarkup:
    """Выбор срока действия промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="1 день", callback_data="promo_duration:1"),
        InlineKeyboardButton(text="7 дней", callback_data="promo_duration:7"),
        InlineKeyboardButton(text="30 дней", callback_data="promo_duration:30"),
        InlineKeyboardButton(text="90 дней", callback_data="promo_duration:90"),
        InlineKeyboardButton(text="Бессрочно", callback_data="promo_duration:0"),
        InlineKeyboardButton(text="Настраиваемый период", callback_data="promo_custom_duration"),
        InlineKeyboardButton(text="Назад", callback_data="create_promocode")
    )

    builder.adjust(2, 2, 2, 1)
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

def promo_type_selection_menu() -> InlineKeyboardMarkup:
    """Меню выбора типа скидки для промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Процентная скидка", callback_data="promo_type:percentage"),
        InlineKeyboardButton(text="Фиксированная сумма", callback_data="promo_type:fixed"),
        InlineKeyboardButton(text="Назад к редактированию", callback_data="edit_promo_data")
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
    else:
        builder.adjust(2, 2, 1, 1, 1)

    return builder.as_markup()

def promo_creation_confirmation_menu() -> InlineKeyboardMarkup:
    """Меню подтверждения создания промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="✅ Да, создать промокод", callback_data="confirm_create_promo"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_promo_data"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
    )

    builder.adjust(1)
    return builder.as_markup()

def promo_cancel_menu() -> InlineKeyboardMarkup:
    """Меню отмены создания промокода"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="Да, отменить", callback_data="cancel_promo_creation"),
        InlineKeyboardButton(text="Нет, продолжить", callback_data="back_to_promo_summary")
    )

    builder.adjust(1)
    return builder.as_markup()

from datetime import date
from typing import List, Optional, Dict
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.database.repositories import ExcursionRepository
from app.database.session import async_session
from app.utils.datetime_utils import get_weekday_short_name


# ===== ГЛАВНЫЕ КЛАВИАТУРЫ =====

def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню пользователя"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Личный кабинет",
        "Наши экскурсии и запись",
        "Отзывы",
        "Основные вопросы",
        "О нас"
    ]

    for text in buttons:
        builder.add(KeyboardButton(text=text))

    builder.adjust(1, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def inline_navigation() -> InlineKeyboardMarkup:
    """Инлайн-кнопки навигации (в кабинет/главное)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="В личный кабинет", callback_data='back_to_cabinet')
    builder.button(text="В главное меню", callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()


# ===== ЛИЧНЫЙ КАБИНЕТ И РЕГИСТРАЦИЯ =====

def registration_data_menu(has_children: bool = False) -> InlineKeyboardMarkup:
    """Меню личного кабинета"""
    builder = InlineKeyboardBuilder()

    builder.button(text='Редактировать мои данные', callback_data='redact_users_data')
    if has_children:
        builder.button(text='Данные детей', callback_data='child_choice')
    builder.button(text='Регистрация ребенка', callback_data='reg_child')
    builder.button(text='Мои бронирования', callback_data='user_booking')
    builder.button(text='В главное меню', callback_data='back_to_main')

    builder.adjust(1)
    return builder.as_markup()

def error_registration_menu() -> ReplyKeyboardMarkup:
    """Меню при ошибке регистрации"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text='Зарегистрироваться'))
    builder.add(KeyboardButton(text='В главное меню'))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


# ===== КЛАВИАТУРЫ ДЛЯ БРОНИРОВАНИЙ ПОЛЬЗОВАТЕЛЯ =====

def bookings_main_menu() -> InlineKeyboardMarkup:
    """Главное меню раздела 'Мои бронирования'"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Активные бронирования", callback_data="my_active_bookings")
    builder.button(text="История бронирований", callback_data="my_history_bookings")
    builder.button(text="Назад в кабинет", callback_data="back_to_cabinet")
    builder.adjust(1)
    return builder.as_markup()

def empty_bookings(back_callback: str = "user_booking") -> InlineKeyboardMarkup:
    """Клавиатура для случая, когда бронирований нет"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад в меню", callback_data=back_callback)
    builder.button(text="В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def bookings_list(
    bookings: List,
    callback_prefix: str,
    back_callback: str = "user_booking"
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком бронирований

    Args:
        bookings: список бронирований
        callback_prefix: префикс для callback_data (например "booking_detail:")
        back_callback: callback для кнопки "Назад"
    """
    builder = InlineKeyboardBuilder()

    for booking in bookings:
        slot = booking.slot
        excursion = slot.excursion if slot else None

        if slot and excursion:
            date_str = slot.start_datetime.strftime("%d.%m.%Y")
            button_text = f"{excursion.name} ({date_str})"
            builder.button(
                text=button_text,
                callback_data=f"{callback_prefix}{booking.id}"
            )

    builder.button(text="Назад в меню", callback_data=back_callback)
    builder.button(text="В главное меню", callback_data="back_to_main")
    builder.adjust(1)

    return builder.as_markup()

def post_booking(booking_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура после успешного создания бронирования

    Args:
        booking_id: ID созданного бронирования
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить сейчас", callback_data=f"pay_booking:{booking_id}")
    builder.button(text="Отменить бронирование", callback_data=f"cancel_booking:{booking_id}")
    builder.button(text="В главное меню", callback_data="back_to_main_with_info")
    builder.adjust(1)
    return builder.as_markup()

def cancel_confirmation(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отмены"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, отменить", callback_data=f"confirm_cancel:{booking_id}")
    builder.button(text="Нет, вернуться", callback_data=f"booking_detail:{booking_id}")
    builder.adjust(1)
    return builder.as_markup()

def back_to_booking(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой возврата к бронированию"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад к бронированию", callback_data=f"booking_detail:{booking_id}")
    builder.adjust(1)
    return builder.as_markup()

def active_booking_actions(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для активного неоплаченного бронирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", callback_data=f"pay_booking:{booking_id}")
    builder.button(text="Отменить бронирование", callback_data=f"cancel_booking:{booking_id}")
    builder.button(text="Назад к списку", callback_data="user_booking")
    builder.button(text="В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def paid_booking_actions(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для оплаченного бронирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Информация о возврате", callback_data=f"refund_info:{booking_id}")
    builder.button(text="Назад к списку", callback_data="user_booking")
    builder.button(text="В главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


# ===== РЕДАКТИРОВАНИЕ ДАННЫХ =====


def redaction_menu() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования данных пользователя"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Имя', callback_data='redact_name')
    builder.button(text='Фамилия', callback_data='redact_surname')
    builder.button(text='Номер телефона', callback_data='redact_phone')
    builder.button(text='Дата рождения', callback_data='redact_birth_date')
    builder.button(text='Адрес', callback_data='redact_address')
    builder.button(text='Email', callback_data='redact_email')
    builder.button(text='Вес', callback_data='redact_weight')
    builder.button(text='Вернуться в кабинет', callback_data='back_to_cabinet')
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

def redaction_child_menu() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования данных ребенка"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Имя', callback_data='redact_child_name')
    builder.button(text='Фамилия', callback_data='redact_child_surname')
    builder.button(text='Дата рождения', callback_data='redact_child_birth_date')
    builder.button(text='Вес', callback_data='redact_child_weight')
    builder.button(text='Адрес', callback_data='redact_child_address')
    builder.button(text='Назад к списку детей', callback_data='child_choice')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


# ===== СОГЛАСИЕ НА ОБРАБОТКУ ПД =====

def pd_consent() -> InlineKeyboardMarkup:
    """Согласие на обработку ПД (стандартное)"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Я согласен', callback_data='pd_consent_true')
    builder.button(text='Я не даю согласие', callback_data='pd_consent_false')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()

def pd_consent_token() -> InlineKeyboardMarkup:
    """Согласие на обработку ПД (для токена)"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Я согласен', callback_data='pd_consent_token_true')
    builder.button(text='Я не даю согласие', callback_data='pd_consent_token_false')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()

def pd_consent_child() -> InlineKeyboardMarkup:
    """Согласие на обработку ПД (для ребенка)"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Я согласен', callback_data='pd_consent_child_true')
    builder.button(text='Я не даю согласие', callback_data='pd_consent_child_false')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()


# ===== ТОКЕН АВТОРИЗАЦИИ =====

def token_check() -> InlineKeyboardMarkup:
    """Проверка наличия токена"""
    builder = InlineKeyboardBuilder()
    builder.button(text='У меня есть токен', callback_data='user_has_token')
    builder.button(text='У меня нет токена', callback_data='user_hasnt_token')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()

def token_confirmation() -> InlineKeyboardMarkup:
    """Подтверждение токена"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Да, это я', callback_data='user_has_right_token')
    builder.button(text='Нет, это не я', callback_data='user_has_wrong_token')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()


# ===== ЭКСКУРСИИ =====
def excursion_details(excursion_id: int) -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура с действиями для конкретной экскурсии
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Расписание этой экскурсии",
        callback_data=f"public_schedule_exc:{excursion_id}"
    )
    builder.button(
        text="К списку экскурсий",
        callback_data="public_back_to_excursions"
    )
    builder.adjust(1)
    return builder.as_markup()

async def all_excursions() -> Optional[InlineKeyboardMarkup]:
    """
    Инлайн-клавиатура со списком экскурсий и общим расписанием
    Асинхронная, так как обращается к БД
    """
    async with async_session() as session:
        excursion_repo = ExcursionRepository(session)
        excursions = await excursion_repo.get_all(active_only=True)

        if not excursions:
            return None

        builder = InlineKeyboardBuilder()

        # Кнопка общего расписания
        builder.button(
            text="Расписание всех экскурсий",
            callback_data="public_schedule_all"
        )

        # Разделитель
        builder.button(
            text="─────────────",
            callback_data="no_action"
        )

        # Список экскурсий
        for excursion in excursions:
            builder.button(
                text=excursion.name,
                callback_data=f"public_exc_detail:{excursion.id}"
            )

        builder.button(
            text="В главное меню",
            callback_data="back_to_main"
        )

        builder.adjust(1)
        return builder.as_markup()

def public_schedule_options() -> InlineKeyboardMarkup:
    """Опции просмотра расписания для пользователей"""
    builder = InlineKeyboardBuilder()

    builder.button(text="На сегодня", callback_data="public_schedule:today")
    builder.button(text="На завтра", callback_data="public_schedule:tomorrow")
    builder.button(text="На неделю вперед", callback_data="public_schedule_week")
    builder.button(text="На месяц вперед", callback_data="public_schedule_month")
    builder.button(text="Выбрать дату", callback_data="public_schedule_by_date")
    builder.button(text="Назад к списку экскурсий", callback_data="public_back_to_excursions")

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def public_slot_action(slot_id: int, available_places: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для записи на слот

    Args:
        slot_id: ID слота
        available_places: Количество свободных мест
    """
    builder = InlineKeyboardBuilder()

    if available_places > 0:
        builder.button(
            text=f"Записаться ({available_places} мест)",
            callback_data=f"public_book_slot:{slot_id}"
        )
    else:
        builder.button(
            text="Мест нет",
            callback_data="no_action"
        )

    builder.button(
        text="Назад к расписанию",
        callback_data="public_back_to_schedule"
    )

    builder.adjust(1)
    return builder.as_markup()

def public_schedule_date_menu(slots: list, target_date: date) -> InlineKeyboardMarkup:
    """Клавиатура слотов на конкретную дату"""
    builder = InlineKeyboardBuilder()

    for slot in slots:
        start_time = slot.start_datetime.strftime("%H:%M")
        excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

        button_text = f"{start_time} - {excursion_name}"
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."

        builder.button(
            text=button_text,
            callback_data=f"public_view_slot:{slot.id}"
        )

    builder.button(
        text="Назад к расписанию",
        callback_data="public_back_to_date_schedule"
    )
    builder.adjust(1)

    return builder.as_markup()

def public_schedule_week_menu(slots_by_date: Dict[date, list]) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора даты из расписания на неделю

    Args:
        slots_by_date: Словарь {дата: [слоты]}
    """
    builder = InlineKeyboardBuilder()

    for slot_date in sorted(slots_by_date.keys()):
        date_str = slot_date.strftime('%d.%m.%Y')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"{date_str} ({get_weekday_short_name(slot_date)}) - {slots_count} экс.",
            callback_data=f"public_view_date:{slot_date.strftime('%Y-%m-%d')}"
        )

    builder.button(
        text="Назад к выбору периода",
        callback_data="public_back_to_schedule_options"
    )

    builder.adjust(1)
    return builder.as_markup()

def public_schedule_month_menu(slots_by_date: Dict[date, list]) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора даты из расписания на месяц

    Args:
        slots_by_date: Словарь {дата: [слоты]}
    """
    builder = InlineKeyboardBuilder()

    # Показываем первые 7 дат
    sorted_dates = sorted(slots_by_date.keys())[:7]

    for slot_date in sorted_dates:
        date_str = slot_date.strftime('%d.%m.%Y')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"{date_str} ({get_weekday_short_name(slot_date)}) - {slots_count} экс.",
            callback_data=f"public_view_date:{slot_date.strftime('%Y-%m-%d')}"
        )

    # Если есть еще даты
    if len(slots_by_date) > 7:
        builder.button(
            text="Показать еще даты...",
            callback_data="public_show_more_dates"
        )

    builder.button(
        text="Выбрать другую дату",
        callback_data="public_schedule_by_date"
    )

    builder.button(
        text="Назад к выбору периода",
        callback_data="public_back_to_schedule_options"
    )

    builder.adjust(1)
    return builder.as_markup()

def excursion_schedule(slots: list) -> InlineKeyboardMarkup:
    """
    Клавиатура со слотами для конкретной экскурсии

    Args:
        slots: Список слотов ExcursionSlot
    """
    builder = InlineKeyboardBuilder()

    if not slots:
        builder.button(
            text="Нет доступных записей",
            callback_data="no_action"
        )
        if slots:
            builder.button(
                text="Назад к экскурсии",
                callback_data=f"public_exc_detail:{slots[0].excursion_id}"
            )
        builder.adjust(1)
        return builder.as_markup()

    # Группируем слоты по датам
    slots_by_date = {}
    for slot in slots:
        date_key = slot.start_datetime.date()
        if date_key not in slots_by_date:
            slots_by_date[date_key] = []
        slots_by_date[date_key].append(slot)

    # Создаем кнопки по датам
    for date_key in sorted(slots_by_date.keys()):
        date_slots = slots_by_date[date_key]
        date_str = date_key.strftime('%d.%m.%Y')
        weekday = get_weekday_short_name(date_key)

        builder.button(
            text=f"{date_str} ({weekday}) - {len(date_slots)} экс.",
            callback_data=f"public_view_exc_date:{date_key.strftime('%Y-%m-%d')}:{slots[0].excursion_id}"
        )

    builder.button(
        text="Назад к экскурсии",
        callback_data=f"public_exc_detail:{slots[0].excursion_id}"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== 9. ИНФОРМАЦИЯ И FAQ =====

def feedback() -> InlineKeyboardMarkup:
    """Кнопка с ссылкой на группу отзывов"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Группа с отзывами',
        url="https://t.me/+W8tkMz0Jz3A2ZTIy?clckid=cc64aa67"
    )
    return builder.as_markup()

def about_us() -> InlineKeyboardMarkup:
    """Кнопки с ссылками на соцсети"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Группа с отзывами",
        url="https://t.me/+W8tkMz0Jz3A2ZTIy?clckid=cc64aa67"
    )
    builder.button(
        text="Группа ВКонтакте",
        url="https://vk.com/angarariver38"
    )
    builder.button(
        text="Телеграм-канал",
        url="https://t.me/po_angare"
    )
    builder.adjust(1)
    return builder.as_markup()

def questions() -> InlineKeyboardMarkup:
    """Клавиатура с часто задаваемыми вопросами"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Откуда начинаем?', callback_data='qu_startplace')
    builder.button(text='Что с собой взять?', callback_data='qu_things_witn')
    builder.button(text='Какие есть скидки?', callback_data='qu_discount')
    builder.button(text='Можно ли только своей компанией?', callback_data='qu_self_co')
    builder.button(text='В главное меню', callback_data='back_to_main')
    builder.adjust(1)
    return builder.as_markup()


# ===== 10. БРОНИРОВАНИЕ НА СЛОТ =====
def participants(has_children: bool) -> InlineKeyboardMarkup:
    """Клавиатура выбора участников"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Записываюсь только я",
        callback_data="booking_just_me"
    )

    if has_children:
        builder.button(
            text="Я буду с детьми (макс. 5)",
            callback_data="booking_with_children"
        )

    builder.button(
        text="Отменить бронирование",
        callback_data="booking_cancel"
    )

    builder.adjust(1)
    return builder.as_markup()

def skip_promocode() -> InlineKeyboardMarkup:
    """Клавиатура для шага промокода"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить промокод", callback_data="skip_promo_code")
    builder.button(text="Отменить бронирование", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()

def confirmation() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения бронирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить бронирование", callback_data="confirm_booking")
    builder.button(text="Отменить", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()

def children_selection(children: list, selected_ids: list = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора детей"""
    builder = InlineKeyboardBuilder()

    if selected_ids is None:
        selected_ids = []

    for child in children:
        age_info = ""
        if child.date_of_birth:
            today = date.today()
            age = today.year - child.date_of_birth.year
            age_info = f" ({age} лет)"

        prefix = "✓ " if child.id in selected_ids else ""
        button_text = f"{prefix}{child.full_name}{age_info}"

        builder.button(
            text=button_text,
            callback_data=f"select_child:{child.id}"
        )

    builder.button(text="Завершить выбор", callback_data="finish_children_selection")
    builder.button(text="Отменить бронирование", callback_data="cancel_booking")
    builder.adjust(1)

    return builder.as_markup()

def child_weight(child_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для ввода веса ребенка"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Пропустить (использовать средний вес)",
        callback_data=f"skip_child_weight:{child_id}"
    )
    builder.button(text="Отменить бронирование", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()

def booking_start() -> InlineKeyboardMarkup:
    """Клавиатура для начала бронирования"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Начать бронирование", callback_data="confirm_start_booking")
    builder.button(text="Другие варианты", callback_data="public_schedule_back")
    builder.adjust(1)
    return builder.as_markup()
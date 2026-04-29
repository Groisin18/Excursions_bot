from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List

from app.database.models import ExcursionSlot, Booking


def captain_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню капитана"""
    builder = ReplyKeyboardBuilder()

    buttons = [
        "Мое расписание",
        "Моя статистика",
        "Завершить экскурсию",
        "Отметить прибытие клиента",
        "Выход"
    ]

    for text in buttons:
        builder.add(KeyboardButton(text=text))

    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def captain_slots_for_arrival_keyboard(slots: List[ExcursionSlot]) -> InlineKeyboardMarkup:
    """Клавиатура выбора слота для отметки прибытия (только слоты на сегодня, где капитан назначен)"""
    builder = InlineKeyboardBuilder()

    for slot in slots:
        time_str = slot.start_datetime.strftime("%H:%M")
        excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
        label = f"{excursion_name} - {time_str}"
        builder.add(InlineKeyboardButton(
            text=label,
            callback_data=f"captain_arrival_slot:{slot.id}"
        ))

    builder.add(InlineKeyboardButton(
        text="Назад в меню",
        callback_data="captain_back_to_menu"
    ))

    builder.adjust(1)
    return builder.as_markup()


def slot_clients_arrival_keyboard(slot_id: int, bookings: List[Booking]) -> InlineKeyboardMarkup:
    """Клавиатура со списком клиентов слота для отметки прибытия"""
    builder = InlineKeyboardBuilder()

    for booking in bookings:
        client_name = booking.adult_user.full_name if booking.adult_user else "Неизвестный"
        arrived = booking.client_status.value == "arrived" if booking.client_status else False
        prefix = "V " if arrived else ""

        builder.add(InlineKeyboardButton(
            text=f"{prefix}{client_name}",
            callback_data=f"captain_mark_arrived:{booking.id}:{slot_id}"
        ))

    builder.add(InlineKeyboardButton(
        text="Назад к выбору слота",
        callback_data="captain_back_to_slots"
    ))

    builder.adjust(1)
    return builder.as_markup()


def captain_slots_for_complete_keyboard(slots: List[ExcursionSlot]) -> InlineKeyboardMarkup:
    """Клавиатура выбора слота для завершения экскурсии"""
    builder = InlineKeyboardBuilder()

    for slot in slots:
        time_str = slot.start_datetime.strftime("%d.%m %H:%M")
        excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"
        label = f"{excursion_name} - {time_str}"
        builder.add(InlineKeyboardButton(
            text=label,
            callback_data=f"captain_complete_slot:{slot.id}"
        ))

    builder.add(InlineKeyboardButton(
        text="Назад в меню",
        callback_data="captain_back_to_menu"
    ))

    builder.adjust(1)
    return builder.as_markup()
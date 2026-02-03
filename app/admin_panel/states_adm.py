from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для администратора"""
    waiting_for_statistics_period = State()
    waiting_for_booking_search = State()
    waiting_for_client_search = State()
    waiting_for_captain_data = State()
    waiting_for_excursion_data = State()
    waiting_for_notification_text = State()
    waiting_for_promocode_data = State()
    waiting_for_schedule_date = State()
    waiting_for_schedule_time = State()
    waiting_for_schedule_capacity = State()

class AdminCreateBooking(StatesGroup):
    """Состояния для создания записи администратором"""
    waiting_for_client_choice = State()  # Выбор: поиск/новый/последние
    waiting_for_client_search = State()   # Поиск клиента
    waiting_for_client_create = State()   # Создание нового клиента
    waiting_for_excursion = State()       # Выбор экскурсии
    waiting_for_date = State()            # Выбор даты
    waiting_for_time = State()            # Выбор времени
    waiting_for_people_count = State()    # Количество людей
    waiting_for_confirmation = State()    # Подтверждение

class AddToSchedule(StatesGroup):
    """Состояния для добавления экскурсии в расписание"""
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_capacity = State()
    waiting_for_max_weight = State()
    waiting_for_captain_selection = State()

class RescheduleSlot(StatesGroup):
    waiting_for_new_datetime = State()
    waiting_for_confirmation = State()

class NewExcursion(StatesGroup):
    """Состояния для создания нового вида экскурсий"""
    name = State()
    description = State()
    base_duration_minutes = State()
    base_price = State()
    end_reg = State()

class RedactExcursion(StatesGroup):
    """Состояния для редактирования вида экскурсий"""
    name = State()
    description = State()
    base_duration_minutes = State()
    base_price = State()
    excursion_id = State()

class CreatePromocode(StatesGroup):
    """Состояния для создания промокода"""
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_description = State()
    waiting_for_usage_limit = State()
    waiting_for_duration = State()
    waiting_for_confirmation = State()
from aiogram.fsm.state import State, StatesGroup


class Reg_user(StatesGroup):
    pd_consent = State()
    is_token = State()
    name = State()
    surname = State()
    date_of_birth = State()
    weight = State()
    address = State()
    email = State()
    phone = State()
    end_reg = State()

class Reg_token(StatesGroup):
    pd_consent = State()
    token = State()
    email = State()
    phone = State()
    end_reg = State()

class Reg_child(StatesGroup):
    pd_consent = State()
    name = State()
    surname = State()
    date_of_birth = State()
    weight = State()
    address = State()
    end_reg = State()

class Red_user(StatesGroup):
    name = State()
    surname = State()
    date_of_birth = State()
    weight = State()
    address = State()
    email = State()
    phone = State()
    end_reg = State()

class Red_child(StatesGroup):
    name = State()
    surname = State()
    date_of_birth = State()
    weight = State()
    address = State()
    end_reg = State()

class UserScheduleStates(StatesGroup):
    waiting_for_schedule_date = State()

class UserBookingStates(StatesGroup):
    """Состояния для процесса бронирования"""
    checking_weight = State()           # 1. Проверка веса взрослого
    requesting_adult_weight = State()
    selecting_participants = State()    # 2. Я один / Я с детьми
    selecting_children = State()        # 3. Выбор конкретных детей
    requesting_child_weight = State()   # 4. Запрос веса для детей без веса (динамическое)
    applying_promo_code = State()       # 5. Ввод промокода
    calculating_total = State()         # 6. Расчет и показ суммы
    confirming_booking = State()        # 7. Финальное подтверждение
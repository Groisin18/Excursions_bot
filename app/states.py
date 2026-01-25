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
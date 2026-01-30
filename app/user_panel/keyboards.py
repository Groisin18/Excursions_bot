from datetime import date

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import DatabaseManager
from app.database.models import async_session, SlotStatus
from app.utils.logging_config import get_logger
from app.utils.datetime_utils import get_weekday_name, get_weekday_short_name

logger = get_logger(__name__)

# ===== ГЛАВНЫЕ КЛАВИАТУРЫ =====

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Тест оплаты'), KeyboardButton(text='Личный кабинет')],
        [KeyboardButton(text='Наши экскурсии'), KeyboardButton(text='Отзывы')],
        [KeyboardButton(text='Основные вопросы'), KeyboardButton(text='О нас')]
    ],
    resize_keyboard=True
)

getcontact = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Отправить контакт', request_contact=True)]
    ],
    resize_keyboard=True,
    input_field_placeholder='Нажми на кнопку или введи номер вручную'
)

inline_in_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='В личный кабинет', callback_data='back_to_cabinet')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)


# ===== ЛИЧНЫЙ КАБИНЕТ И РЕГИСТРАЦИЯ =====

async def registration_data_menu_builder(has_children: bool = False):
    """Создает меню личного кабинета"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text='Редактировать мои данные',
        callback_data='redact_users_data'
    ))
    if has_children:
        builder.add(InlineKeyboardButton(
            text='Данные детей',
            callback_data='child_choice'
        ))
    builder.add(InlineKeyboardButton(
        text='Регистрация ребенка',
        callback_data='reg_child'
    ))
    builder.add(InlineKeyboardButton(
        text='В главное меню',
        callback_data='back_to_main'
    ))
    builder.adjust(1)
    return builder.as_markup()

inline_end_reg = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Отредактировать данные', callback_data='redact_users_data')],
        [InlineKeyboardButton(text='Зарегистрировать ребенка', callback_data='reg_child')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')],
    ]
)

err_reg = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Зарегистрироваться')],
        [KeyboardButton(text='В главное меню')]
    ],
    resize_keyboard=True
)


# ===== РЕДАКТИРОВАНИЕ ДАННЫХ =====

async def redaction_builder():
    """Клавиатура для редактирования данных пользователя"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Имя', callback_data='redact_name'))
    builder.add(InlineKeyboardButton(text='Фамилия', callback_data='redact_surname'))
    builder.add(InlineKeyboardButton(text='Номер телефона', callback_data='redact_phone'))
    builder.add(InlineKeyboardButton(text='Дата рождения', callback_data='redact_birth_date'))
    builder.add(InlineKeyboardButton(text='Адрес', callback_data='redact_address'))
    builder.add(InlineKeyboardButton(text='Email', callback_data='redact_email'))
    builder.add(InlineKeyboardButton(text='Вес', callback_data='redact_weight'))
    builder.add(InlineKeyboardButton(text='Вернуться в кабинет', callback_data='back_to_cabinet'))

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

async def redaction_child_builder():
    """Клавиатура для редактирования данных ребенка"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Имя', callback_data='redact_child_name'))
    builder.add(InlineKeyboardButton(text='Фамилия', callback_data='redact_child_surname'))
    builder.add(InlineKeyboardButton(text='Дата рождения', callback_data='redact_child_birth_date'))
    builder.add(InlineKeyboardButton(text='Вес', callback_data='redact_child_weight'))
    builder.add(InlineKeyboardButton(text='Адрес', callback_data='redact_child_address'))
    builder.add(InlineKeyboardButton(text='Назад к списку детей', callback_data='child_choice'))
    builder.add(InlineKeyboardButton(text='В главное меню', callback_data='back_to_main'))

    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


# ===== СОГЛАСИЕ НА ОБРАБОТКУ ПД =====

inline_pd_consent = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Я согласен', callback_data='pd_consent_true')],
        [InlineKeyboardButton(text='Я не даю согласие', callback_data='pd_consent_false')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)

inline_pd_consent_token = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Я согласен', callback_data='pd_consent_token_true')],
        [InlineKeyboardButton(text='Я не даю согласие', callback_data='pd_consent_token_false')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)

inline_pd_consent_child = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Я согласен', callback_data='pd_consent_child_true')],
        [InlineKeyboardButton(text='Я не даю согласие', callback_data='pd_consent_child_false')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)


# ===== ТОКЕН АВТОРИЗАЦИИ =====

inline_is_token = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='У меня есть токен', callback_data='user_has_token')],
        [InlineKeyboardButton(text='У меня нет токена', callback_data='user_hasnt_token')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)

inline_is_token_right = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Да, это я', callback_data='user_has_right_token')],
        [InlineKeyboardButton(text='Нет, это не я', callback_data='user_has_wrong_token')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)


# ===== ЭКСКУРСИИ =====

async def get_excursion_details_inline(excursion_id: int) -> InlineKeyboardMarkup:
    """
    Получить инлайн-клавиатуру с действиями для конкретной экскурсии.
    """
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="Расписание этой экскурсии",
        callback_data=f"public_schedule_exc:{excursion_id}"
    ))
    keyboard.add(InlineKeyboardButton(
        text="К списку экскурсий",
        callback_data="public_back_to_excursions"
    ))
    keyboard.adjust(1)
    return keyboard.as_markup()

async def all_excursions_inline() -> InlineKeyboardMarkup:
    """Создать инлайн-клавиатуру со списком экскурсий и общим расписанием"""
    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            excursions = await db.get_all_excursions(active_only=True)

            if not excursions:
                return None

            keyboard = InlineKeyboardBuilder()

            # Кнопка общего расписания
            keyboard.add(InlineKeyboardButton(
                text="Расписание всех экскурсий",
                callback_data="public_schedule_all"
            ))

            # Разделитель
            keyboard.add(InlineKeyboardButton(
                text="─────────────",
                callback_data="no_action"
            ))

            # Список экскурсий
            for excursion in excursions:
                keyboard.add(InlineKeyboardButton(
                    text=excursion.name,
                    callback_data=f"public_exc_detail:{excursion.id}"
                ))

            keyboard.add(InlineKeyboardButton(
                text="В главное меню",
                callback_data="back_to_main"
            ))

            keyboard.adjust(1)
            return keyboard.as_markup()

    except Exception as e:
        logger.error(f"Ошибка создания клавиатуры экскурсий: {e}", exc_info=True)
        return None

def public_schedule_options() -> InlineKeyboardMarkup:
    """Опции просмотра расписания для пользователей"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="На сегодня", callback_data="public_schedule_today"),
        InlineKeyboardButton(text="На завтра", callback_data="public_schedule_tomorrow"),
        InlineKeyboardButton(text="На неделю вперед", callback_data="public_schedule_week"),
        InlineKeyboardButton(text="На месяц вперед", callback_data="public_schedule_month"),
        InlineKeyboardButton(text="Выбрать дату", callback_data="public_schedule_by_date"),
        InlineKeyboardButton(text="Назад к списку экскурсий", callback_data="public_back_to_excursions")
    )

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def public_slot_action_menu(slot_id: int, available_places: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для записи на слот

    Args:
        slot_id: ID слота
        available_places: Количество свободных мест
    """
    builder = InlineKeyboardBuilder()

    if available_places > 0:
        builder.add(
            InlineKeyboardButton(
                text=f"Записаться ({available_places} мест)",
                callback_data=f"public_book_slot:{slot_id}"
            )
        )
    else:
        builder.add(
            InlineKeyboardButton(
                text="Мест нет",
                callback_data="no_action"
            )
        )

    builder.add(
        InlineKeyboardButton(
            text="Назад к расписанию",
            callback_data="public_back_to_schedule"
        )
    )

    builder.adjust(1)
    return builder.as_markup()

def public_schedule_date_menu(slots: list, target_date: date) -> InlineKeyboardMarkup:
    """
    Клавиатура для записи на слоты на конкретную дату (публичная)

    Args:
        slots: Список объектов ExcursionSlot
        target_date: Дата для которой показывается расписание
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для записи на слоты
    for slot in slots:
        if slot.status == SlotStatus.scheduled:
            # Получаем свободные места для текста кнопки
            # (свободные места будем считать в хэндлере и передавать отдельно)
            start_time = slot.start_datetime.strftime("%H:%M")
            excursion_name = slot.excursion.name if slot.excursion else "Экскурсия"

            builder.button(
                text=f"{start_time} - {excursion_name}",
                callback_data=f"public_view_slot:{slot.id}"
            )

    # Кнопка возврата
    builder.button(
        text="Назад к выбору периода",
        callback_data="public_back_to_schedule_options"
    )

    builder.adjust(1)
    return builder.as_markup()

def public_slot_detail_menu(slot_id: int, free_places: int, slot_time: str, excursion_name: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для записи на конкретный слот

    Args:
        slot_id: ID слота
        free_places: Количество свободных мест
        slot_time: Время слота (формат "12:00-16:00")
        excursion_name: Название экскурсии
    """
    builder = InlineKeyboardBuilder()

    if free_places > 0:
        builder.button(
            text=f"Записаться ({free_places} мест)",
            callback_data=f"public_book_slot:{slot_id}"
        )
    else:
        builder.button(
            text="Мест нет",
            callback_data="no_action"
        )

    # Кнопка назад к расписанию на дату
    builder.button(
        text="Назад к расписанию",
        callback_data="public_back_to_date_schedule"
    )

    builder.adjust(1)
    return builder.as_markup()

def public_schedule_week_menu(slots_by_date: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора даты из расписания на неделю (публичная)

    Args:
        slots_by_date: Словарь {дата: [слоты]}
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для выбора конкретной даты
    for slot_date in sorted(slots_by_date.keys()):
        date_str = slot_date.strftime('%d.%m.%Y')
        slots_count = len(slots_by_date[slot_date])

        builder.button(
            text=f"{date_str} ({get_weekday_short_name(slot_date)}) - {slots_count} экс.",
            callback_data=f"public_view_date:{slot_date.strftime('%Y-%m-%d')}"
        )

    # Кнопка возврата
    builder.button(
        text="Назад к выбору периода",
        callback_data="public_back_to_schedule_options"
    )

    builder.adjust(1)
    return builder.as_markup()

def public_schedule_month_menu(slots_by_date: dict) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора даты из расписания на месяц (публичная)

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
            text=f"Показать еще даты...",
            callback_data="public_show_more_dates"
        )

    # Кнопка выбора конкретной даты
    builder.button(
        text="Выбрать другую дату",
        callback_data="public_schedule_by_date"
    )

    # Кнопка возврата
    builder.button(
        text="Назад к выбору периода",
        callback_data="public_back_to_schedule_options"
    )

    builder.adjust(1)
    return builder.as_markup()

async def get_excursion_schedule_keyboard(slots: list) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со слотами для конкретной экскурсии

    Args:
        slots: Список слотов ExcursionSlot
    """
    builder = InlineKeyboardBuilder()

    if not slots:
        builder.button(
            text="Нет доступных записей",
            callback_data="no_action"
        )
        builder.button(
            text="Назад к экскурсии",
            callback_data=f"public_exc_detail:{slots[0].excursion_id if slots else 0}"
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

    # Кнопка назад
    builder.button(
        text="Назад к экскурсии",
        callback_data=f"public_exc_detail:{slots[0].excursion_id}"
    )

    builder.adjust(1)
    return builder.as_markup()


# ===== 9. ИНФОРМАЦИЯ И FAQ =====

inline_feedback = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Группа с отзывами', url="https://t.me/+W8tkMz0Jz3A2ZTIy?clckid=cc64aa67"),
         InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')],
    ]
)

inline_about_us = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Группа с отзывами", url="https://t.me/+W8tkMz0Jz3A2ZTIy?clckid=cc64aa67")],
        [InlineKeyboardButton(text="Группа ВКонтакте", url="https://vk.com/angarariver38")],
        [InlineKeyboardButton(text="Телеграм-канал", url="https://t.me/po_angare")],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')],
    ]
)

inline_questions = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Откуда начинаем?', callback_data='qu_startplace')],
        [InlineKeyboardButton(text='Что с собой взять?', callback_data='qu_things_witn')],
        [InlineKeyboardButton(text='Какие есть скидки?', callback_data='qu_discount')],
        [InlineKeyboardButton(text='Можно ли только своей компанией?', callback_data='qu_self_co')],
        [InlineKeyboardButton(text='В главное меню', callback_data='back_to_main')]
    ]
)
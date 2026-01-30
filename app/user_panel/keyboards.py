import asyncio
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from app.database.requests import DatabaseManager
from app.database.models import async_session
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_excursions_cache = None
_cache_time = 0
CACHE_TIMEOUT = 300  # 5 минут


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

async def excursion_builder():
    """Запасная клавиатура с экскурсиями (если БД недоступна)"""
    excursion_list = (
        'Дубынинские столбы',
        'Вечерние Дубынинские столбы',
        'Ангарский каньон',
        'Вечерний остров Московский'
    )

    keyboard = ReplyKeyboardBuilder()
    for excursion in excursion_list:
        keyboard.add(KeyboardButton(text=excursion))
    return keyboard.adjust(2).as_markup()

async def get_excursions_keyboard(force_refresh: bool = False):
    """
    Получить клавиатуру с экскурсиями из базы данных.
    """
    global _excursions_cache, _cache_time
    current_time = asyncio.get_event_loop().time()

    if (not force_refresh and _excursions_cache and
        (current_time - _cache_time) < CACHE_TIMEOUT):
        return _excursions_cache

    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            excursions = await db.get_all_excursions(active_only=True)

            if not excursions:
                logger.warning("Нет активных экскурсий в базе данных")
                keyboard = ReplyKeyboardBuilder()
                keyboard.add(KeyboardButton(text="Назад в меню"))
                return keyboard.as_markup(
                    resize_keyboard=True,
                    input_field_placeholder="К сожалению, нет актуальных экскурсий"
                )

            logger.debug(f"Найдено {len(excursions)} активных экскурсий")
            keyboard = ReplyKeyboardBuilder()

            for excursion in excursions:
                keyboard.add(KeyboardButton(text=excursion.name))
            keyboard.add(KeyboardButton(text="Назад в меню"))
            keyboard.adjust(2, repeat=True)

            _excursions_cache = keyboard.as_markup(
                resize_keyboard=True,
                input_field_placeholder="Выберите экскурсию"
            )
            _cache_time = current_time

            return _excursions_cache

    except Exception as e:
        logger.error(f"Ошибка при создании клавиатуры экскурсий: {e}", exc_info=True)
        keyboard = ReplyKeyboardBuilder()
        keyboard.add(KeyboardButton(text="Назад в меню"))
        return keyboard.as_markup(resize_keyboard=True)

async def get_excursions_inline_keyboard(action: str = "select") -> InlineKeyboardMarkup:
    """
    Получить инлайн-клавиатуру с экскурсиями из базы данных.
    action: Действие для callback_data (select, book, info и т.д.)
    """
    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            excursions = await db.get_all_excursions(active_only=True)

            if not excursions:
                logger.warning("Нет активных экскурсий для инлайн-клавиатуры")
                return None

            keyboard = InlineKeyboardBuilder()
            for excursion in excursions:
                keyboard.add(InlineKeyboardButton(
                    text=f"{excursion.name}",
                    callback_data=f"excursion_{action}_{excursion.id}"
                ))
            keyboard.add(InlineKeyboardButton(
                text="В главное меню",
                callback_data="back_to_main"
            ))
            keyboard.adjust(1)
            return keyboard.as_markup()

    except Exception as e:
        logger.error(f"Ошибка при создании инлайн-клавиатуры экскурсий: {e}", exc_info=True)
        return None

async def get_excursion_details_inline(excursion_id: int) -> InlineKeyboardMarkup:
    """
    Получить инлайн-клавиатуру с действиями для конкретной экскурсии.
    """
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="Посмотреть расписание",
        callback_data=f"excursion_schedule_{excursion_id}"
    ))
    keyboard.add(InlineKeyboardButton(
        text="Подробное описание",
        callback_data=f"excursion_details_{excursion_id}"
    ))
    keyboard.add(InlineKeyboardButton(
        text="Забронировать",
        callback_data=f"excursion_book_{excursion_id}"
    ))
    keyboard.add(InlineKeyboardButton(
        text="К списку экскурсий",
        callback_data="back_to_excursions_list"
    ))
    keyboard.adjust(1)  # Все кнопки вертикально
    return keyboard.as_markup()


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
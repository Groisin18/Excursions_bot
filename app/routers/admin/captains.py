from aiogram import F, Router
from aiogram.types import Message

from app.database.managers import UserManager
from app.database.session import async_session
from app.middlewares import AdminMiddleware
from app.admin_panel.keyboards_adm import admin_main_menu, captains_submenu
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_captains")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УПРАВЛЕНИЕ КАПИТАНАМИ =====

@router.message(F.text == "Список капитанов")
async def show_captains_list(message: Message):
    """Показать список капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил список капитанов")

    try:
        async with async_session() as session:
            user_manager = UserManager(session)
            captains_data = await user_manager.get_captains_with_stats()

            if not captains_data:
                logger.debug("Капитаны не найдены")
                await message.answer("Капитаны не найдены", reply_markup=captains_submenu())
                return

            logger.info(f"Найдено капитанов: {len(captains_data)}")
            response = "Список капитанов:\n\n"
            for data in captains_data:
                captain = data['captain']
                stats = data['stats']

                response += (
                    f"Имя: {captain.full_name}\n"
                    f"Телефон: {captain.phone_number}\n"
                    f"Рейсов: {stats.get('total_bookings', 0)}\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список капитанов отправлен администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка капитанов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка капитанов", reply_markup=captains_submenu())


@router.message(F.text == "График работы")
async def captains_schedule(message: Message):
    """График работы капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил график работы капитанов")

    try:
        await message.answer("Функция 'График работы капитанов' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Расчет зарплаты")
async def calculate_salaries(message: Message):
    """Расчет зарплат капитанов"""
    logger.info(f"Администратор {message.from_user.id} запросил расчет зарплат")

    try:
        await message.answer("Функция 'Расчет зарплаты капитанов' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Добавить капитана")
async def add_captain(message: Message):
    """Добавление нового капитана"""
    logger.info(f"Администратор {message.from_user.id} хочет добавить капитана")

    try:
        await message.answer("Для добавления нового капитана ему сначала нужно зарегистрироваться в качестве клиента.\n"
                             "Затем через админ-панель, Клиенты -> Поиск клиента найдите его запись по фамилии-имени или номеру телефона.\n"
                             "Далее в клавиатуре нажмите пункт 'Изменить статус' и выберите роль капитана.\n")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
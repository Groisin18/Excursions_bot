import asyncio

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as main_kb

from app.admin_panel.keyboards_adm import (
    admin_main_menu, excursions_submenu, captains_submenu, clients_submenu,
    bookings_submenu, statistics_submenu, finances_submenu,
    notifications_submenu, settings_submenu
)
from app.database.repositories import UserRepository
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_main")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== ОСНОВНЫЕ ХЭНДЛЕРЫ =====

@router.message(Command("admin"))
async def admin_start(message: Message):
    """Вход в админ-панель"""
    logger.info(f"Администратор {message.from_user.id} ({message.from_user.username}) вошел в админ-панель")

    try:
        await message.answer(
            "Панель администратора\n"
            "Выберите категорию для управления:",
            reply_markup=admin_main_menu()
        )
        logger.debug(f"Главное меню показано пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при входе в админ-панель для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Ошибка при загрузке админ-панели", reply_markup=main_kb.main)


@router.message(Command("adminhelp"))
async def adminhelp_command(message: Message):
    """Команда помощи для администраторов"""
    logger.debug(f"Запрос adminhelp от пользователя {message.from_user.id}")

    try:
        await message.reply(
            'Привет! Это команда /adminhelp.\n\n'
            '/help - общий список команд\n'
            '/admin - админ-панель\n'
            '/promote (номер телефона) - назначить пользователя админом, капитаном, или разжаловать в клиенты\n'
            '/dashboard - дашборд админа\n'
            '/statistic_today - детальная статистика за сегодня\n'
            '/report - генерация отчета за период',
            reply_markup=main_kb.main
        )
        logger.debug(f"Adminhelp отправлен пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки adminhelp: {e}", exc_info=True)


@router.message(F.text == "Выход")
async def admin_exit(message: Message):
    """Выход из админ-панели"""
    logger.info(f"Администратор {message.from_user.id} вышел из админ-панели")

    try:
        await message.answer(
            "Вы вышли из админ-панели", reply_markup=main_kb.main)
    except Exception as e:
        logger.error(f"Ошибка при выходе из админ-панели: {e}", exc_info=True)


@router.message(F.text == "Назад", StateFilter(None))
async def back_handler(message: Message, state: FSMContext):
    """Обработка кнопки Назад - возврат в главное меню (только без активного состояния)"""
    logger.debug(f"Администратор {message.from_user.id} нажал 'Назад' без активного состояния")

    try:
        await state.clear()
        await message.answer(
            "Главное меню администратора:",
            reply_markup=admin_main_menu()
        )
        logger.debug(f"Пользователь {message.from_user.id} вернулся в главное меню")
    except Exception as e:
        logger.error(f"Ошибка обработки кнопки 'Назад': {e}", exc_info=True)


@router.callback_query(F.data == 'back_to_admin_panel')
async def callback_back_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка возврата в админ-панель из колбэка"""
    logger.debug(f"Администратор {callback.from_user.id} вернулся в админ-панель из колбэка")

    try:
        await state.clear()
        await callback.answer("Действие отменено")
        await callback.message.answer(
            "Главное меню администратора:",
            reply_markup=admin_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка обработки колбэка возврата: {e}", exc_info=True)


# ===== ПЕРЕХОД В ПОДМЕНЮ =====

@router.message(F.text == "Экскурсии")
async def excursions_main(message: Message):
    """Переход в управление экскурсиями"""
    logger.info(f"Администратор {message.from_user.id} открыл управление экскурсиями")

    try:
        await message.answer(
            "Управление экскурсиями:",
            reply_markup=excursions_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия управления экскурсиями: {e}", exc_info=True)
        await message.answer("Ошибка открытия управления экскурсиями", reply_markup=admin_main_menu())

@router.message(F.text == "Капитаны")
async def captains_main(message: Message):
    """Переход в управление капитанами"""
    logger.info(f"Администратор {message.from_user.id} открыл управление капитанами")

    try:
        await message.answer(
            "Управление капитанами:",
            reply_markup=captains_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия управления капитанами: {e}", exc_info=True)
        await message.answer("Ошибка открытия управления капитанами", reply_markup=admin_main_menu())


@router.message(F.text == "Клиенты")
async def clients_main(message: Message):
    """Переход в управление клиентами"""
    logger.info(f"Администратор {message.from_user.id} открыл управление клиентами")

    try:
        await message.answer(
            "Управление клиентами:",
            reply_markup=clients_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия управления клиентами: {e}", exc_info=True)
        await message.answer("Ошибка открытия управления клиентами", reply_markup=admin_main_menu())


@router.message(F.text == "Записи")
async def bookings_main(message: Message):
    """Переход в управление записями"""
    logger.info(f"Администратор {message.from_user.id} открыл управление записями")

    try:
        await message.answer(
            "Управление записями:",
            reply_markup=bookings_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия управления записями: {e}", exc_info=True)
        await message.answer("Ошибка открытия управления записями", reply_markup=admin_main_menu())


@router.message(F.text == "Статистика")
async def statistics_main(message: Message):
    """Переход в статистику"""
    logger.info(f"Администратор {message.from_user.id} открыл статистику")

    try:
        await message.answer(
            "Статистика:",
            reply_markup=statistics_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия статистики: {e}", exc_info=True)
        await message.answer("Ошибка открытия статистики", reply_markup=admin_main_menu())


@router.message(F.text == "Финансы")
async def finances_main(message: Message):
    """Переход в финансы"""
    logger.info(f"Администратор {message.from_user.id} открыл финансовый раздел")

    try:
        await message.answer(
            "Финансы:",
            reply_markup=finances_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия финансов: {e}", exc_info=True)
        await message.answer("Ошибка открытия финансов", reply_markup=admin_main_menu())


@router.message(F.text == "Уведомления")
async def notifications_main(message: Message):
    """Переход в уведомления"""
    logger.info(f"Администратор {message.from_user.id} открыл уведомления")

    try:
        await message.answer(
            "Управление уведомлениями:",
            reply_markup=notifications_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия уведомлений: {e}", exc_info=True)
        await message.answer("Ошибка открытия уведомлений", reply_markup=admin_main_menu())


@router.message(F.text == "Настройки")
async def settings_main(message: Message):
    """Переход в настройки"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки")

    try:
        await message.answer(
            "Настройки системы:",
            reply_markup=settings_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия настроек: {e}", exc_info=True)
        await message.answer("Ошибка открытия настроек", reply_markup=admin_main_menu())


@router.message(F.text == "Назад")
async def back_from_submenu(message: Message, state: FSMContext):
    """Возврат из любого подменю в главное меню"""
    current_state = await state.get_state()
    logger.debug(f"Администратор {message.from_user.id} нажал 'Назад' из подменю. Состояние: {current_state}")

    try:
        await state.clear()
        await message.answer(
            "Главное меню администратора:",
            reply_markup=admin_main_menu()
        )
        logger.debug(f"Пользователь {message.from_user.id} вернулся в главное меню из подменю")
    except Exception as e:
        logger.error(f"Ошибка возврата из подменю: {e}", exc_info=True)
        await message.answer("Ошибка", reply_markup=admin_main_menu())



# ===== КОМАНДЫ АДМИНИСТРИРОВАНИЯ =====

@router.message(Command("promote"))
async def promote_command(message: Message):
    """Команда для изменения статуса админа, капитана, клиента"""
    logger.info(f"Администратор {message.from_user.id} использует команду /promote")
    if len(message.text.split()) > 1:
        try:
            target_phone = message.text.split()[1]
            masked_phone = target_phone[:3] + "***" + target_phone[-3:] if len(target_phone) > 6 else "***"
            logger.info(f"Поиск пользователя по телефону {masked_phone} для изменения статуса")

            async with async_session() as session:
                user_repo = UserRepository(session)
                to_admin_user = await user_repo.get_by_phone(target_phone)

            if to_admin_user is None:
                logger.warning(f"Пользователь с телефоном {masked_phone} не найден")
                await message.answer("Пользователь не найден")
                return

            logger.info(f"Найден пользователь {to_admin_user.id} ({to_admin_user.full_name}) для изменения статуса")

            # Создаем клавиатуру с данными в callback
            from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Сделать администратором', callback_data=f"confirm_give_adm:{to_admin_user.telegram_id}"),
                InlineKeyboardButton(text='Сделать капитаном', callback_data=f"confirm_give_cap:{to_admin_user.telegram_id}")],
                [InlineKeyboardButton(text='Разжаловать в клиенты', callback_data=f"confirm_give_clt:{to_admin_user.telegram_id}"),
                InlineKeyboardButton(text='Нет', callback_data="back_to_admin_panel")],
                ])
            text = (
                "Вы хотите изменить статус пользователя:\n"
                f"{to_admin_user.full_name}\n"
                f"Telegram ID: {to_admin_user.telegram_id}\n"
                f"Текущий статус: {str(to_admin_user.role).split('.')[1]}"
            )
            await message.answer(text, reply_markup=keyboard)
            logger.debug(f"Диалог изменения статуса показан для пользователя {to_admin_user.id}")

        except ValueError as e:
            logger.error(f"Ошибка парсинга номера телефона: {e}")
            await message.answer("Неверный формат номера телефона")
        except Exception as e:
            logger.error(f"Ошибка в команде /promote: {e}", exc_info=True)
            await message.answer("Произошла ошибка", reply_markup=admin_main_menu())
    else:
        logger.debug(f"Администратор {message.from_user.id} использовал /promote без параметров")
        await message.answer("Использование: /promote (номер телефона)")


@router.callback_query(F.data.startswith('confirm_give_adm:'))
async def promote_to_admin(callback: CallbackQuery):
    """Повышение до администратора"""
    target_user_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} повышает пользователя {target_user_id} до администратора")

    await callback.answer('Меняем статус пользователя...')

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            target_user = await user_repo.get_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для повышения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await user_repo.promote_to_admin(target_user)

            if success:
                logger.info(f"Пользователь {target_user_id} ({user_name}) успешно повышен до администратора")
                await callback.message.answer(
                    f"{user_name} успешно стал администратором",
                    reply_markup=admin_main_menu()
                )
            else:
                logger.warning(f"Не удалось повысить пользователя {target_user_id} до администратора")
                await callback.message.answer(
                    "Ошибка при назначении администратора",
                    reply_markup=admin_main_menu()
                )

    except Exception as e:
        logger.error(f"Ошибка повышения пользователя {target_user_id} до администратора: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при назначении", reply_markup=admin_main_menu())


@router.callback_query(F.data.startswith('confirm_give_cap:'))
async def promote_to_captain(callback: CallbackQuery):
    """Повышение до капитана"""
    target_user_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} повышает пользователя {target_user_id} до капитана")

    await callback.answer('Меняем статус пользователя...')

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            target_user = await user_repo.get_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для повышения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await user_repo.promote_to_captain(target_user)

            if success:
                logger.info(f"Пользователь {target_user_id} ({user_name}) успешно повышен до капитана")
                await callback.message.answer(
                    f"{user_name} успешно стал капитаном",
                    reply_markup=admin_main_menu()
                )
            else:
                logger.warning(f"Не удалось повысить пользователя {target_user_id} до капитана")
                await callback.message.answer(
                    "Ошибка при назначении капитана",
                    reply_markup=admin_main_menu()
                )

    except Exception as e:
        logger.error(f"Ошибка повышения пользователя {target_user_id} до капитана: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при назначении", reply_markup=admin_main_menu())


@router.callback_query(F.data.startswith('confirm_give_clt:'))
async def promote_to_client(callback: CallbackQuery):
    """Понижение до клиента"""
    target_user_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} понижает пользователя {target_user_id} до клиента")

    await callback.answer('Меняем статус пользователя...')

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            target_user = await user_repo.get_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для понижения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await user_repo.promote_to_client(target_user)

            if success:
                logger.info(f"Пользователь {target_user_id} ({user_name}) успешно понижен до клиента")
                await callback.message.answer(
                    f"{user_name} теперь обычный клиент",
                    reply_markup=admin_main_menu()
                )
            else:
                logger.warning(f"Не удалось понизить пользователя {target_user_id} до клиента")
                await callback.message.answer(
                    "Ошибка при изменении статуса",
                    reply_markup=admin_main_menu()
                )

    except Exception as e:
        logger.error(f"Ошибка понижения пользователя {target_user_id} до клиента: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при изменении статуса", reply_markup=admin_main_menu())
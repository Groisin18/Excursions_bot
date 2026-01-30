import asyncio

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime
from sqlalchemy import select, text

import app.user_panel.keyboards as main_kb

from app.admin_panel.keyboards_adm import (
    admin_main_menu, excursions_submenu, captains_submenu, clients_submenu,
    bookings_submenu, statistics_submenu, finances_submenu, notifications_submenu,
    settings_submenu
)
from app.database.requests import DatabaseManager
from app.database.models import engine, async_session, User
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
        await message.answer("Ошибка при загрузке админ-панели")


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
            '/report - генерация отчета за период\n'
            '/debug - проверка состояния и подключения к базе данных (для сисадмина!)\n'
            '/reset_db - принудительное отключение сессий базы данных (для сисадмина!)',
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
            "Вы вышли из админ-панели",
            reply_markup=main_kb.main
        )
        logger.debug(f"Пользователь {message.from_user.id} успешно вышел из админ-панели")
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
async def promote_to_admin_command(message: Message):
    """Команда для изменения статуса админа, капитана, клиента"""
    logger.info(f"Администратор {message.from_user.id} использует команду /promote")
    if len(message.text.split()) > 1:
        try:
            target_phone = message.text.split()[1]
            masked_phone = target_phone[:3] + "***" + target_phone[-3:] if len(target_phone) > 6 else "***"
            logger.info(f"Поиск пользователя по телефону {masked_phone} для изменения статуса")

            async with async_session() as session:
                db_manager = DatabaseManager(session)
                to_admin_user = await db_manager.get_user_by_phone(target_phone)

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
            await message.answer("Произошла ошибка")
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
            db_manager = DatabaseManager(session)
            target_user = await db_manager.get_user_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для повышения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await db_manager.promote_to_admin(target_user)

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
        await callback.message.answer("Произошла ошибка при назначении")


@router.callback_query(F.data.startswith('confirm_give_cap:'))
async def promote_to_captain(callback: CallbackQuery):
    """Повышение до капитана"""
    target_user_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} повышает пользователя {target_user_id} до капитана")

    await callback.answer('Меняем статус пользователя...')

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            target_user = await db_manager.get_user_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для повышения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await db_manager.promote_to_captain(target_user)

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
        await callback.message.answer("Произошла ошибка при назначении")


@router.callback_query(F.data.startswith('confirm_give_clt:'))
async def promote_to_client(callback: CallbackQuery):
    """Понижение до клиента"""
    target_user_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} понижает пользователя {target_user_id} до клиента")

    await callback.answer('Меняем статус пользователя...')

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            target_user = await db_manager.get_user_by_telegram_id(target_user_id)

            if not target_user:
                logger.error(f"Пользователь {target_user_id} не найден для понижения")
                await callback.message.answer("Пользователь не найден")
                return

            user_name = target_user.full_name
            success = await db_manager.promote_to_client(target_user)

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
        await callback.message.answer("Произошла ошибка при изменении статуса")


@router.callback_query(F.data == 'no_action')
async def redact_exc_data(callback: CallbackQuery):
    """Пустой обработчик для отмены действий"""
    logger.debug(f"Пользователь {callback.from_user.id} отменил действие через 'no_action'")
    await callback.answer("Действие отменено")


# ===== КОМАНДЫ ДЕБАГА =====

@router.message(Command('debug'))
async def cmd_debug(message: Message, state: FSMContext):
    """Команда отладки"""
    logger.info(f"Запрос debug от пользователя {message.from_user.id}")

    try:
        async with async_session() as session:
            # Проверяем подключение к БД
            result = await session.execute(select(1))
            test = result.scalar()

            # Проверяем пользователя
            user = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = user.scalar_one_or_none()
            current_state = await state.get_state()

            debug_info = {
                "db_connection": "OK" if test == 1 else "FAILED",
                "user_found": bool(user),
                "user_telegram_id": message.from_user.id,
                "user_date_of_birth": user.date_of_birth if user else None,
                "current_fsm_state": current_state
            }

            logger.info(f"Debug info для пользователя {message.from_user.id}: {debug_info}")
            await message.answer(f"Debug info:\n{debug_info}")

    except Exception as e:
        logger.error(f"Debug error для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(f"Debug error: {e}")


async def reset_database_sessions():
    """Принудительно сбрасывает все сессии БД"""
    logger.warning("Принудительный сброс сессий БД")

    try:
        # Закрываем все соединения в engine
        if 'engine' in globals():
            await engine.dispose()
            logger.info("Engine соединения сброшены")
            return True
        else:
            logger.warning("Engine не найден в глобальной области видимости")
            return False
    except Exception as e:
        logger.error(f"Ошибка при сбросе сессий: {e}", exc_info=True)
        return False


@router.message(Command('reset_db'))
async def cmd_reset_db(message: Message):
    """Принудительный сброс сессий БД"""
    logger.warning(f"Пользователь {message.from_user.id} использует команду reset_db")

    try:
        success = await reset_database_sessions()
        if success:
            logger.info(f"Сессии БД сброшены по запросу пользователя {message.from_user.id}")
            await message.answer("Сессии БД сброшены! Бот должен работать нормально.")
        else:
            logger.error(f"Не удалось сбросить сессии БД для пользователя {message.from_user.id}")
            await message.answer("Ошибка при сбросе сессий БД")
    except Exception as e:
        logger.error(f"Ошибка выполнения reset_db: {e}", exc_info=True)
        await message.answer(f"Ошибка сброса: {e}")



@router.message(Command('optimize_db'))
async def cmd_optimize_db(message: Message):
    """Оптимизация базы данных (только для админов)"""
    # Отправляем начальное сообщение
    status_msg = await message.answer("Начинаю оптимизацию БД...")
    start_time = datetime.now()
    try:
        # Шаг 1: Быстрые оптимизации (не блокирующие)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA optimize"))
            analysis = await result.fetchone()
            await status_msg.edit_text(
                f"Анализ БД выполнен:\n"
                f"Рекомендации: {analysis[0] if analysis else 'нет'}"
            )
            await asyncio.sleep(1)

            # Шаг 2: Checkpoint WAL (быстрый)
            await conn.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
            await status_msg.edit_text("WAL checkpoint выполнен")
            await asyncio.sleep(1)

            # Шаг 3: Анализ индексов
            await conn.execute(text("ANALYZE"))
            await status_msg.edit_text("Анализ индексов выполнен")
            await asyncio.sleep(1)

        # Шаг 4: Медленные операции (спрашиваем подтверждение)
        confirm_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="VACUUM (Занимает время! Только при разросшейся БД)",
                        callback_data="db_vacuum"
                    ),
                    InlineKeyboardButton(
                        text="Только быстрая оптимизация",
                        callback_data="db_fast_only"
                    )
                ]
            ]
        )

        await status_msg.edit_text(
            f"Быстрая оптимизация завершена за {(datetime.now() - start_time).total_seconds():.1f} сек\n"
            f"Хотите выполнить полную оптимизацию (VACUUM)?\n"
            f"Это может занять время и заблокировать БД на 1-10 мин!\n\n"
            "Когда нужно делать VACUUM?\n"
            "После массового удаления - например, удалил 1000+ старых бронирований\n"
            "Раз в месяц/квартал - профилактическая оптимизация\n"
            "Когда БД выросла вдвое - без видимых причин\n"
            "Перед бэкапом - чтобы бэкап был меньше\n\n"
            "Когда не нужно делать VACUUM?\n"
            "В пиковое время - бот будет недоступен 1-10 минут\n"
            "На маленькой БД (< 100MB) - эффект минимальный\n"
            "Если нет свободного места на сервере - VACUUM временно требует 2x мест\n\n"
            "VACUUM Не удаляет таблицы, действующие данные, не меняет структуру БД, не сбрасывает счетчики\n",
            reply_markup=confirm_keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка оптимизации БД: {e}")
        await message.answer(f"Ошибка оптимизации: {e}")
        if status_msg:
            await status_msg.delete()


@router.callback_query(F.data.startswith('db_'))
async def handle_db_optimization_confirm(callback: CallbackQuery):
    """Обработка подтверждения оптимизации"""
    await callback.answer('')
    if callback.data == "db_fast_only":
        await callback.message.edit_text("Быстрая оптимизация завершена!")
        return

    # Полная оптимизация с VACUUM
    status_msg = await callback.message.edit_text(
        "Запускаю полную оптимизацию (VACUUM)...\n"
        "Это может занять несколько минут!"
    )
    start_time = datetime.now()
    try:
        async with engine.connect() as conn:
            db_size_before = (await conn.execute(
                text("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
            )).scalar_one()
            try:
                await asyncio.wait_for(
                    conn.execute(text("VACUUM")),
                    timeout=600  # 10 минут максимум
                )
            except asyncio.TimeoutError:
                await status_msg.edit_text("VACUUM превысил лимит времени (10 минут)")
                return

            db_size_after = (await conn.execute(
                text("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
            )).scalar_one()
            stats_result = await conn.execute(text("PRAGMA stats"))
            stats = await stats_result.fetchone()
        saved_space = db_size_before - db_size_after
        saved_percent = (saved_space / db_size_before * 100) if db_size_before > 0 else 0
        time_taken = (datetime.now() - start_time).total_seconds()
        report = (
            f"Полная оптимизация БД завершена!\n"
            f"Время выполнения: {time_taken:.1f} сек\n"
            f"Размер БД: {db_size_after / 1024 / 1024:.2f} MB\n"
            f"Сэкономлено: {saved_space / 1024 / 1024:.2f} MB ({saved_percent:.1f}%)\n"
            f"Статистика: {stats[0] if stats else 'N/A'}"
        )

        await status_msg.edit_text(report)

        logger.info(
            f"Optimization completed: "
            f"time={time_taken:.1f}s, "
            f"saved={saved_space / 1024 / 1024:.2f}MB, "
            f"admin={callback.from_user.id}"
        )

    except asyncio.TimeoutError:
        await status_msg.edit_text("Операция VACUUM превысила лимит времени")
        logger.warning("VACUUM timeout exceeded")

    except Exception as e:
        logger.error(f"Ошибка при выполнении VACUUM: {e}")
        await status_msg.edit_text(f"Ошибка при оптимизации: {e}")
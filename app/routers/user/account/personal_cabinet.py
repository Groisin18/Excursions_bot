'''
Роутер основных хэндлеров личного кабинета пользователя
'''
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as kb

from app.user_panel.states import Reg_user
from app.database.requests import DatabaseManager
from app.database.models import async_session
from app.utils.logging_config import get_logger


router = Router(name="personal_cabinet")

logger = get_logger(__name__)


@router.message(F.text == 'Личный кабинет')
async def registration_data(message: Message, state: FSMContext):
    """Обработчик личного кабинета - объединенная логика"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} открыл личный кабинет")
    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            user = await db.get_user_by_telegram_id(user_telegram_id)
            if user:
                logger.debug(f"Пользователь {user_telegram_id} зарегистрирован, показываем кабинет")
                has_children = await db.user_has_children(user.id)
                keyboard = await kb.registration_data_menu_builder(has_children=has_children)
                user_info = (
                    f"Ваш личный кабинет\n\n"
                    f"Имя: {user.full_name or 'Не указано'}\n"
                    f"Телефон: {user.phone_number or 'Не указано'}\n"
                    f"Email: {user.email or 'Не указано'}\n"
                )
                if has_children:
                    children = await db.get_children_users(user.id)
                    user_info += f"\nДетей зарегистрировано: {len(children)}"
                await message.answer(user_info, reply_markup=keyboard)
            else:
                logger.debug(f"Пользователь {user_telegram_id} не зарегистрирован, начало регистрации")
                await state.set_state(Reg_user.is_token)
                await message.answer(
                    'Для начала давайте зарегистрируемся!\n\n'
                    'Если вас ранее регистрировал другой человек, то выдается '
                    'специальный токен (набор символов). Есть ли он у вас?',
                    reply_markup=kb.inline_is_token
                )
    except Exception as e:
        logger.error(f"Ошибка в личном кабинете для пользователя {user_telegram_id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при открытии личного кабинета. Попробуйте еще раз.",
            reply_markup=kb.main
        )

@router.callback_query(F.data == 'child_choice')
async def child_choice(callback: CallbackQuery):
    """Показать список детей с данными для редактирования"""
    user_telegram_id = callback.from_user.id

    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            user = await db.get_user_by_telegram_id(user_telegram_id)

            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return

            children = await db.get_children_users(user.id)

            if not children:
                await callback.answer("У вас нет зарегистрированных детей", show_alert=True)
                return

            # Создаем сообщение с информацией о детях
            message_text = "Ваши дети\n\n"

            for i, child in enumerate(children, 1):
                message_text += f"{i}. {child.full_name}\n"

                if hasattr(child, 'verification_token') and child.verification_token:
                    message_text += f"   Токен: {child.verification_token}\n"

                if hasattr(child, 'date_of_birth') and child.date_of_birth:
                    birth_date = child.date_of_birth
                    if isinstance(birth_date, str):
                        message_text += f"   Дата рождения: {birth_date}\n"
                    else:
                        message_text += f"   Дата рождения: {birth_date.strftime('%d.%m.%Y')}\n"

                if hasattr(child, 'address') and child.address:
                    message_text += f"   Адрес: {child.address}\n"

                if hasattr(child, 'weight') and child.weight:
                    message_text += f"   Вес: {child.weight} кг\n"

                message_text += "\n"

            message_text += "\nВыберите ребенка для редактирования:"

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            for child in children:
                builder.button(
                    text=f"{child.full_name}",
                    callback_data=f"edit_child:{child.id}"
                )
            builder.button(text="Добавить ребенка", callback_data="reg_child")
            builder.button(text="Назад в кабинет", callback_data="back_to_cabinet")
            builder.button(text="В главное меню", callback_data="back_to_main")

            builder.adjust(1)

            try:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=builder.as_markup()
                )
            except Exception:
                await callback.message.answer(
                    message_text,
                    reply_markup=builder.as_markup()
                )

    except Exception as e:
        logger.error(f"Ошибка показа данных детей: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data == 'back_to_cabinet')
async def back_to_cabinet(callback: CallbackQuery):
    """Вернуться в личный кабинет"""
    user_id = callback.from_user.id

    try:
        async with async_session() as session:
            db = DatabaseManager(session)

            user = await db.get_user_by_telegram_id(user_id)
            if not user:
                await callback.answer("Ошибка", show_alert=True)
                return

            has_children = await db.user_has_children(user.id)
            keyboard = await kb.registration_data_menu_builder(has_children=has_children)

            user_info = (
                f"Ваш личный кабинет\n\n"
                f"Имя: {user.full_name or 'Не указано'}\n"
                f"Телефон: {user.phone_number or 'Не указано'}\n"
                f"Email: {user.email or 'Не указано'}\n"
            )

            if has_children:
                children = await db.get_children_users(user.id)
                user_info += f"\nДетей зарегистрировано: {len(children)}"

            await callback.message.edit_text(
                user_info,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Ошибка возврата в кабинет: {e}")
        await callback.answer("Ошибка", show_alert=True)
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as kb
from app.utils.logging_config import get_logger

router = Router(name="fallback")

logger = get_logger(__name__)


@router.callback_query(F.data == 'no_action')
async def redact_exc_data(callback: CallbackQuery):
    """Пустой обработчик для необрабатываемых инлайн-кнопок"""
    try:
        logger.debug(f"Пользователь {callback.from_user.id} нажал кнопку 'no_action'")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в обработчике no_action: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(F.content_type.in_({'photo', 'video', 'document', 'sticker', 'voice'}))
async def unsupported_content(message: Message):
    """Обработка неподдерживаемых типов контента"""
    logger.info(
        f"Неподдерживаемый контент от пользователя {message.from_user.id}: "
        f"тип={message.content_type}"
    )
    try:
        content_type_names = {
            'photo': 'фото',
            'video': 'видео',
            'document': 'документ',
            'sticker': 'стикер',
            'voice': 'голосовое сообщение'
        }
        content_type_name = content_type_names.get(message.content_type, message.content_type)
        await message.answer(
            f'Я не могу обработать {content_type_name}. '
            f'Пожалуйста, используйте текстовые сообщения или кнопки меню.',
            reply_markup=kb.main
        )
        logger.debug(f"Пользователю {message.from_user.id} отправлено сообщение о неподдерживаемом контенте")
    except Exception as e:
        logger.error(f"Ошибка обработки неподдерживаемого контента: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=kb.main)


@router.message(F.text.contains('/'))
async def unknown_command(message: Message):
    """Обработка неизвестных команд (со слешем)"""
    logger.info(
        f"Неизвестная команда от пользователя {message.from_user.id}: '{message.text}'"
    )
    try:
        command = message.text.split()[0] if message.text else ""
        if command.startswith('/'):
            logger.debug(f"Пользователь {message.from_user.id} ввел неизвестную команду: {command}")
        await message.answer(
            f'Неизвестная команда. Используйте кнопки меню или введите /help для списка команд.',
            reply_markup=kb.main
        )
    except Exception as e:
        logger.error(f"Ошибка обработки неизвестной команды: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=kb.main)


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка неизвестных колбэков"""
    logger.warning(
        f"Неизвестный колбэк от пользователя {callback.from_user.id} "
        f"({callback.from_user.username}): data='{callback.data}', "
        f"сообщение_id={callback.message.message_id if callback.message else 'N/A'}"
    )
    try:
        await callback.answer('Произошла ошибка', show_alert=True)
        current_state = await state.get_state()
        if current_state:
            logger.debug(f"Текущее состояние FSM: {current_state}")
        await state.clear()
        logger.debug(f"Состояние FSM очищено для пользователя {callback.from_user.id}")

        await callback.message.answer(
            'Мы извиняемся. Произошла ошибка. Выберите другой пункт меню.',
            reply_markup=kb.main
        )
        logger.debug(f"Пользователю {callback.from_user.id} отправлено сообщение об ошибке")
    except Exception as e:
        logger.error(f"Ошибка обработки неизвестного колбэка: {e}", exc_info=True)


@router.message()
async def unknown_message(message: Message, state: FSMContext):
    """Обработка неизвестных сообщений"""
    logger.warning(
        f"Неизвестное сообщение от пользователя {message.from_user.id} "
        f"({message.from_user.username}): text='{message.text}', "
        f"тип={message.content_type}"
    )
    try:
        current_state = await state.get_state()
        if current_state:
            logger.info(f"Пользователь {message.from_user.id} в состоянии {current_state} отправил неизвестное сообщение")
        await state.clear()
        logger.debug(f"Состояние FSM очищено для пользователя {message.from_user.id}")

        await message.answer(
            'Это неизвестная команда. Пожалуйста, используйте кнопки меню.',
            reply_markup=kb.main
        )
        logger.debug(f"Пользователю {message.from_user.id} отправлено сообщение о неизвестной команде")
    except Exception as e:
        logger.error(f"Ошибка обработки неизвестного сообщения: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.", reply_markup=kb.main)
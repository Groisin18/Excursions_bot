from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.admin_panel.states_adm import AdminStates
from app.admin_panel.keyboards_adm import (
    admin_main_menu, notifications_submenu, cancel_button
)

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_notification")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ===== УВЕДОМЛЕНИЯ =====

@router.message(F.text == "Отправить уведомление")
async def send_notification_start(message: Message, state: FSMContext):
    """Начало отправки уведомления"""
    logger.info(f"Администратор {message.from_user.id} начал отправку уведомления")

    try:
        await message.answer(
            "Введите текст уведомления:",
            reply_markup=cancel_button()
        )
        await state.set_state(AdminStates.waiting_for_notification_text)
        logger.debug(f"Пользователь {message.from_user.id} перешел в состояние отправки уведомления")
    except Exception as e:
        logger.error(f"Ошибка начала отправки уведомления: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=notifications_submenu()
        )


@router.message(AdminStates.waiting_for_notification_text)
async def send_notification_process(message: Message, state: FSMContext):
    """Обработка текста уведомления"""
    notification_text = message.text
    logger.info(f"Администратор {message.from_user.id} отправил уведомление (длина: {len(notification_text)} символов)")

    try:
        # Здесь можно добавить логику выбора получателей
        # Пока отправляем только отправителю как пример
        await message.answer(
            f"Уведомление будет отправлено:\n\n{notification_text}\n\n"
            f"Функция массовой рассылки в разработке.",
            reply_markup=notifications_submenu()
        )
        logger.debug(f"Уведомление обработано для администратора {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка обработки уведомления: {e}", exc_info=True)
        await message.answer("Ошибка при обработке уведомления", reply_markup=notifications_submenu())
        await state.clear()



@router.message(F.text == "Отмена", AdminStates.waiting_for_notification_text)
async def cancel_notification(message: Message, state: FSMContext):
    """Отмена отправки уведомления"""
    logger.info(f"Администратор {message.from_user.id} отменил отправку уведомления")

    try:
        await state.clear()
        await message.answer(
            "Отправка уведомления отменена",
            reply_markup=notifications_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка отмены уведомления: {e}", exc_info=True)
        await message.answer("Ошибка", reply_markup=notifications_submenu())
        await state.clear()

@router.message(F.text == "Напоминания")
async def notifications_reminders(message: Message):
    """Управление напоминаниями"""
    logger.info(f"Администратор {message.from_user.id} открыл управление напоминаниями")

    try:
        await message.answer("Функция 'Напоминания' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


@router.message(F.text == "Шаблоны сообщений")
async def notifications_templates(message: Message):
    """Управление шаблонами сообщений"""
    logger.info(f"Администратор {message.from_user.id} открыл управление шаблонами сообщений")

    try:
        await message.answer("Функция 'Шаблоны сообщений' в разработке")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
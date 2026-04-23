# app/routers/admin/notification.py

"""Роутер для управления массовыми рассылками"""

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.admin_panel.states_adm import AdminMassNotification
from app.admin_panel.keyboards_adm import (
    notifications_submenu, admin_main_menu, cancel_button,
    notification_confirmation_keyboard
)
from app.database.session import async_session
from app.database.repositories.notification_repository import NotificationRepository
from app.database.models import UserRole
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

router = Router(name="admin_notification")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.message(F.text == "Отправить всем клиентам")
async def start_mass_notification_clients(message: Message, state: FSMContext):
    """Начало массовой рассылки клиентам"""
    logger.info(f"Администратор {message.from_user.id} начал рассылку клиентам")

    await state.update_data(audience_type=UserRole.client.value)
    await state.set_state(AdminMassNotification.waiting_for_message)

    await message.answer(
        "Введите текст сообщения для рассылки всем клиентам:",
        reply_markup=cancel_button()
    )


@router.message(F.text == "Отправить всем капитанам")
async def start_mass_notification_captains(message: Message, state: FSMContext):
    """Начало массовой рассылки капитанам"""
    logger.info(f"Администратор {message.from_user.id} начал рассылку капитанам")

    await state.update_data(audience_type=UserRole.captain.value)
    await state.set_state(AdminMassNotification.waiting_for_message)

    await message.answer(
        "Введите текст сообщения для рассылки всем капитанам:",
        reply_markup=cancel_button()
    )


@router.message(AdminMassNotification.waiting_for_message)
async def process_message_text(message: Message, state: FSMContext):
    """Обработка текста сообщения"""
    message_text = message.text

    if len(message_text) > 4000:
        await message.answer(
            "Сообщение слишком длинное. Максимум 4000 символов.\n\n"
            "Сократите текст и отправьте снова.",
            reply_markup=cancel_button()
        )
        return

    await state.update_data(message_text=message_text)
    await state.set_state(AdminMassNotification.waiting_for_confirmation)

    await message.answer(
        f"Предпросмотр сообщения:\n\n{message_text}\n\nПодтвердите отправку:",
        reply_markup=notification_confirmation_keyboard()
    )


@router.callback_query(AdminMassNotification.waiting_for_confirmation, F.data == "confirm_send")
async def confirm_send(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отправки рассылки"""
    data = await state.get_data()
    audience_type_value = data.get("audience_type")
    message_text = data.get("message_text")

    if not audience_type_value or not message_text:
        await callback.message.answer(
            "Ошибка: данные рассылки потеряны. Начните заново.",
            reply_markup=notifications_submenu()
        )
        await state.clear()
        await callback.answer()
        return

    # Восстанавливаем Enum из значения
    audience_type = UserRole(audience_type_value)

    async with async_session() as session:
        repo = NotificationRepository(session)

        notification = await repo.create_notification(
            message=message_text,
            audience_type=audience_type,
            created_by_id=callback.from_user.id
        )
        await session.commit()

        logger.info(f"Создана рассылка #{notification.id} для {audience_type.value}")

        audience_name = "клиентам" if audience_type == UserRole.client else "капитанам"

        await callback.message.edit_text(
            f"Рассылка создана и поставлена в очередь.\n\n"
            f"Аудитория: {audience_name}\n"
            f"ID рассылки: {notification.id}\n\n"
            f"Уведомление о завершении будет отправлено вам в личные сообщения.",
            reply_markup=notifications_submenu()
        )

    await state.clear()
    await callback.answer()


@router.callback_query(AdminMassNotification.waiting_for_confirmation, F.data == "cancel_send")
async def cancel_send(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки рассылки"""
    await callback.message.edit_text("Рассылка отменена.")
    await callback.message.answer(
        "Управление уведомлениями:",
        reply_markup=notifications_submenu()
    )
    await state.clear()
    await callback.answer()


@router.message(F.text == "Назад")
async def back_to_admin_menu(message: Message, state: FSMContext):
    """Возврат в главное меню администратора"""
    await state.clear()
    await message.answer(
        "Главное меню администратора:",
        reply_markup=admin_main_menu()
    )
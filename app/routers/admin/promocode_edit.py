"""Модуль для редактирования промокодов"""

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from app.database.repositories import PromoCodeRepository
from app.database.unit_of_work import UnitOfWork
from app.database.models import DiscountType
from app.database.session import async_session

from app.admin_panel.states_adm import EditPromocode
from app.admin_panel.keyboards_adm import (
    promocodes_menu, excursions_submenu,
    promo_type_selection_menu, promo_duration_selection_menu,
    promo_creation_confirmation_menu, promo_edit_field_menu, cancel_button
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger
from app.utils.validation import validate_promocode


logger = get_logger(__name__)


router = Router(name="admin_promocode_edit")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


@router.callback_query(F.data.startswith("edit_promo:"))
async def start_edit_promocode(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования промокода"""
    promo_id = int(callback.data.split(":")[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование промокода ID={promo_id}")
    await callback.answer()

    try:
        # Получаем данные промокода
        async with async_session() as session:
            promo_repo = PromoCodeRepository(session)
            promocode = await promo_repo.get_by_id(promo_id)

            if not promocode:
                await callback.message.answer(
                    "Промокод не найден.",
                    reply_markup=promocodes_menu()
                )
                return

            # Важно: сохраняем тип как строку, а не как enum из-за Redis
            await state.update_data(
                promo_id=promocode.id,
                current_code=promocode.code,
                current_discount_type="percent" if promocode.discount_type == DiscountType.percent else "fixed",
                current_discount_value=promocode.discount_value,
                current_usage_limit=promocode.usage_limit,
                current_valid_from=promocode.valid_from,
                current_valid_until=promocode.valid_until
            )

            await state.set_state(EditPromocode.waiting_for_field_selection)

            # Показываем меню выбора поля для редактирования
            await show_edit_field_menu(callback.message, promocode)

    except Exception as e:
        logger.error(f"Ошибка начала редактирования промокода: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при начале редактирования",
            reply_markup=excursions_submenu()
        )
        await state.clear()

async def show_edit_field_menu(message: Message, promocode):
    """Показать меню выбора поля для редактирования"""

    # Формируем информацию о текущих значениях
    if promocode.discount_type == DiscountType.percent:
        discount_text = f"{promocode.discount_value}%"
        discount_type_text = "Проценты"
    else:
        discount_text = f"{promocode.discount_value} руб."
        discount_type_text = "Фиксированная сумма"

    usage_text = f"{promocode.used_count}"
    if promocode.usage_limit:
        usage_text += f" из {promocode.usage_limit}"
    else:
        usage_text += " (неограниченно)"

    info = (
        f"Редактирование промокода {promocode.code}\n\n"
        f"Текущие значения:\n"
        f"• Код: {promocode.code}\n"
        f"• Тип скидки: {discount_type_text}\n"
        f"• Значение скидки: {discount_text}\n"
        f"• Использовано: {usage_text}\n"
        f"• Действует: {promocode.valid_from.strftime('%d.%m.%Y %H:%M')} - {promocode.valid_until.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Выберите поле для редактирования:"
    )

    await message.answer(
        info,
        reply_markup=promo_edit_field_menu()
    )
@router.callback_query(F.data.startswith("edit_promo_field:"), EditPromocode.waiting_for_field_selection)
async def select_edit_field(callback: CallbackQuery, state: FSMContext):
    """Выбор поля для редактирования"""
    field = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал поле для редактирования: {field}")
    await callback.answer()

    data = await state.get_data()
    promo_id = data.get('promo_id')

    try:
        # Сохраняем выбранное поле
        await state.update_data(editing_field=field)

        # Перенаправляем на соответствующий обработчик в зависимости от поля
        if field == "code":
            await state.set_state(EditPromocode.waiting_for_new_code)
            await callback.message.answer(
                "Введите новый код промокода:\n"
                "• Только большие латинские буквы и цифры\n"
                "• Длина от 4 до 20 символов\n"
                "• Например: SUMMER2024, WELCOME10, BLACKFRIDAY\n\n"
                "Или введите /cancel для отмены",
                reply_markup=cancel_button()
            )

        elif field == "type":
            await state.set_state(EditPromocode.waiting_for_new_type)
            await callback.message.answer(
                "Выберите новый тип скидки:",
                reply_markup=promo_type_selection_menu()
            )

        elif field == "value":
            await state.set_state(EditPromocode.waiting_for_new_value)

            data = await state.get_data()
            discount_type = data.get('current_discount_type')

            if discount_type == DiscountType.percent:
                await callback.message.answer(
                    "Введите новый размер скидки в процентах (от 1 до 100):\n"
                    "Например: 10 (для 10% скидки)\n\n"
                    "Или введите /cancel для отмены",
                    reply_markup=cancel_button()
                )
            else:
                await callback.message.answer(
                    "Введите новый размер скидки в рублях (от 10 до 10000):\n"
                    "Например: 500 (для скидки 500 рублей)\n\n"
                    "Или нажмите /cancel для отмены",
                    reply_markup=cancel_button()
                )

        elif field == "limit":
            await state.set_state(EditPromocode.waiting_for_new_usage_limit)
            await callback.message.answer(
                "Введите новый лимит использований:\n"
                "• Для неограниченного использования введите 0\n"
                "• Для ограниченного использования введите число (например: 10, 50, 100)\n"
                "• Максимальный лимит: 10000 использований\n\n"
                "Или нажмите /cancel для отмены",
                reply_markup=cancel_button()
            )

        elif field == "duration":
            await state.set_state(EditPromocode.waiting_for_new_duration)

            data = await state.get_data()
            current_valid_until = data.get('current_valid_until')

            days_left = (current_valid_until - datetime.now()).days if current_valid_until > datetime.now() else 0

            await callback.message.answer(
                f"Текущий срок действия: до {current_valid_until.strftime('%d.%m.%Y %H:%M')}\n"
                f"Осталось дней: {max(0, days_left)}\n\n"
                "Выберите новый срок действия:",
                reply_markup=promo_duration_selection_menu(
                    include_cancel=True,
                    cancel_callback="cancel_promo_edit",
                    include_back=True,
                    back_callback="back_to_edit_fields"
                )
            )

    except Exception as e:
        logger.error(f"Ошибка выбора поля для редактирования: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.message(EditPromocode.waiting_for_new_code)
async def handle_new_code(message: Message, state: FSMContext):
    """Обработка нового кода промокода"""
    logger.info(f"Администратор {message.from_user.id} ввел новый код: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await cancel_edit(message, state)
            return

        new_code = message.text.strip()

        # Валидация кода
        try:
            new_code = validate_promocode(new_code)
        except ValueError as e:
            await message.answer(str(e))
            return

        # Проверяем, не занят ли код другим промокодом
        data = await state.get_data()
        promo_id = data.get('promo_id')
        current_code = data.get('current_code')

        if new_code == current_code:
            await message.answer(
                "Новый код совпадает с текущим. Пожалуйста, введите другой код или нажмите /cancel для отмены"
            )
            return

        async with async_session() as session:
            promo_repo = PromoCodeRepository(session)
            existing_promo = await promo_repo.get_by_code(new_code)

            if existing_promo and existing_promo.id != promo_id:
                await message.answer(
                    f"Промокод с кодом '{new_code}' уже существует.\n"
                    "Пожалуйста, введите другой код:"
                )
                return

        # Сохраняем новое значение
        await state.update_data(new_code=new_code.upper())
        await show_edit_summary(message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки нового кода: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data.startswith("promo_type:"), EditPromocode.waiting_for_new_type)
async def handle_new_type(callback: CallbackQuery, state: FSMContext):
    """Обработка нового типа скидки"""
    promo_type = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал новый тип: {promo_type}")
    await callback.answer()

    try:
        # Сохраняем как строку
        new_discount_type = promo_type  # "percent" или "fixed"
        await state.update_data(new_discount_type=new_discount_type)

        # Если тип изменился, нужно будет ввести новое значение
        data = await state.get_data()
        current_type = data.get('current_discount_type')

        if new_discount_type != current_type:
            await state.set_state(EditPromocode.waiting_for_new_value)

            if new_discount_type == "percent":
                await callback.message.answer(
                    "Введите новый размер скидки в процентах (от 1 до 100):",
                    reply_markup=cancel_button()
                )
            else:
                await callback.message.answer(
                    "Введите новый размер скидки в рублях (от 10 до 10000):",
                    reply_markup=cancel_button()
                )
        else:
            # Тип не изменился, переходим к сводке
            await show_edit_summary(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки нового типа: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.message(EditPromocode.waiting_for_new_value)
async def handle_new_value(message: Message, state: FSMContext):
    """Обработка нового значения скидки"""
    logger.info(f"Администратор {message.from_user.id} ввел новое значение: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await cancel_edit(message, state)
            return

        data = await state.get_data()

        # Определяем текущий тип скидки (новый или старый)
        if 'new_discount_type' in data:
            discount_type_str = data['new_discount_type']
        else:
            discount_type_str = data['current_discount_type']

        try:
            new_value = int(message.text.strip())

            if discount_type_str == "percent":
                if new_value < 1 or new_value > 100:
                    await message.answer(
                        "Процент скидки должен быть от 1 до 100.\n"
                        "Пожалуйста, введите корректное значение:"
                    )
                    return
            else:  # fixed
                if new_value < 10 or new_value > 10000:
                    await message.answer(
                        "Фиксированная скидка должна быть от 10 до 10000 рублей.\n"
                        "Пожалуйста, введите корректное значение:"
                    )
                    return

            await state.update_data(new_discount_value=new_value)
            await show_edit_summary(message, state)

        except ValueError:
            await message.answer("Пожалуйста, введите число.")

    except Exception as e:
        logger.error(f"Ошибка обработки нового значения: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.message(EditPromocode.waiting_for_new_usage_limit)
async def handle_new_usage_limit(message: Message, state: FSMContext):
    """Обработка нового лимита использований"""
    logger.info(f"Администратор {message.from_user.id} ввел новый лимит: '{message.text}'")

    try:
        if message.text.lower() == "/cancel":
            await cancel_edit(message, state)
            return

        try:
            new_limit = int(message.text.strip())

            if new_limit < 0 or new_limit > 10000:
                await message.answer(
                    "Лимит использований должен быть от 0 до 10000.\n"
                    "0 - неограниченное использование\n"
                    "Пожалуйста, введите корректное значение:"
                )
                return

            # Если лимит 0, устанавливаем None (неограниченное использование)
            if new_limit == 0:
                new_limit = None

            await state.update_data(new_usage_limit=new_limit)
            await show_edit_summary(message, state)

        except ValueError:
            await message.answer(
                "Пожалуйста, введите число от 0 до 10000."
            )

    except Exception as e:
        logger.error(f"Ошибка обработки нового лимита: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data.startswith("promo_duration:"), EditPromocode.waiting_for_new_duration)
async def handle_new_duration(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора нового срока действия"""
    duration_str = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал новый срок: {duration_str} дней")
    await callback.answer()

    try:
        data = await state.get_data()
        current_valid_from = data.get('current_valid_from')

        if duration_str == "0":
            # Бессрочный (оставляем текущую дату начала, ставим далеко в будущее)
            new_valid_until = current_valid_from.replace(year=current_valid_from.year + 10)
        else:
            days = int(duration_str)
            # Срок от текущей даты начала
            new_valid_until = current_valid_from + timedelta(days=days)

        await state.update_data(new_valid_until=new_valid_until)
        await show_edit_summary(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки нового срока: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data == "promo_custom_duration", EditPromocode.waiting_for_new_duration)
async def handle_custom_duration(callback: CallbackQuery, state: FSMContext):
    """Запрос пользовательского срока действия"""
    logger.info(f"Администратор {callback.from_user.id} выбрал пользовательский срок")
    await callback.answer()

    try:
        await state.set_state(EditPromocode.waiting_for_new_custom_duration)
        await callback.message.answer(
            "Введите новый срок действия в днях (от 1 до 365):\n"
            "Срок будет отсчитываться от текущей даты начала промокода\n\n"
            "Или введите /cancel для отмены",
            reply_markup=cancel_button()
        )

    except Exception as e:
        logger.error(f"Ошибка запроса пользовательского срока: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.message(EditPromocode.waiting_for_new_custom_duration)
async def handle_custom_duration_input(message: Message, state: FSMContext):
    """Обработка ввода пользовательского срока"""
    logger.info(f"Администратор {message.from_user.id} ввел срок: {message.text} дней")

    try:
        if message.text.lower() == "/cancel":
            await cancel_edit(message, state)
            return

        try:
            days = int(message.text.strip())
        except ValueError:
            await message.answer("Пожалуйста, введите число от 1 до 365")
            return

        if days < 1 or days > 365:
            await message.answer("Пожалуйста, введите число от 1 до 365")
            return

        data = await state.get_data()
        current_valid_from = data.get('current_valid_from')
        new_valid_until = current_valid_from + timedelta(days=days)

        await state.update_data(new_valid_until=new_valid_until)
        await show_edit_summary(message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки пользовательского срока: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

async def show_edit_summary(message: Message, state: FSMContext):
    """Показать сводку изменений для подтверждения"""
    data = await state.get_data()

    # Текущие значения
    current_code = data.get('current_code')
    current_discount_type_str = data.get('current_discount_type')  # строка
    current_discount_value = data.get('current_discount_value')
    current_usage_limit = data.get('current_usage_limit')
    current_valid_until = data.get('current_valid_until')

    # Новые значения (если есть)
    new_code = data.get('new_code')
    new_discount_type_str = data.get('new_discount_type')  # строка
    new_discount_value = data.get('new_discount_value')
    new_usage_limit = data.get('new_usage_limit')
    new_valid_until = data.get('new_valid_until')

    summary = "Изменения промокода:\n\n"

    # Код
    if new_code and new_code != current_code:
        summary += f"Код: {current_code} → {new_code}\n"
    else:
        summary += f"Код: {current_code} (без изменений)\n"

    # Тип и значение скидки
    current_discount_text = f"{current_discount_value}%"
    if current_discount_type_str == "fixed":
        current_discount_text = f"{current_discount_value} руб."

    if new_discount_type_str is not None or new_discount_value is not None:
        new_type = new_discount_type_str if new_discount_type_str is not None else current_discount_type_str
        new_val = new_discount_value if new_discount_value is not None else current_discount_value

        new_discount_text = f"{new_val}%"
        if new_type == "fixed":
            new_discount_text = f"{new_val} руб."

        summary += f"Скидка: {current_discount_text} → {new_discount_text}\n"
    else:
        summary += f"Скидка: {current_discount_text} (без изменений)\n"

    # Лимит использований
    current_limit_text = "неограниченно" if current_usage_limit is None else str(current_usage_limit)
    new_limit_text = current_limit_text

    if new_usage_limit is not None:
        new_limit_text = "неограниченно" if new_usage_limit is None else str(new_usage_limit)

    if new_usage_limit is not None and new_usage_limit != current_usage_limit:
        summary += f"Лимит: {current_limit_text} → {new_limit_text}\n"
    else:
        summary += f"Лимит: {current_limit_text} (без изменений)\n"

    # Срок действия
    current_date_text = current_valid_until.strftime('%d.%m.%Y %H:%M')

    if new_valid_until is not None:
        new_date_text = new_valid_until.strftime('%d.%m.%Y %H:%M')
        summary += f"Действует до: {current_date_text} → {new_date_text}\n"
    else:
        summary += f"Действует до: {current_date_text} (без изменений)\n"

    summary += "\nПрименить изменения?"

    await state.set_state(EditPromocode.waiting_for_confirmation)
    await message.answer(summary, reply_markup=promo_creation_confirmation_menu())

@router.callback_query(F.data == "confirm_create_promo", EditPromocode.waiting_for_confirmation)
async def confirm_edit_promocode(callback: CallbackQuery, state: FSMContext):
    """Подтверждение редактирования промокода"""
    admin_id = callback.from_user.id
    logger.info(f"Администратор {admin_id} подтвердил редактирование промокода")
    await callback.answer()

    try:
        data = await state.get_data()
        promo_id = data.get('promo_id')

        # Собираем только измененные поля
        update_data = {}

        if 'new_code' in data and data['new_code'] != data.get('current_code'):
            update_data['code'] = data['new_code']

        if 'new_discount_type' in data:
            # Преобразуем строку в enum для БД
            discount_type_str = data['new_discount_type']
            update_data['discount_type'] = DiscountType.percent if discount_type_str == "percent" else DiscountType.fixed

        if 'new_discount_value' in data:
            update_data['discount_value'] = data['new_discount_value']

        if 'new_usage_limit' in data:
            update_data['usage_limit'] = data['new_usage_limit']

        if 'new_valid_until' in data:
            update_data['valid_until'] = data['new_valid_until']

        if not update_data:
            await callback.message.answer(
                "Нет изменений для сохранения.",
                reply_markup=promocodes_menu()
            )
            await state.clear()
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                promo_repo = PromoCodeRepository(uow.session)

                success = await promo_repo.update_promocode(promo_id, **update_data)

                if success:
                    promocode = await promo_repo.get_by_id(promo_id)

                    # Формируем сообщение об успехе
                    if promocode.discount_type == DiscountType.percent:
                        discount_text = f"{promocode.discount_value}%"
                    else:
                        discount_text = f"{promocode.discount_value} руб."

                    success_message = (
                        f"Промокод успешно обновлен!\n\n"
                        f"Код: {promocode.code}\n"
                        f"Скидка: {discount_text}\n"
                        f"Лимит: {'неограниченно' if promocode.usage_limit is None else promocode.usage_limit}\n"
                        f"Действует до: {promocode.valid_until.strftime('%d.%m.%Y %H:%M')}"
                    )

                    await callback.message.answer(success_message)
                else:
                    await callback.message.answer(
                        "Не удалось обновить промокод.",
                        reply_markup=promocodes_menu()
                    )

        await state.clear()
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=promocodes_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка редактирования промокода администратором {admin_id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при редактировании промокода.",
            reply_markup=excursions_submenu()
        )
        await state.clear()

@router.callback_query(F.data == "back_to_edit_fields")
async def back_to_edit_fields(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору поля для редактирования"""
    logger.info(f"Администратор {callback.from_user.id} вернулся к выбору поля")
    await callback.answer()

    try:
        data = await state.get_data()
        promo_id = data.get('promo_id')

        async with async_session() as session:
            promo_repo = PromoCodeRepository(session)
            promocode = await promo_repo.get_by_id(promo_id)

            if promocode:
                await state.set_state(EditPromocode.waiting_for_field_selection)
                await show_edit_field_menu(callback.message, promocode)
            else:
                await callback.message.answer(
                    "Промокод не найден.",
                    reply_markup=promocodes_menu()
                )
                await state.clear()

    except Exception as e:
        logger.error(f"Ошибка возврата к полям: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data == "back_to_promo_summary")
async def back_to_promo_summary(callback: CallbackQuery, state: FSMContext):
    """Возврат к сводке редактирования"""
    logger.info(f"Администратор {callback.from_user.id} вернулся к сводке")
    await callback.answer()

    try:
        await state.set_state(EditPromocode.waiting_for_confirmation)
        await show_edit_summary(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка возврата к сводке: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data == "edit_promo_data")
async def edit_promo_data(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных промокода перед созданием"""
    logger.info(f"Администратор {callback.from_user.id} хочет редактировать данные промокода")
    await callback.answer()

    try:
        await callback.message.answer(
            "Выберите поле для редактирования:",
            reply_markup=promo_edit_field_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка начала редактирования: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при начале редактирования", reply_markup=excursions_submenu())
        await state.clear()

@router.callback_query(F.data == "cancel_promo_edit")
async def cancel_edit_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования через callback"""
    logger.info(f"Администратор {callback.from_user.id} отменил редактирование")
    await callback.answer()

    await cancel_edit(callback.message, state)

async def cancel_edit(message: Message, state: FSMContext):
    """Общая функция отмены редактирования"""
    await state.clear()
    await message.answer(
        "Редактирование отменено.",
        reply_markup=promocodes_menu()
    )
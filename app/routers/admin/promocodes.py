from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime

from app.admin_panel.states_adm import CreatePromocode
from app.database.requests import DatabaseManager
from app.database.models import async_session, DiscountType, PromoCode
from app.admin_panel.keyboards_adm import (
    promocodes_menu,
    promo_edit_field_menu, promo_type_selection_menu,
    promo_duration_selection_menu, promo_creation_confirmation_menu
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_admin_logger

router = Router(name="admin_promocodes")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = get_admin_logger()

# ===== ОБЩИЕ КНОПКИ =====

@router.message(F.text == "Промокоды")
async def show_promocodes(message: Message):
    """Управление промокодами"""
    logger.info(f"Администратор {message.from_user.id} открыл управление промокодами")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            # Получаем все активные промокоды
            promocodes = await db_manager.get_all_promocodes()

            if not promocodes:
                await message.answer(
                    "Активные промокоды не найдены.\n\n"
                    "Вы можете:\n"
                    "1. Создать новый промокод\n"
                    "2. Посмотреть архивные промокоды\n"
                    "3. Вернуться в меню",
                    reply_markup=promocodes_menu()
                )
                return

            # Формируем список промокодов
            response = "Список активных промокодов:\n\n"
            for promo in promocodes:
                # Определяем тип скидки
                if promo.discount_type == DiscountType.PERCENTAGE:
                    discount_text = f"{promo.discount_value}%"
                else:
                    discount_text = f"{promo.discount_value} руб."

                # Проверяем статус
                current_time = datetime.now()
                is_expired = promo.valid_until < current_time
                is_limit_reached = promo.used_count >= promo.usage_limit if promo.usage_limit else False

                status = "Активен"
                if is_expired:
                    status = "Истек"
                elif is_limit_reached:
                    status = "Лимит использований"

                # Форматируем даты
                valid_from = promo.valid_from.strftime("%d.%m.%Y")
                valid_until = promo.valid_until.strftime("%d.%m.%Y")

                response += (
                    f"Код: {promo.code}\n"
                    f"Скидка: {discount_text}\n"
                    f"Использовано: {promo.used_count}"
                    f"{f'/{promo.usage_limit}' if promo.usage_limit else ''}\n"
                    f"Действует: {valid_from} - {valid_until}\n"
                    f"Статус: {status}\n"
                )

                if promo.description:
                    response += f"Описание: {promo.description}\n"

                response += "---\n"

            await message.answer(response)

            await message.answer(
                "Выберите действие:",
                reply_markup=promocodes_menu()
            )

    except Exception as e:
        logger.error(f"Ошибка открытия промокодов: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка промокодов")


@router.callback_query(F.data == "list_promocodes")
async def list_promocodes_callback(callback: CallbackQuery):
    """Список промокодов (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} запросил список промокодов")

    try:
        await callback.answer()
        await show_promocodes(callback.message)
    except Exception as e:
        logger.error(f"Ошибка в list_promocodes: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "create_promocode")
async def create_promocode_callback(callback: CallbackQuery):
    """Создание промокода (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} хочет создать промокод")

    try:
        await callback.answer()
        await callback.message.answer("Функция создания промокода в разработке")
        # Здесь можно добавить FSM для создания промокода
    except Exception as e:
        logger.error(f"Ошибка в create_promocode: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")


# ===== СОЗДАНИЕ ПРОМОКОДОВ (FSM) =====

@router.callback_query(F.data == "create_promocode")
async def create_promocode_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания промокода"""
    logger.info(f"Администратор {callback.from_user.id} начал создание промокода")

    try:
        await callback.answer()

        # Очищаем предыдущее состояние
        await state.clear()

        # Запрашиваем код промокода
        await state.set_state(CreatePromocode.waiting_for_code)
        await callback.message.answer(
            "Создание нового промокода\n\n"
            "Введите код промокода:\n"
            "• Только латинские буквы и цифры\n"
            "• Длина от 4 до 20 символов\n"
            "• Например: SUMMER2024, WELCOME10, BLACKFRIDAY\n\n"
            "Или введите /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка начала создания промокода: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при начале создания промокода")


@router.message(CreatePromocode.waiting_for_code)
async def handle_promocode_code(message: Message, state: FSMContext):
    """Обработка ввода кода промокода"""
    logger.info(f"Администратор {message.from_user.id} ввел код промокода: '{message.text}'")

    try:
        # Проверяем отмену
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Создание промокода отменено.",
                reply_markup=promocodes_menu()
            )
            return

        code = message.text.strip()

        # Валидация кода
        if not code:
            await message.answer("Код промокода не может быть пустым. Пожалуйста, введите код:")
            return

        if len(code) < 4 or len(code) > 20:
            await message.answer(
                "Код промокода должен быть от 4 до 20 символов.\n"
                "Пожалуйста, введите корректный код:"
            )
            return

        # Проверяем, что код содержит только разрешенные символы
        import re
        if not re.match(r'^[A-Za-z0-9_-]+$', code):
            await message.answer(
                "Код промокода может содержать только:\n"
                "• Латинские буквы (A-Z, a-z)\n"
                "• Цифры (0-9)\n"
                "• Дефис (-) и нижнее подчеркивание (_)\n"
                "Пожалуйста, введите корректный код:"
            )
            return

        # Проверяем, не существует ли уже такой промокод
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            existing_promo = await db_manager.get_promo_code(code)

            if existing_promo:
                await message.answer(
                    f"Промокод с кодом '{code}' уже существует.\n"
                    f"Он был создан {existing_promo.valid_from.strftime('%d.%m.%Y')} "
                    f"и действителен до {existing_promo.valid_until.strftime('%d.%m.%Y')}.\n\n"
                    "Пожалуйста, введите другой код:"
                )
                return

        # Сохраняем код и переходим к выбору типа
        await state.update_data(code=code.upper())
        await state.set_state(CreatePromocode.waiting_for_type)

        # Показываем клавиатуру для выбора типа скидки
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        builder.button(text="Процентная скидка", callback_data="promo_type:percentage")
        builder.button(text="Фиксированная сумма", callback_data="promo_type:fixed")
        builder.button(text="Отмена", callback_data="cancel_promo_creation")
        builder.adjust(1)

        await message.answer(
            f"Код промокода: {code.upper()}\n\n"
            "Выберите тип скидки:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка обработки кода промокода: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке кода промокода")


@router.callback_query(F.data.startswith("promo_type:"))
async def handle_promocode_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа промокода"""
    promo_type = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал тип промокода: {promo_type}")

    try:
        await callback.answer()

        # Сохраняем тип промокода
        discount_type = DiscountType.PERCENTAGE if promo_type == "percentage" else DiscountType.FIXED_AMOUNT
        await state.update_data(discount_type=discount_type)
        await state.set_state(CreatePromocode.waiting_for_value)

        # Запрашиваем значение скидки
        if promo_type == "percentage":
            await callback.message.answer(
                "Вы выбрали процентную скидку.\n\n"
                "Введите размер скидки в процентах (от 1 до 100):\n"
                "Например: 10 (для 10% скидки)\n\n"
                "Или введите /cancel для отмены"
            )
        else:
            await callback.message.answer(
                "Вы выбрали фиксированную сумму.\n\n"
                "Введите размер скидки в рублях (от 10 до 10000):\n"
                "Например: 500 (для скидки 500 рублей)\n\n"
                "Или введите /cancel для отмены"
            )

    except Exception as e:
        logger.error(f"Ошибка обработки типа промокода: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при выборе типа промокода")


@router.message(CreatePromocode.waiting_for_value)
async def handle_promocode_value(message: Message, state: FSMContext):
    """Обработка ввода значения скидки"""
    logger.info(f"Администратор {message.from_user.id} ввел значение скидки: '{message.text}'")

    try:
        # Проверяем отмену
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Создание промокода отменено.",
                reply_markup=promocodes_menu()
            )
            return

        # Получаем сохраненные данные
        data = await state.get_data()
        discount_type = data.get('discount_type')

        try:
            value = int(message.text.strip())

            if discount_type == DiscountType.PERCENTAGE:
                if value < 1 or value > 100:
                    await message.answer(
                        "Процентная скидка должна быть от 1 до 100%.\n"
                        "Пожалуйста, введите корректное значение:"
                    )
                    return
            else:  # FIXED_AMOUNT
                if value < 10 or value > 10000:
                    await message.answer(
                        "Фиксированная скидка должна быть от 10 до 10000 рублей.\n"
                        "Пожалуйста, введите корректное значение:"
                    )
                    return

            # Сохраняем значение и переходим к описанию
            await state.update_data(discount_value=value)
            await state.set_state(CreatePromocode.waiting_for_description)

            await message.answer(
                f"Значение скидки: {value} {'%' if discount_type == DiscountType.PERCENTAGE else 'руб.'}\n\n"
                "Введите описание промокода (необязательно):\n"
                "Например: 'Скидка на первую экскурсию', 'Летняя акция'\n"
                "Или просто отправьте 'нет' или 'без описания'\n\n"
                "Или введите /cancel для отмены"
            )

        except ValueError:
            await message.answer(
                "Пожалуйста, введите число.\n"
                "Для процентной скидки: от 1 до 100\n"
                "Для фиксированной суммы: от 10 до 10000"
            )

    except Exception as e:
        logger.error(f"Ошибка обработки значения промокода: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке значения скидки")


@router.message(CreatePromocode.waiting_for_description)
async def handle_promocode_description(message: Message, state: FSMContext):
    """Обработка ввода описания промокода"""
    logger.info(f"Администратор {message.from_user.id} ввел описание промокода: '{message.text}'")

    try:
        # Проверяем отмену
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Создание промокода отменено.",
                reply_markup=promocodes_menu()
            )
            return

        description = message.text.strip()

        # Если пользователь не хочет добавлять описание
        if description.lower() in ["нет", "без описания", "пропустить", "-", ""]:
            description = None
        elif len(description) > 200:
            await message.answer(
                "Описание слишком длинное (максимум 200 символов).\n"
                "Пожалуйста, введите более короткое описание:"
            )
            return

        # Сохраняем описание и переходим к лимиту использований
        await state.update_data(description=description)
        await state.set_state(CreatePromocode.waiting_for_usage_limit)

        await message.answer(
            f"Описание: {description if description else 'без описания'}\n\n"
            "Введите лимит использований промокода:\n"
            "• Для неограниченного использования введите 0\n"
            "• Для ограниченного использования введите число (например: 10, 50, 100)\n"
            "• Максимальный лимит: 10000 использований\n\n"
            "Или введите /cancel для отмены"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки описания промокода: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке описания")


@router.message(CreatePromocode.waiting_for_usage_limit)
async def handle_promocode_usage_limit(message: Message, state: FSMContext):
    """Обработка ввода лимита использований"""
    logger.info(f"Администратор {message.from_user.id} ввел лимит использований: '{message.text}'")

    try:
        # Проверяем отмену
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Создание промокода отменено.",
                reply_markup=promocodes_menu()
            )
            return

        try:
            usage_limit = int(message.text.strip())

            if usage_limit < 0 or usage_limit > 10000:
                await message.answer(
                    "Лимит использований должен быть от 0 до 10000.\n"
                    "0 - неограниченное использование\n"
                    "Пожалуйста, введите корректное значение:"
                )
                return

            # Если лимит 0, устанавливаем None (неограниченное использование)
            if usage_limit == 0:
                usage_limit = None

            # Сохраняем лимит и переходим к сроку действия
            await state.update_data(usage_limit=usage_limit)
            await state.set_state(CreatePromocode.waiting_for_duration)

            # Формируем текст с информацией о лимите
            limit_text = "неограниченно" if usage_limit is None else f"{usage_limit} использований"

            # Используем клавиатуру из keyboards_adm.py
            await message.answer(
                f"Лимит использований: {limit_text}\n\n"
                "Выберите срок действия промокода:",
                reply_markup=promo_duration_selection_menu(
                    include_cancel=True,
                    cancel_callback="cancel_promo_creation",
                    include_back=False
                )
            )

        except ValueError:
            await message.answer(
                "Пожалуйста, введите число от 0 до 10000.\n"
                "0 - неограниченное использование"
            )

    except Exception as e:
        logger.error(f"Ошибка обработки лимита использований: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке лимита использований")


@router.callback_query(F.data.startswith("promo_duration:"))
async def handle_promocode_duration(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора срока действия промокода"""
    duration_str = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал срок действия: {duration_str} дней")

    try:
        await callback.answer()

        if duration_str == "0":
            # Бессрочный промокод
            valid_until = None
            duration_text = "бессрочно"
        else:
            # Ограниченный по времени
            days = int(duration_str)
            from datetime import datetime, timedelta
            valid_until = datetime.now() + timedelta(days=days)
            duration_text = f"{days} дней"

        # Сохраняем срок действия
        await state.update_data(valid_until=valid_until)
        await state.set_state(CreatePromocode.waiting_for_confirmation)

        # Показываем сводку для подтверждения
        await show_promocode_summary(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки срока действия: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при выборе срока действия")


@router.callback_query(F.data == "promo_custom_duration")
async def handle_custom_duration(callback: CallbackQuery, state: FSMContext):
    """Запрос пользовательского срока действия"""
    logger.info(f"Администратор {callback.from_user.id} выбрал пользовательский срок")

    try:
        await callback.answer()

        await callback.message.answer(
            "Введите срок действия промокода в днях (от 1 до 365):\n"
            "Например: 14 (для 2 недель), 60 (для 2 месяцев)\n\n"
            "Или введите /cancel для отмены"
        )
        # Сохраняем состояние для ввода пользовательского срока
        await state.set_state(CreatePromocode.waiting_for_duration)
        await state.update_data(waiting_for_custom_duration=True)

    except Exception as e:
        logger.error(f"Ошибка запроса пользовательского срока: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")


@router.callback_query(F.data == "cancel_promo_creation")
async def cancel_promo_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания промокода"""
    logger.info(f"Администратор {callback.from_user.id} отменил создание промокода")

    try:
        await callback.answer()

        await state.clear()
        await callback.message.answer(
            "Создание промокода отменено.",
            reply_markup=promocodes_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка отмены создания промокода: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")


async def show_promocode_summary(message: Message, state: FSMContext):
    """Показать сводку по промокоду для подтверждения"""
    data = await state.get_data()

    code = data.get('code', 'Не указан')
    discount_type = data.get('discount_type')
    discount_value = data.get('discount_value', 0)
    description = data.get('description')
    usage_limit = data.get('usage_limit')
    valid_until = data.get('valid_until')

    # Формируем текст сводки
    summary = "📋 Сводка по промокоду:\n\n"
    summary += f"Код: <code>{code}</code>\n"

    if discount_type == DiscountType.PERCENTAGE:
        summary += f"Тип скидки: Процентная ({discount_value}%)\n"
    else:
        summary += f"Тип скидки: Фиксированная ({discount_value} руб.)\n"

    summary += f"Описание: {description if description else 'без описания'}\n"
    summary += f"Лимит использований: {'неограниченно' if usage_limit is None else usage_limit}\n"

    if valid_until:
        from datetime import datetime
        summary += f"Срок действия: {valid_until.strftime('%d.%m.%Y %H:%M')}\n"
        # Показываем сколько дней осталось
        days_left = (valid_until - datetime.now()).days
        summary += f"Действителен еще: {days_left} дней\n"
    else:
        summary += "Срок действия: бессрочно\n"

    summary += "\nВсё верно?"

    # Создаем клавиатуру подтверждения
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, создать промокод", callback_data="confirm_create_promo")
    builder.button(text="Редактировать", callback_data="edit_promo_data")
    builder.button(text="Отмена", callback_data="cancel_promo_creation")
    builder.adjust(1)

    await message.answer(summary, reply_markup=builder.as_markup())


@router.callback_query(F.data == "confirm_create_promo")
async def confirm_create_promocode(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания промокода"""
    logger.info(f"Администратор {callback.from_user.id} подтвердил создание промокода")

    try:
        await callback.answer()

        # Получаем все данные
        data = await state.get_data()

        code = data.get('code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        description = data.get('description')
        usage_limit = data.get('usage_limit')
        valid_until = data.get('valid_until')

        # Устанавливаем время начала действия
        from datetime import datetime
        valid_from = datetime.now()

        # Создаем промокод в базе данных
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            # Создаем промокод
            promocode = PromoCode(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                description=description,
                valid_from=valid_from,
                valid_until=valid_until,
                usage_limit=usage_limit,
                used_count=0,
                is_active=True
            )

            session.add(promocode)
            await session.commit()
            await session.refresh(promocode)

            logger.info(f"Промокод создан: ID={promocode.id}, code={promocode.code}")

            # Формируем сообщение об успехе
            success_message = "Промокод успешно создан!\n\n"
            success_message += f"Код: <code>{promocode.code}</code>\n"

            if promocode.discount_type == DiscountType.PERCENTAGE:
                success_message += f"Скидка: {promocode.discount_value}%\n"
            else:
                success_message += f"Скидка: {promocode.discount_value} руб.\n"

            if promocode.description:
                success_message += f"Описание: {promocode.description}\n"

            success_message += f"Лимит использований: {'неограниченно' if promocode.usage_limit is None else promocode.usage_limit}\n"

            if promocode.valid_until:
                success_message += f"Действует до: {promocode.valid_until.strftime('%d.%m.%Y')}\n"
            else:
                success_message += "Срок действия: бессрочно\n"

            success_message += f"\nID промокода: {promocode.id}"

            await callback.message.answer(success_message)

            # Показываем меню промокодов
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=promocodes_menu()
            )

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания промокода: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при создании промокода.\n"
            "Пожалуйста, попробуйте еще раз."
        )
        await state.clear()


@router.callback_query(F.data == "edit_promo_data")
async def edit_promo_data(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных промокода перед созданием"""
    logger.info(f"Администратор {callback.from_user.id} хочет редактировать данные промокода")

    try:
        await callback.answer()

        # Используем клавиатуру из keyboards_adm.py
        await callback.message.answer(
            "Выберите поле для редактирования:",
            reply_markup=promo_edit_field_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка начала редактирования: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при начале редактирования")


@router.callback_query(F.data.startswith("edit_promo_field:"))
async def edit_promo_field(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования"""
    field = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} редактирует поле: {field}")

    try:
        await callback.answer()

        # Конфигурация для каждого поля
        field_configs = {
            "code": {
                "text": "Введите новый код промокода:",
                "state": CreatePromocode.waiting_for_code
            },
            "type": {
                "text": "Выберите новый тип скидки:",
                "state": CreatePromocode.waiting_for_type,
                "use_keyboard": True,
                "keyboard": promo_type_selection_menu
            },
            "value": {
                "text": "Введите новое значение скидки:",
                "state": CreatePromocode.waiting_for_value
            },
            "description": {
                "text": "Введите новое описание:",
                "state": CreatePromocode.waiting_for_description
            },
            "limit": {
                "text": "Введите новый лимит использований:",
                "state": CreatePromocode.waiting_for_usage_limit
            },
            "duration": {
                "text": "Выберите новый срок действия:",
                "state": CreatePromocode.waiting_for_duration,
                "use_keyboard": True,
                "keyboard": lambda: promo_duration_selection_menu(
                    include_cancel=True,
                    cancel_callback="cancel_promo_creation",
                    include_back=True,
                    back_callback="edit_promo_data"
                )
            }
        }

        if field not in field_configs:
            await callback.message.answer("Неизвестное поле для редактирования.")
            return

        config = field_configs[field]

        # Устанавливаем состояние
        await state.set_state(config["state"])

        # Если поле использует клавиатуру, показываем ее
        if config.get("use_keyboard"):
            keyboard_func = config["keyboard"]
            await callback.message.answer(
                config["text"],
                reply_markup=keyboard_func() if callable(keyboard_func) else keyboard_func
            )
        else:
            # Для полей без клавиатуры просто запрашиваем ввод
            await callback.message.answer(config["text"])

    except Exception as e:
        logger.error(f"Ошибка редактирования поля {field}: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при выборе поля для редактирования")


@router.callback_query(F.data == "edit_promo_data")
async def edit_promo_data(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных промокода перед созданием"""
    logger.info(f"Администратор {callback.from_user.id} хочет редактировать данные промокода")

    try:
        await callback.answer()

        # Показываем меню выбора поля для редактирования
        await callback.message.answer(
            "Выберите поле для редактирования:",
            reply_markup=promo_edit_field_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка начала редактирования: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при начале редактирования")


@router.callback_query(F.data == "back_to_promo_summary")
async def back_to_promo_summary(callback: CallbackQuery, state: FSMContext):
    """Возврат к сводке промокода"""
    logger.info(f"Администратор {callback.from_user.id} вернулся к сводке промокода")

    try:
        await callback.answer()
        await state.set_state(CreatePromocode.waiting_for_confirmation)
        await show_promocode_summary(callback.message, state)
    except Exception as e:
        logger.error(f"Ошибка возврата к сводке: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при возврате к сводке")


async def show_promocode_summary(message: Message, state: FSMContext):
    """Показать сводку по промокоду для подтверждения"""
    data = await state.get_data()

    code = data.get('code', 'Не указан')
    discount_type = data.get('discount_type')
    discount_value = data.get('discount_value', 0)
    description = data.get('description')
    usage_limit = data.get('usage_limit')
    valid_until = data.get('valid_until')

    # Формируем текст сводки
    summary = "Сводка по промокоду:\n\n"
    summary += f"Код: <code>{code}</code>\n"

    if discount_type == DiscountType.PERCENTAGE:
        summary += f"Тип скидки: Процентная ({discount_value}%)\n"
    else:
        summary += f"Тип скидки: Фиксированная ({discount_value} руб.)\n"

    summary += f"Описание: {description if description else 'без описания'}\n"
    summary += f"Лимит использований: {'неограниченно' if usage_limit is None else usage_limit}\n"

    if valid_until:
        from datetime import datetime
        summary += f"Срок действия: {valid_until.strftime('%d.%m.%Y %H:%M')}\n"
        # Показываем сколько дней осталось
        days_left = (valid_until - datetime.now()).days
        summary += f"Действителен еще: {days_left} дней\n"
    else:
        summary += "Срок действия: бессрочно\n"

    summary += "\nВсё верно?"

    # Используем клавиатуру из keyboards_adm.py
    await message.answer(summary, reply_markup=promo_creation_confirmation_menu())


@router.callback_query(F.data.startswith("promo_duration:"))
async def handle_promocode_duration(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора срока действия промокода"""
    duration_str = callback.data.split(":")[1]
    logger.info(f"Администратор {callback.from_user.id} выбрал срок действия: {duration_str} дней")

    try:
        await callback.answer()

        if duration_str == "0":
            # Бессрочный промокод
            valid_until = None
            duration_text = "бессрочно"
        else:
            # Ограниченный по времени
            days = int(duration_str)
            from datetime import datetime, timedelta
            valid_until = datetime.now() + timedelta(days=days)
            duration_text = f"{days} дней"

        # Сохраняем срок действия
        await state.update_data(valid_until=valid_until)
        await state.set_state(CreatePromocode.waiting_for_confirmation)

        # Показываем сводку для подтверждения
        await show_promocode_summary(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки срока действия: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при выборе срока действия")


@router.message(CreatePromocode.waiting_for_duration)
async def handle_custom_duration_input(message: Message, state: FSMContext):
    """Обработка ввода пользовательского срока действия"""
    logger.info(f"Администратор {message.from_user.id} ввел пользовательский срок: '{message.text}'")

    try:
        # Проверяем отмену
        if message.text.lower() == "/cancel":
            await state.clear()
            await message.answer(
                "Создание промокода отменено.",
                reply_markup=promocodes_menu()
            )
            return

        # Проверяем, ждем ли мы пользовательский срок
        data = await state.get_data()
        if not data.get('waiting_for_custom_duration'):
            # Если не ждем пользовательский срок, значит это ответ на стандартное меню
            # Пропускаем обработку
            return

        try:
            days = int(message.text.strip())

            if days < 1 or days > 365:
                await message.answer(
                    "Срок действия должен быть от 1 до 365 дней.\n"
                    "Пожалуйста, введите корректное значение:"
                )
                return

            from datetime import datetime, timedelta
            valid_until = datetime.now() + timedelta(days=days)

            # Сохраняем срок действия и очищаем флаг
            await state.update_data(
                valid_until=valid_until,
                waiting_for_custom_duration=False
            )

            await state.set_state(CreatePromocode.waiting_for_confirmation)
            await show_promocode_summary(message, state)

        except ValueError:
            await message.answer(
                "Пожалуйста, введите число от 1 до 365.\n"
                "Например: 30 (для 30 дней)"
            )

    except Exception as e:
        logger.error(f"Ошибка обработки пользовательского срока: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке срока действия")



# ===== ОБРАБОТЧИКИ ДЛЯ ПРОМОКОДОВ =====

@router.callback_query(F.data == "list_promocodes")
async def list_promocodes_callback(callback: CallbackQuery):
    """Список промокодов (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} запросил список промокодов")

    try:
        await callback.answer()
        await show_promocodes(callback.message)
    except Exception as e:
        logger.error(f"Ошибка в list_promocodes: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "create_promocode")
async def create_promocode_callback(callback: CallbackQuery):
    """Создание промокода (из клавиатуры)"""
    logger.info(f"Администратор {callback.from_user.id} хочет создать промокод")

    try:
        await callback.answer()
        await callback.message.answer(
            "Функция создания промокода в разработке.\n"
            "Для создания промокода используйте команду /create_promo"
        )
    except Exception as e:
        logger.error(f"Ошибка в create_promocode: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "archive_promocodes")
async def archive_promocodes_callback(callback: CallbackQuery):
    """Архивные промокоды"""
    logger.info(f"Администратор {callback.from_user.id} запросил архивные промокоды")

    try:
        await callback.answer()

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            # Получаем неактивные промокоды
            promocodes = await db_manager.get_all_promocodes(include_inactive=True)

            # Фильтруем истекшие промокоды
            expired_promocodes = [p for p in promocodes if p.valid_until < datetime.now()]

            if not expired_promocodes:
                await callback.message.answer("Архивных (истекших) промокодов нет.")
                return

            response = "Архивные (истекшие) промокоды:\n\n"

            for promo in expired_promocodes[:10]:  # Показываем первые 10
                if promo.discount_type == DiscountType.PERCENTAGE:
                    discount_text = f"{promo.discount_value}%"
                else:
                    discount_text = f"{promo.discount_value} руб."

                valid_until = promo.valid_until.strftime("%d.%m.%Y")

                response += (
                    f"Код: {promo.code}\n"
                    f"Скидка: {discount_text}\n"
                    f"Использовано: {promo.used_count}"
                    f"{f'/{promo.usage_limit}' if promo.usage_limit else ''}\n"
                    f"Истек: {valid_until}\n"
                )

                if promo.description:
                    response += f"Описание: {promo.description}\n"

                response += "---\n"

            if len(expired_promocodes) > 10:
                response += f"\n... и еще {len(expired_promocodes) - 10} промокодов"

            await callback.message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка показа архивных промокодов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data == "promocodes_stats")
async def promocodes_stats_callback(callback: CallbackQuery):
    """Статистика промокодов"""
    logger.info(f"Администратор {callback.from_user.id} запросил статистику промокодов")

    try:
        await callback.answer()

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            promocodes = await db_manager.get_all_promocodes(include_inactive=True)

            if not promocodes:
                await callback.message.answer("Нет данных о промокодах.")
                return

            total_promocodes = len(promocodes)
            active_promocodes = len([p for p in promocodes if p.valid_until >= datetime.now()])
            expired_promocodes = total_promocodes - active_promocodes

            total_uses = sum(p.used_count for p in promocodes)

            response = (
                "Статистика промокодов:\n\n"
                f"Всего промокодов: {total_promocodes}\n"
                f"Активных: {active_promocodes}\n"
                f"Истекших: {expired_promocodes}\n"
                f"Общее количество использований: {total_uses}\n\n"
            )

            # Самый популярный промокод
            if promocodes:
                most_used = max(promocodes, key=lambda p: p.used_count)
                response += f"Самый популярный промокод: {most_used.code} ({most_used.used_count} использований)\n"

            await callback.message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка показа статистики промокодов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

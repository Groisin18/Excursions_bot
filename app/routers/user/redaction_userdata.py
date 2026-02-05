from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.user_panel.states import Red_user, Red_child
from app.utils.validation import (validate_email, validate_phone, validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from datetime import datetime

import app.user_panel.keyboards as kb
from app.database.requests import DatabaseManager
from app.database.models import async_session
from app.utils.logging_config import get_logger

router = Router(name="redaction")

logger = get_logger(__name__)


# ===== РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ =====


@router.callback_query(F.data == 'redact_users_data')
async def redact_users_data(callback: CallbackQuery, state: FSMContext):
    """Показать данные пользователя для редактирования"""
    logger.info(f"Пользователь {callback.from_user.id} открыл редактирование своих данных")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(callback.from_user.id)

            if not user:
                logger.warning(f"Пользователь {callback.from_user.id} не найден при редактировании")
                await callback.message.answer("Пользователь не найден")
                return

            logger.debug(f"Данные пользователя {callback.from_user.id} показаны для редактирования")
            await callback.answer('')
            await callback.message.answer(
                "Ваши данные на текущий момент:\n"
                f"Фамилия, имя: {user.full_name}\n"
                f"Дата рождения: {user.date_of_birth}\n"
                f"Вес: {user.weight} кг\n"
                f"Адрес: {user.address}\n"
                f"Телефон: {user.phone_number}\n"
                f"Email: {user.email}\n\n"
                "Выберите пункт, который хотите поменять",
                reply_markup=await kb.redaction_builder()
            )

    except Exception as e:
        logger.error(f"Ошибка показа данных для редактирования: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке ваших данных")

@router.callback_query(F.data == 'redact_name')
async def redact_name_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования имени"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование имени")

    try:
        await callback.answer('Редактируем имя')
        await state.set_state(Red_user.name)
        await callback.message.answer('Введите новое имя')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования имени")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования имени: {e}", exc_info=True)

@router.message(Red_user.name)
async def redact_name_two(message: Message, state: FSMContext):
    """Завершение редактирования имени"""
    logger.info(f"Пользователь {message.from_user.id} ввел новое имя: '{message.text}'")

    try:
        validated_name = validate_name(message.text)

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении имени")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

            fullname = user.full_name
            new_full_name = fullname.split()[0] + ' ' + validated_name

            logger.debug(f"Обновление имени пользователя {message.from_user.id}: {fullname} -> {new_full_name}")

            success = await db_manager.update_user_data(
                id=user.id,
                full_name=new_full_name
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Имя пользователя {message.from_user.id} обновлено на: {updated_user.full_name}")

                await message.answer(
                    "Имя обновено!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить имя пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидное имя от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании имени: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_surname')
async def redact_surname_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования фамилии"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование фамилии")

    try:
        await callback.answer('Редактируем фамилию')
        await state.set_state(Red_user.surname)
        await callback.message.answer('Введите новую фамилию')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования фамилии")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования фамилии: {e}", exc_info=True)

@router.message(Red_user.surname)
async def redact_surname_two(message: Message, state: FSMContext):
    """Завершение редактирования фамилии"""
    logger.info(f"Пользователь {message.from_user.id} ввел новую фамилию: '{message.text}'")

    try:
        validated_surname = validate_surname(message.text)

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении фамилии")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

            fullname = user.full_name
            if len(fullname.split()) >= 2:
                new_full_name = validated_surname + ' ' + fullname.split()[1]
            else:
                new_full_name = validated_surname

            logger.debug(f"Обновление фамилии пользователя {message.from_user.id}: {fullname} -> {new_full_name}")

            success = await db_manager.update_user_data(
                id=user.id,
                full_name=new_full_name
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Фамилия пользователя {message.from_user.id} обновлена")

                await message.answer(
                    "Фамилия обновлена!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить фамилию пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидная фамилия от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании фамилии: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_phone')
async def redact_phone_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования телефона"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование телефона")

    try:
        await callback.answer('Редактируем телефон')
        await state.set_state(Red_user.phone)
        await callback.message.answer('Введите новый номер телефона')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования телефона")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования телефона: {e}", exc_info=True)

@router.message(Red_user.phone)
async def redact_phone_two(message: Message, state: FSMContext):
    """Завершение редактирования телефона"""
    logger.info(f"Пользователь {message.from_user.id} ввел новый телефон: '{message.text}'")

    try:
        validated_phone = validate_phone(message.text)
        logger.debug(f"Телефон валидирован: {validated_phone[:3]}...{validated_phone[-3:]}")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)
            success = await db_manager.update_user_data(
                id=user.id,
                phone_number=validated_phone
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Телефон пользователя {message.from_user.id} обновлен")

                await message.answer(
                    "Телефон обновлен!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить телефон пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидный телефон от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании телефона: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_birth_date')
async def redact_birth_date_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования даты рождения"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование даты рождения")

    try:
        await callback.answer('Редактируем дату рождения')
        await state.set_state(Red_user.date_of_birth)
        await callback.message.answer(
            'Введите новую дату рождения в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ '
            '(например, день Победы - 09.05.1945 или 09.05.45)'
        )
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования даты рождения")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования даты рождения: {e}", exc_info=True)

@router.message(Red_user.date_of_birth)
async def redact_birth_date_two(message: Message, state: FSMContext):
    """Завершение редактирования даты рождения"""
    logger.info(f"Пользователь {message.from_user.id} ввел новую дату рождения: '{message.text}'")

    try:
        async with async_session() as session:
            validated_date_str = validate_birthdate(message.text)
            birth_date_for_save = datetime.strptime(validated_date_str, "%d.%m.%Y").date()

            logger.debug(f"Дата рождения валидирована: {validated_date_str} -> {birth_date_for_save}")

            db_manager = DatabaseManager(session)

            user = await db_manager.get_user_by_telegram_id(message.from_user.id)
            success = await db_manager.update_user_data(
                id=user.id,
                date_of_birth=birth_date_for_save
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Дата рождения пользователя {message.from_user.id} обновлена")

                response_text = (
                    "Дата рождения обновлена!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}"
                )
                keyboard = kb.inline_end_reg
                await message.answer(response_text, reply_markup=keyboard)

            else:
                logger.warning(f"Не удалось обновить дату рождения пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления", reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании даты рождения: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_weight')
async def redact_weight_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования веса"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование веса")

    try:
        await callback.answer('Редактируем вес')
        await state.set_state(Red_user.weight)
        await callback.message.answer('Введите новый вес')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования веса")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования веса: {e}", exc_info=True)

@router.message(Red_user.weight)
async def redact_weight_two(message: Message, state: FSMContext):
    """Завершение редактирования веса"""
    logger.info(f"Пользователь {message.from_user.id} ввел новый вес: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        logger.debug(f"Вес валидирован: {validated_weight} кг")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)
            success = await db_manager.update_user_data(
                id=user.id,
                weight=validated_weight
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Вес пользователя {message.from_user.id} обновлен на {validated_weight} кг")

                await message.answer(
                    "Вес обновлен!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить вес пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидный вес от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании веса: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_address')
async def redact_address_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования адреса"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование адреса")

    try:
        await callback.answer('Редактируем адрес')
        await state.set_state(Red_user.address)
        await callback.message.answer('Введите новый адрес')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования адреса")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования адреса: {e}", exc_info=True)

@router.message(Red_user.address)
async def redact_address_two(message: Message, state: FSMContext):
    """Завершение редактирования адреса"""
    logger.info(f"Пользователь {message.from_user.id} ввел новый адрес: '{message.text}'")

    try:
        validated_address = validate_address(message.text)
        logger.debug(f"Адрес валидирован (длина: {len(validated_address)} символов)")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)
            success = await db_manager.update_user_data(
                id=user.id,
                address=validated_address
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Адрес пользователя {message.from_user.id} обновлен")

                await message.answer(
                    "Адрес обновлен!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить адрес пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидный адрес от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании адреса: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_email')
async def redact_email_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования email"""
    logger.info(f"Пользователь {callback.from_user.id} начал редактирование email")

    try:
        await callback.answer('Редактируем email')
        await state.set_state(Red_user.email)
        await callback.message.answer('Введите новый адрес email')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние редактирования email")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования email: {e}", exc_info=True)

@router.message(Red_user.email)
async def redact_email_two(message: Message, state: FSMContext):
    """Завершение редактирования email"""
    logger.info(f"Пользователь {message.from_user.id} ввел новый email: '{message.text}'")

    try:
        validated_email = validate_email(message.text)
        logger.debug(f"Email валидирован: {validated_email}")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(message.from_user.id)
            success = await db_manager.update_user_data(
                id=user.id,
                email=validated_email
            )

            if success:
                updated_user = await db_manager.get_user_by_telegram_id(message.from_user.id)
                logger.info(f"Email пользователя {message.from_user.id} обновлен")

                await message.answer(
                    "Email обновлен!\n\n"
                    "Ваши данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {updated_user.date_of_birth}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=kb.inline_end_reg
                )
            else:
                logger.warning(f"Не удалось обновить email пользователя {message.from_user.id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=kb.inline_end_reg)

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидный email от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании email: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()


# ===== РЕДАКТИРОВАНИЕ РЕБЕНКА =====


@router.callback_query(F.data.startswith('edit_child:'))
async def redact_child_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования конкретного ребенка"""
    user_telegram_id = callback.from_user.id
    child_id = int(callback.data.split(':')[1])

    try:
        async with async_session() as session:
            db = DatabaseManager(session)

            # Проверяем права доступа
            user = await db.get_user_by_telegram_id(user_telegram_id)
            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return

            child = await db.get_user_by_id(child_id)
            if not child or child.linked_to_parent_id != user.id:
                await callback.answer("Доступ запрещен", show_alert=True)
                return

            # Сохраняем ID ребенка в состоянии
            await state.update_data(
                child_id=child_id,
                child_name=child.full_name
            )

            logger.info(f"Пользователь {user_telegram_id} начал редактирование ребенка {child_id}")

            # Разделяем full_name на имя и фамилию для отображения
            name_parts = child.full_name.split()
            child_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]
            child_surname = name_parts[0] if len(name_parts) > 1 else ""

            await callback.answer('')
            await callback.message.answer(
                "Данные ребенка на текущий момент:\n"
                f"Имя: {child_name}\n"
                f"Фамилия: {child_surname}\n"
                f"Дата рождения: {child.date_of_birth}\n"
                f"Вес: {child.weight} кг\n"
                f"Адрес: {child.address}\n\n"
                "Выберите пункт, который хотите поменять",
                reply_markup=await kb.redaction_child_builder()
            )

    except Exception as e:
        logger.error(f"Ошибка начала редактирования ребенка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data == 'redact_child_name')
async def redact_child_name_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования имени ребенка"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал редактирование имени ребенка")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await callback.answer("Ошибка: ребенок не выбран", show_alert=True)
            return

        await callback.answer('Редактируем имя ребенка')
        await state.set_state(Red_child.name)
        await callback.message.answer('Введите новое имя ребенка')
        logger.debug(f"Пользователь {user_telegram_id} перешел в состояние редактирования имени ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования имени ребенка: {e}", exc_info=True)

@router.message(Red_child.name)
async def redact_child_name_two(message: Message, state: FSMContext):
    """Завершение редактирования имени ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} ввел новое имя ребенка: '{message.text}'")

    try:
        validated_name = validate_name(message.text)
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await message.answer("Ошибка: ребенок не выбран")
            await state.clear()
            return

        async with async_session() as session:
            db = DatabaseManager(session)
            child = await db.get_user_by_id(child_id)

            if not child:
                logger.warning(f"Ребенок {child_id} не найден при обновлении имени")
                await message.answer("Ребенок не найден")
                await state.clear()
                return

            name_parts = child.full_name.split()
            current_surname = name_parts[0] if len(name_parts) > 1 else ""
            if current_surname:
                new_full_name = f"{current_surname} {validated_name}"
            else:
                new_full_name = validated_name

            logger.debug(f"Обновление имени ребенка {child_id}: {child.full_name} -> {new_full_name}")

            success = await db.update_user_data(
                id=child_id,
                full_name=new_full_name
            )

            if success:
                updated_child = await db.get_user_by_id(child_id)
                logger.info(f"Имя ребенка {child_id} обновлено на: {updated_child.full_name}")

                await message.answer(
                    "Имя ребенка обновлено!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth}\n"
                    f"Вес: {updated_child.weight} кг\n"
                    f"Адрес: {updated_child.address}",
                    reply_markup=await kb.redaction_child_builder()
                )
            else:
                logger.warning(f"Не удалось обновить имя ребенка {child_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=await kb.redaction_child_builder())

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {user_telegram_id}")

    except ValueError as e:
        logger.warning(f"Невалидное имя ребенка от пользователя {user_telegram_id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании имени ребенка: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_child_surname')
async def redact_child_surname_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования фамилии ребенка"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал редактирование фамилии ребенка")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await callback.answer("Ошибка: ребенок не выбран", show_alert=True)
            return

        await callback.answer('Редактируем фамилию ребенка')
        await state.set_state(Red_child.surname)
        await callback.message.answer('Введите новую фамилию ребенка')
        logger.debug(f"Пользователь {user_telegram_id} перешел в состояние редактирования фамилии ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования фамилии ребенка: {e}", exc_info=True)

@router.message(Red_child.surname)
async def redact_child_surname_two(message: Message, state: FSMContext):
    """Завершение редактирования фамилии ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} ввел новую фамилию ребенка: '{message.text}'")

    try:
        validated_surname = validate_surname(message.text)
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await message.answer("Ошибка: ребенок не выбран")
            await state.clear()
            return

        async with async_session() as session:
            db = DatabaseManager(session)
            child = await db.get_user_by_id(child_id)

            if not child:
                logger.warning(f"Ребенок {child_id} не найден при обновлении фамилии")
                await message.answer("Ребенок не найден")
                await state.clear()
                return
            name_parts = child.full_name.split()
            current_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]
            new_full_name = f"{validated_surname} {current_name}"

            logger.debug(f"Обновление фамилии ребенка {child_id}: {child.full_name} -> {new_full_name}")

            success = await db.update_user_data(
                id=child_id,
                full_name=new_full_name
            )

            if success:
                updated_child = await db.get_user_by_id(child_id)
                logger.info(f"Фамилия ребенка {child_id} обновлена")

                await message.answer(
                    "Фамилия ребенка обновлена!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth}\n"
                    f"Вес: {updated_child.weight} кг\n"
                    f"Адрес: {updated_child.address}",
                    reply_markup=await kb.redaction_child_builder()
                )
            else:
                logger.warning(f"Не удалось обновить фамилию ребенка {child_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=await kb.redaction_child_builder())

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {user_telegram_id}")

    except ValueError as e:
        logger.warning(f"Невалидная фамилия ребенка от пользователя {user_telegram_id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании фамилии ребенка: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_child_birth_date')
async def redact_child_birth_date_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования даты рождения ребенка"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал редактирование даты рождения ребенка")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await callback.answer("Ошибка: ребенок не выбран", show_alert=True)
            return

        await callback.answer('Редактируем дату рождения ребенка')
        await state.set_state(Red_child.date_of_birth)
        await callback.message.answer(
            'Введите новую дату рождения ребенка в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ '
            '(например, 09.05.2015 или 09.05.15)'
        )
        logger.debug(f"Пользователь {user_telegram_id} перешел в состояние редактирования даты рождения ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования даты рождения ребенка: {e}", exc_info=True)

@router.message(Red_child.date_of_birth)
async def redact_child_birth_date_two(message: Message, state: FSMContext):
    """Завершение редактирования даты рождения ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} ввел новую дату рождения ребенка: '{message.text}'")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await message.answer("Ошибка: ребенок не выбран")
            await state.clear()
            return

        async with async_session() as session:
            validated_date_str = validate_birthdate(message.text)
            birth_date_for_save = datetime.strptime(validated_date_str, "%d.%m.%Y").date()

            logger.debug(f"Дата рождения ребенка валидирована: {validated_date_str} -> {birth_date_for_save}")

            db = DatabaseManager(session)
            success = await db.update_user_data(
                id=child_id,
                date_of_birth=birth_date_for_save
            )

            if success:
                updated_child = await db.get_user_by_id(child_id)
                logger.info(f"Дата рождения ребенка {child_id} обновлена")

                await message.answer(
                    "Дата рождения ребенка обновлена!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth}\n"
                    f"Вес: {updated_child.weight} кг\n"
                    f"Адрес: {updated_child.address}",
                    reply_markup=await kb.redaction_child_builder()
                )
            else:
                logger.warning(f"Не удалось обновить дату рождения ребенка {child_id}")
                await message.answer("Ошибка обновления",
                                   reply_markup=await kb.redaction_child_builder())

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {user_telegram_id}")

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения ребенка от пользователя {user_telegram_id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании даты рождения ребенка: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_child_weight')
async def redact_child_weight_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования веса ребенка"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал редактирование веса ребенка")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await callback.answer("Ошибка: ребенок не выбран", show_alert=True)
            return

        await callback.answer('Редактируем вес ребенка')
        await state.set_state(Red_child.weight)
        await callback.message.answer('Введите новый вес ребенка')
        logger.debug(f"Пользователь {user_telegram_id} перешел в состояние редактирования веса ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования веса ребенка: {e}", exc_info=True)

@router.message(Red_child.weight)
async def redact_child_weight_two(message: Message, state: FSMContext):
    """Завершение редактирования веса ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} ввел новый вес ребенка: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await message.answer("Ошибка: ребенок не выбран")
            await state.clear()
            return

        async with async_session() as session:
            db = DatabaseManager(session)

            logger.debug(f"Вес ребенка валидирован: {validated_weight} кг")

            success = await db.update_user_data(
                id=child_id,
                weight=validated_weight
            )

            if success:
                updated_child = await db.get_user_by_id(child_id)
                logger.info(f"Вес ребенка {child_id} обновлен на {validated_weight} кг")

                await message.answer(
                    "Вес ребенка обновлен!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth}\n"
                    f"Вес: {updated_child.weight} кг\n"
                    f"Адрес: {updated_child.address}",
                    reply_markup=await kb.redaction_child_builder()
                )
            else:
                logger.warning(f"Не удалось обновить вес ребенка {child_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=await kb.redaction_child_builder())

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {user_telegram_id}")

    except ValueError as e:
        logger.warning(f"Невалидный вес ребенка от пользователя {user_telegram_id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании веса ребенка: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data == 'redact_child_address')
async def redact_child_address_one(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования адреса ребенка"""
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} начал редактирование адреса ребенка")

    try:
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await callback.answer("Ошибка: ребенок не выбран", show_alert=True)
            return

        await callback.answer('Редактируем адрес ребенка')
        await state.set_state(Red_child.address)
        await callback.message.answer('Введите новый адрес ребенка')
        logger.debug(f"Пользователь {user_telegram_id} перешел в состояние редактирования адреса ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала редактирования адреса ребенка: {e}", exc_info=True)

@router.message(Red_child.address)
async def redact_child_address_two(message: Message, state: FSMContext):
    """Завершение редактирования адреса ребенка"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} ввел новый адрес ребенка: '{message.text}'")

    try:
        validated_address = validate_address(message.text)
        data = await state.get_data()
        child_id = data.get('child_id')

        if not child_id:
            await message.answer("Ошибка: ребенок не выбран")
            await state.clear()
            return

        async with async_session() as session:
            db = DatabaseManager(session)

            logger.debug(f"Адрес ребенка валидирован (длина: {len(validated_address)} символов)")

            success = await db.update_user_data(
                id=child_id,
                address=validated_address
            )

            if success:
                updated_child = await db.get_user_by_id(child_id)
                logger.info(f"Адрес ребенка {child_id} обновлен")

                await message.answer(
                    "Адрес ребенка обновлен!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth}\n"
                    f"Вес: {updated_child.weight} кг\n"
                    f"Адрес: {updated_child.address}",
                    reply_markup=await kb.redaction_child_builder()
                )
            else:
                logger.warning(f"Не удалось обновить адрес ребенка {child_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=await kb.redaction_child_builder())

            await state.clear()
            logger.debug(f"Состояние очищено для пользователя {user_telegram_id}")

    except ValueError as e:
        logger.warning(f"Невалидный адрес ребенка от пользователя {user_telegram_id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании адреса ребенка: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()
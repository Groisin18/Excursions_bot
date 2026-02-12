from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as kb
from app.user_panel.states import Red_user

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import UserRepository
from app.database.session import async_session
from app.utils.validation import (validate_email, validate_phone, validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from app.utils.logging_config import get_logger

router = Router(name="user_redaction")

logger = get_logger(__name__)


@router.callback_query(F.data == 'redact_users_data')
async def redact_users_data(callback: CallbackQuery, state: FSMContext):
    """Показать данные пользователя для редактирования"""
    logger.info(f"Пользователь {callback.from_user.id} открыл редактирование своих данных")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(callback.from_user.id)

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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении имени")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

            surname = user.full_name.split()[0]
            new_full_name = surname + ' ' + validated_name

            logger.debug(f"Обновление имени пользователя {message.from_user.id}: {user.full_name} -> {new_full_name}")

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, full_name=new_full_name)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Имя пользователя {message.from_user.id} обновлено на: {updated_user.full_name}")

                    await message.answer(
                        "Имя обновлено!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении фамилии")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

            name = user.full_name.split()[1]  # Имя (вторая часть)
            new_full_name = validated_surname + ' ' + name

            logger.debug(f"Обновление фамилии пользователя {message.from_user.id}: {user.full_name} -> {new_full_name}")

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, full_name=new_full_name)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Фамилия пользователя {message.from_user.id} обновлена")

                    await message.answer(
                        "Фамилия обновлена!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении телефона")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, phone_number=validated_phone)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Телефон пользователя {message.from_user.id} обновлен")

                    await message.answer(
                        "Телефон обновлен!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
        validated_date = validate_birthdate(message.text)
        logger.debug(f"Дата рождения валидирована: {validated_date}")

        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении даты рождения")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, date_of_birth=validated_date)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Дата рождения пользователя {message.from_user.id} обновлена")

                    response_text = (
                        "Дата рождения обновлена!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
                        f"Вес: {updated_user.weight} кг\n"
                        f"Адрес: {updated_user.address}\n"
                        f"Телефон: {updated_user.phone_number}\n"
                        f"Email: {updated_user.email}"
                    )
                    await message.answer(response_text, reply_markup=kb.inline_end_reg)
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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении веса")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, weight=validated_weight)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Вес пользователя {message.from_user.id} обновлен на {validated_weight} кг")

                    await message.answer(
                        "Вес обновлен!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении адреса")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, address=validated_address)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Адрес пользователя {message.from_user.id} обновлен")

                    await message.answer(
                        "Адрес обновлен!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(message.from_user.id)

            if not user:
                logger.warning(f"Пользователь {message.from_user.id} не найден при обновлении email")
                await message.answer("Пользователь не найден")
                await state.clear()
                return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(user.id, email=validated_email)

                if success:
                    updated_user = await user_repo.get_by_id(user.id)
                    logger.info(f"Email пользователя {message.from_user.id} обновлен")

                    await message.answer(
                        "Email обновлен!\n\n"
                        "Ваши данные:\n"
                        f"Фамилия, имя: {updated_user.full_name}\n"
                        f"Дата рождения: {updated_user.date_of_birth.strftime('%d.%m.%Y')}\n"
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
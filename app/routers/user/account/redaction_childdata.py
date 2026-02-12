from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.user_panel.states import Red_child
from app.utils.validation import (validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from datetime import datetime

import app.user_panel.keyboards as kb
from app.database.unit_of_work import UnitOfWork
from app.database.repositories import UserRepository
from app.database.session import async_session
from app.utils.logging_config import get_logger

router = Router(name="child_redaction")

logger = get_logger(__name__)


@router.callback_query(F.data.startswith('edit_child:'))
async def redact_child_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования конкретного ребенка"""
    user_telegram_id = callback.from_user.id
    child_id = int(callback.data.split(':')[1])

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)

            # Проверяем права доступа
            user = await user_repo.get_by_telegram_id(user_telegram_id)
            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return

            child = await user_repo.get_by_id(child_id)
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
                f"Дата рождения: {child.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                child = await user_repo.get_by_id(child_id)

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

                success = await user_repo.update(
                    child_id,
                    full_name=new_full_name
                )

                if success:
                    updated_child = await user_repo.get_by_id(child_id)
                    logger.info(f"Имя ребенка {child_id} обновлено на: {updated_child.full_name}")

                    await message.answer(
                        "Имя ребенка обновлено!\n\n"
                        "Данные ребенка:\n"
                        f"Имя, фамилия: {updated_child.full_name}\n"
                        f"Дата рождения: {updated_child.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            user_repo = UserRepository(session)
            child = await user_repo.get_by_id(child_id)

            if not child:
                logger.warning(f"Ребенок {child_id} не найден при обновлении фамилии")
                await message.answer("Ребенок не найден")
                await state.clear()
                return

            name_parts = child.full_name.split()
            current_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]
            new_full_name = f"{validated_surname} {current_name}"

            logger.debug(f"Обновление фамилии ребенка {child_id}: {child.full_name} -> {new_full_name}")

            async with UnitOfWork(session) as uow:
                user_repo_write = UserRepository(uow.session)
                success = await user_repo_write.update(
                    user_id=child_id,
                    full_name=new_full_name
                )

            if success:
                # Получаем обновленные данные
                updated_child = await user_repo.get_by_id(child_id)
                logger.info(f"Фамилия ребенка {child_id} обновлена")

                await message.answer(
                    "Фамилия ребенка обновлена!\n\n"
                    "Данные ребенка:\n"
                    f"Имя, фамилия: {updated_child.full_name}\n"
                    f"Дата рождения: {updated_child.date_of_birth.strftime('%d.%m.%Y')}\n"
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

        validated_date = validate_birthdate(message.text)
        logger.debug(f"Дата рождения ребенка валидирована: {validated_date}")

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(
                    child_id,
                    date_of_birth=validated_date
                )

                if success:
                    updated_child = await user_repo.get_by_id(child_id)
                    logger.info(f"Дата рождения ребенка {child_id} обновлена")

                    await message.answer(
                        "Дата рождения ребенка обновлена!\n\n"
                        "Данные ребенка:\n"
                        f"Имя, фамилия: {updated_child.full_name}\n"
                        f"Дата рождения: {updated_child.date_of_birth.strftime('%d.%m.%Y')}\n"
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
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)

                logger.debug(f"Вес ребенка валидирован: {validated_weight} кг")

                success = await user_repo.update(
                    user_id=child_id,
                    weight=validated_weight
                )

                if success:
                    updated_child = await user_repo.get_by_id(child_id)
                    logger.info(f"Вес ребенка {child_id} обновлен на {validated_weight} кг")

                    await message.answer(
                        "Вес ребенка обновлен!\n\n"
                        "Данные ребенка:\n"
                        f"Имя, фамилия: {updated_child.full_name}\n"
                        f"Дата рождения: {updated_child.date_of_birth.strftime('%d.%m.%Y')}\n"
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

        logger.debug(f"Адрес ребенка валидирован (длина: {len(validated_address)} символов)")

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_repo = UserRepository(uow.session)
                success = await user_repo.update(child_id, address=validated_address)

                if success:
                    updated_child = await user_repo.get_by_id(child_id)
                    logger.info(f"Адрес ребенка {child_id} обновлен")

                    await message.answer(
                        "Адрес ребенка обновлен!\n\n"
                        "Данные ребенка:\n"
                        f"Имя, фамилия: {updated_child.full_name}\n"
                        f"Дата рождения: {updated_child.date_of_birth.strftime('%d.%m.%Y')}\n"
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
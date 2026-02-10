from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.routers.user.account.models import User

import app.user_panel.keyboards as kb

from app.user_panel.states import Reg_user, Reg_token
from app.database.requests import DatabaseManager, FileManager
from app.database.models import UserRole, RegistrationType, FileType
from app.utils.validation import (validate_email, validate_phone, validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from app.database.session import async_session
from app.utils.logging_config import get_logger
from app.utils.datetime_utils import calculate_age


router = Router(name="adult_registration")

logger = get_logger(__name__)


async def handle_registration(message, final_user):
    """Сохранение пользователя в БД"""
    logger.info(f"Сохранение пользователя {final_user.name} {final_user.surname} в базу данных")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            full_name = final_user.surname + ' ' + final_user.name
            date_of_birth = datetime.strptime(final_user.date_of_birth, "%d.%m.%Y").date()

            logger.debug(f"Создание пользователя: {full_name}, дата рождения: {date_of_birth}")

            user = await db_manager.create_user(
                telegram_id=message.from_user.id,
                full_name=full_name,
                role=UserRole.client,
                phone_number=final_user.phone,
                date_of_birth=date_of_birth,
                address=final_user.address,
                weight=final_user.weight,
                consent_to_pd=True,
                registration_type=RegistrationType.SELF
            )

            if user:
                logger.info(f"Пользователь создан: ID={user.id}, имя='{user.full_name}'")
                return user
            else:
                logger.error("Ошибка создания пользователя: объект не возвращен")
                raise ValueError('Ошибка создания пользователя!!!')

    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}", exc_info=True)
        raise


@router.callback_query(F.data == 'user_hasnt_token')
async def reg_name(callback: CallbackQuery, state: FSMContext):
    """Начало регистрации без токена"""
    logger.info(f"Пользователь {callback.from_user.id} перешел к согласию на обработку персональных данных")
    try:
        await callback.answer('')
        await state.set_state(Reg_token.pd_consent)

        # Получаем file_id из базы данных
        async with async_session() as session:
            file_manager = FileManager(session)
            file_id = await file_manager.get_file_id(FileType.CPD)

            if not file_id:
                logger.error(f"File_id для согласия (CPD) не найден в базе данных для пользователя {callback.from_user.id}")
                await callback.message.answer(
                    'Прекрасно!\n'
                    'Пожалуйста, ознакомьтесь с согласием на обработку персональных данных.\n'
                    'Для продолжения регистрации необходимо принять условия.\n\n'
                    "Извините, произошла ошибка: файл с согласием временно недоступен.\n\n"
                    "Основные положения согласия на обработку данных:\n"
                    "1. Мы обрабатываем ваши данные в целях оказания услуг\n"
                    "2. Данные хранятся в соответствии с законодательством РФ\n"
                    "3. Вы можете отозвать согласие, обратившись к администратору\n\n"
                    "Для получения полной версии документа обратитесь к администратору.",
                    reply_markup=kb.inline_pd_consent
                )
                return

            # Получаем информацию о файле для логирования
            file_record = await file_manager.get_file_record(FileType.CPD)
            file_info = f"{file_record.file_name} ({file_record.file_size} байт)" if file_record else "неизвестно"

            await callback.message.answer_document(
                document=file_id,
                caption=(
                    'Прекрасно!\n'
                    'Пожалуйста, ознакомьтесь с согласием на обработку персональных данных.\n'
                    'Для продолжения регистрации необходимо принять условия.'
                ),
                reply_markup=kb.inline_pd_consent
            )

            logger.info(
                f"PDF согласия на обработку персональных данных успешно отправлен "
                f"пользователю {callback.from_user.id}. Файл: {file_info}"
            )

    except Exception as e:
        logger.error(f"Ошибка согласия на обработку персональных данных: {e}", exc_info=True)

@router.callback_query(F.data == 'pd_consent_false')
async def reg_consest_false(callback: CallbackQuery, state: FSMContext):
    """Согласие не дано, отмена регистрации"""
    await callback.message.answer(
            'К сожалению, регистрация без согласия на обработку персональных'
            'данных невозможна. Для продолжения регистрации необходимо принять условия.',
            reply_markup=kb.inline_pd_consent)

@router.callback_query(F.data == 'pd_consent_true')
async def reg_consest_true(callback: CallbackQuery, state: FSMContext):
    """Согласие дано, переход к вводу email"""
    logger.info(f"Пользователь {callback.from_user.id} дал согласие на обработку персональных данных")
    logger.info(f"Пользователь {callback.from_user.id} начал регистрацию без токена")
    try:
        await callback.answer('')
        await state.set_state(Reg_user.name)
        await callback.message.answer('Хорошо! Введите ваше имя')
        logger.debug(f"Пользователь {callback.from_user.id} перешел к вводу имени")

    except Exception as e:
        logger.error(f"Ошибка начала регистрации без токена: {e}", exc_info=True)

@router.message(Reg_user.name)
async def reg_surname(message: Message, state: FSMContext):
    """Ввод имени"""
    logger.info(f"Пользователь {message.from_user.id} ввел имя: '{message.text}'")

    try:
        validated_name = validate_name(message.text)
        await state.update_data(name=validated_name)
        await state.set_state(Reg_user.surname)

        await message.answer(f'Введите вашу фамилию')
        logger.debug(f"Имя сохранено: {validated_name}")

    except ValueError as e:
        logger.warning(f"Невалидное имя от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.surname)
async def reg_birth_date(message: Message, state: FSMContext):
    """Ввод фамилии"""
    logger.info(f"Пользователь {message.from_user.id} ввел фамилию: '{message.text}'")

    try:
        validated_surname = validate_surname(message.text)
        await state.update_data(surname=validated_surname)
        await state.set_state(Reg_user.date_of_birth)

        await message.answer(
            'Введите вашу дату рождения в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ '
            '(например, день Победы - 09.05.1945 или 09.05.45)'
        )
        logger.debug(f"Фамилия сохранена: {validated_surname}")

    except ValueError as e:
        logger.warning(f"Невалидная фамилия от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.date_of_birth)
async def reg_age(message: Message, state: FSMContext):
    """Ввод даты рождения"""
    logger.info(f"Пользователь {message.from_user.id} ввел дату рождения: '{message.text}'")

    try:
        validated_date = validate_birthdate(message.text)
        age = calculate_age(validated_date)

        await state.update_data(birth_date=validated_date)
        await state.update_data(age=age)
        await state.set_state(Reg_user.weight)

        await message.answer(
            'Введите ваш примерный вес в килограммах '
            '(это необходимо для расчета вместимости лодки в водных прогулках)'
        )
        logger.debug(f"Дата рождения сохранена: {validated_date}, возраст: {age} лет")

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.weight)
async def reg_weight(message: Message, state: FSMContext):
    """Ввод веса"""
    logger.info(f"Пользователь {message.from_user.id} ввел вес: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        await state.update_data(weight=validated_weight)
        await state.set_state(Reg_user.address)

        await message.answer('Введите ваш адрес проживания')
        logger.debug(f"Вес сохранен: {validated_weight} кг")

    except ValueError as e:
        logger.warning(f"Невалидный вес от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.address)
async def reg_address(message: Message, state: FSMContext):
    """Ввод адреса"""
    logger.info(f"Пользователь {message.from_user.id} ввел адрес: '{message.text}'")

    try:
        validated_address = validate_address(message.text)
        await state.update_data(address=validated_address)
        await state.set_state(Reg_user.email)

        await message.answer('Введите ваш адрес электронной почты')
        logger.debug(f"Адрес сохранен: {validated_address}")

    except ValueError as e:
        logger.warning(f"Невалидный адрес от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.email)
async def reg_email(message: Message, state: FSMContext):
    """Ввод email"""
    logger.info(f"Пользователь {message.from_user.id} ввел email: '{message.text}'")

    try:
        validated_email = validate_email(message.text)
        await state.update_data(email=validated_email)
        await state.set_state(Reg_user.phone)

        await message.answer('Введите ваш номер телефона')
        logger.debug(f"Email сохранен: {validated_email}")

    except ValueError as e:
        logger.warning(f"Невалидный email от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_user.phone)
async def reg_phone_and_end(message: Message, state: FSMContext):
    """Ввод телефона и завершение регистрации"""
    logger.info(f"Пользователь {message.from_user.id} ввел телефон: '{message.text}'")

    try:
        validated_phone = validate_phone(message.text)
        await state.update_data(phone=validated_phone)
        await state.set_state(Reg_user.end_reg)

        await message.answer('Регистрация завершается...')
        logger.debug(f"Телефон сохранен: {validated_phone[:3]}...{validated_phone[-3:]}")

    except ValueError as e:
        logger.warning(f"Невалидный телефон от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
        return

    try:
        # Финальная проверка всей модели
        user_data = await state.get_data()
        logger.debug(f"Данные пользователя для создания: {user_data}")

        final_user = User(**user_data)
        logger.info(f"Создание пользователя: {final_user.name} {final_user.surname}")

        # Сохраняем в БД
        user = await handle_registration(message, final_user)

        await message.answer(
            "Регистрация завершена!\n\n"
            "Проверьте данные:\n"
            f"Имя: {final_user.name}\n"
            f"Фамилия: {final_user.surname}\n"
            f"Дата рождения: {final_user.date_of_birth}\n"
            f"Возраст: {final_user.age} лет\n"
            f"Вес: {final_user.weight} кг\n"
            f"Телефон: {final_user.phone}\n"
            f"Email: {final_user.email}",
            reply_markup=await kb.registration_data_menu_builder()
        )

        await state.clear()
        logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка завершения регистрации: {e}", exc_info=True)
        await message.answer(str(e), reply_markup=kb.err_reg)
        await state.clear()
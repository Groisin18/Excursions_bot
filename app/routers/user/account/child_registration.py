'''
Роутер для регистрации пользователем своего ребенка
'''
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.schemas.user import ChildRegistrationData

import app.user_panel.keyboards as kb

from app.user_panel.states import Reg_child
from app.database.repositories import UserRepository, FileRepository
from app.database.managers import UserManager
from app.database.unit_of_work import UnitOfWork
from app.database.models import FileType
from app.utils.validation import (validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from app.database.session import async_session
from app.utils.logging_config import get_logger
from app.utils.datetime_utils import calculate_age


router = Router(name="child_registration")

logger = get_logger(__name__)


@router.callback_query(F.data == 'reg_child')
async def reg_child(callback: CallbackQuery, state: FSMContext):
    """Начало регистрации ребенка"""
    logger.info(f"Пользователь {callback.from_user.id} начал регистрацию ребенка")

    try:
        await callback.answer('')
        await state.set_state(Reg_child.name)
        await callback.message.answer(
            'Вы регистрируете ребенка.\n'
            'Информация о нем будет привязана к вашему аккаунту.\n'
            'По окончанию регистрации вам будет выдан токен вашего ребенка: '
            'специальный код, по которому вы сможете записывать его на экскурсию.\n\n'
            'Для начала регистрации введите имя ребенка',
            reply_markup=kb.inline_in_menu
        )
        logger.debug(f"Пользователь {callback.from_user.id} перешел к регистрации ребенка")

    except Exception as e:
        logger.error(f"Ошибка начала регистрации ребенка: {e}", exc_info=True)

@router.message(Reg_child.name)
async def reg_child_surname(message: Message, state: FSMContext):
    """Ввод имени ребенка"""
    logger.info(f"Пользователь {message.from_user.id} ввел имя ребенка: '{message.text}'")

    try:
        validated_name = validate_name(message.text)
        await state.update_data(name=validated_name)
        await state.update_data(parent_id=message.from_user.id)
        await state.set_state(Reg_child.surname)

        await message.answer(f'Введите фамилию ребенка')
        logger.debug(f"Имя ребенка: {validated_name}")

    except ValueError as e:
        logger.warning(f"Невалидное имя ребенка от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_child.surname)
async def reg_child_consent(message: Message, state: FSMContext):
    """Ввод фамилии ребенка. Согласие на обработку ПД ребенка"""
    logger.info(f"Пользователь {message.from_user.id} ввел фамилию ребенка: '{message.text}'")
    try:
        validated_surname = validate_surname(message.text)
        await state.update_data(surname=validated_surname)
        await state.set_state(Reg_child.pd_consent)
        logger.debug(f"Фамилия ребенка: {validated_surname}")
    except ValueError as e:
        logger.warning(f"Невалидная фамилия ребенка от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
        return

    logger.info(f"Пользователь {message.from_user.id} перешел к согласию на обработку персональных данных ребенка")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            file_repo = FileRepository(session)

            file_id = await file_repo.get_file_id(FileType.CPD_MINOR)
            user = await user_repo.get_by_telegram_id(message.from_user.id)
            data = await state.get_data()
            child_name = data.get('name')
            child_surname = data.get('surname')

            if not file_id:
                logger.error(f"File_id для согласия несовершеннолетних (CPD_MINOR) не найден в базе данных для пользователя {message.from_user.id}")
                await message.answer(
                    'Прекрасно!\n'
                    'Пожалуйста, ознакомьтесь с формой согласия на обработку персональных данных подопечного (ребёнка).\n'
                    'Для продолжения регистрации необходимо принять условия.\n\n'
                    "Извините, произошла ошибка: файл с согласием временно недоступен.\n\n"
                    "Для получения полной версии документа обратитесь к администратору, после чего можете дать согласие.\n\n"
                    f'Я, {user.full_name}, как законный представитель, даю согласие '
                    f'на обработку персональных данных моего ребенка (подопечного) {child_surname} {child_name}, '
                    'в целях регистрации и участия в экскурсиях, в соответствии с предоставленной мне администратором '
                    'формой согласия на обработку персональных данных несовершеннолетних.',
                    reply_markup=kb.inline_pd_consent_child
                )
                return

            # Получаем информацию о файле для логирования
            file_record = await file_repo.get_file_record(FileType.CPD_MINOR)
            file_info = f"{file_record.file_name} ({file_record.file_size} байт)" if file_record else "неизвестно"

            await message.answer_document(
                document=file_id,
                caption=(
                    'Прекрасно!\n'
                    'Пожалуйста, ознакомьтесь с согласием на обработку персональных данных подопечного (ребёнка).\n'
                    'Для продолжения регистрации необходимо принять условия:\n\n'
                    f'Я, {user.full_name}, как законный представитель, даю согласие '
                    f'на обработку персональных данных моего ребенка (подопечного) {child_surname} {child_name}, '
                    'в целях регистрации и участия в экскурсиях, в соответствии с предоставленной '
                    'формой согласия на обработку персональных данных несовершеннолетних.'
                ),
                reply_markup=kb.inline_pd_consent_child
            )

            logger.info(
                f"PDF согласия на обработку персональных данных ребенка успешно отправлен "
                f"пользователю {message.from_user.id}. Файл: {file_info}"
            )

    except Exception as e:
        logger.error(f"Ошибка в моменте согласия на обработку персональных данных ребенка: {e}", exc_info=True)

@router.callback_query(F.data == 'pd_consent_child_false')
async def reg_child_consest_false(callback: CallbackQuery, state: FSMContext):
    """Согласие не дано, отмена регистрации"""
    await callback.message.answer(
            'К сожалению, регистрация без согласия на обработку персональных'
            'данных невозможна. Для продолжения регистрации необходимо принять условия.',
            reply_markup=kb.inline_pd_consent_child)

@router.callback_query(F.data == 'pd_consent_child_true')
async def reg_child_consest_true(callback: CallbackQuery, state: FSMContext):
    """Согласие дано, переход к вводу даты рождения ребенка"""
    data = await state.get_data()
    child_name = data.get('name')
    child_surname = data.get('surname')
    logger.info(f"Пользователь {callback.from_user.id} дал согласие на обработку персональных данных ребенка {child_surname} {child_name}")
    try:
        await callback.answer('')
        await state.set_state(Reg_child.date_of_birth)
        await callback.message.answer(
            'Благодарим!\n'
            'Введите дату рождения ребенка в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ '
            '(например, день Победы - 09.05.1945 или 09.05.45)'
        )
        logger.debug(f"Пользователь {callback.from_user.id} перешел к вводу даты рождения ребенка")

    except Exception as e:
        logger.error(f"Ошибка перехода к вводу email: {e}", exc_info=True)


@router.message(Reg_child.date_of_birth)
async def reg_child_age(message: Message, state: FSMContext):
    """Ввод даты рождения ребенка"""
    logger.info(f"Пользователь {message.from_user.id} ввел дату рождения ребенка: '{message.text}'")

    try:
        validated_date = validate_birthdate(message.text)
        age = calculate_age(validated_date)

        await state.update_data(date_of_birth=validated_date)
        await state.update_data(age=age)
        await state.set_state(Reg_child.weight)

        await message.answer(
            'Введите примерный вес ребенка в килограммах '
            '(это необходимо для расчета вместимости лодки в водных прогулках)'
        )
        logger.debug(f"Дата рождения ребенка сохранена: {validated_date}, возраст: {age} лет")

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_child.weight)
async def reg_child_weight(message: Message, state: FSMContext):
    """Ввод веса ребенка"""
    logger.info(f"Пользователь {message.from_user.id} ввел вес ребенка: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        await state.update_data(weight=validated_weight)
        await state.set_state(Reg_child.address)

        await message.answer('Введите адрес проживания ребенка')
        logger.debug(f"Вес ребенка сохранен: {validated_weight} кг")

    except ValueError as e:
        logger.warning(f"Невалидный вес ребенка от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))

@router.message(Reg_child.address)
async def reg_child_address(message: Message, state: FSMContext):
    """Ввод адреса ребенка и завершение регистрации"""
    logger.info(f"Пользователь {message.from_user.id} ввел адрес ребенка: '{message.text}'")

    try:
        validated_address = validate_address(message.text)
        await state.update_data(address=validated_address)
        await state.set_state(Reg_child.end_reg)

        await message.answer('Регистрация завершается...')
        logger.debug(f"Адрес ребенка сохранен: {validated_address}")

    except ValueError as e:
        logger.warning(f"Невалидный адрес от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
        return

    try:
        # Финальная проверка всей модели
        child_data = await state.get_data()
        logger.debug(f"Данные ребенка для создания: {child_data}")

        # Получаем родителя для parent_id
        async with async_session() as session:
            user_repo = UserRepository(session)
            parent = await user_repo.get_by_telegram_id(message.from_user.id)

            if not parent:
                logger.error(f"Родитель с Telegram ID {message.from_user.id} не найден")
                raise ValueError("Родитель не найден")

            child_data['parent_id'] = parent.id
            final_child = ChildRegistrationData(**child_data)

            logger.info(f"Создание ребенка: {final_child.surname} {final_child.name}")

        # Сохраняем в БД напрямую через менеджер
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_manager = UserManager(uow.session)
                child, child_token = await user_manager.create_child_user(
                    child_data=final_child,
                    parent_telegram_id=message.from_user.id
                )

        await message.answer(
            "Регистрация ребенка завершена!\n\n"
            "Проверьте данные:\n"
            f"Имя: {final_child.name}\n"
            f"Фамилия: {final_child.surname}\n"
            f"Дата рождения: {final_child.date_of_birth}\n"
            f"Возраст: {final_child.age} лет\n"
            f"Адрес: {final_child.address}\n"
            f"Вес: {final_child.weight} кг\n\n"
            "Важно!\n"
            "Запишите токен вашего ребенка:\n\n"
            f"{child_token}\n\n"
            "Чтобы записать ребенка на экскурсию либо снять бронь, будет необходимо ввести этот токен.\n"
            "Вы в любой момент можете посмотреть токены привязанных к вашему аккаунту детей в своем личном кабинете.\n"
            "Для превращения аккаунта ребенка в полноценный самостоятельный аккаунт ему нужно будет ввести данный токен при регистрации.\n"
            "После этого он сможет самостоятельно управлять аккаунтом со своего Телеграма, его данные и история экскурсий при этом сохранятся.\n",
            reply_markup=await kb.registration_data_menu_builder(has_children=True)
        )

        await state.clear()
        logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.error(f"Ошибка валидации при создании ребенка: {e}")
        await message.answer(str(e), reply_markup=kb.err_reg)
        await state.clear()
    except Exception as e:
        logger.error(f"Неизвестная ошибка при создании ребенка: {e}", exc_info=True)
        await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=kb.err_reg)
        await state.clear()
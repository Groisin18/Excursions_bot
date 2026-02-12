'''
Роутер для регистрации с применением имеющегося токена
'''
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.user_panel.keyboards as kb
from app.user_panel.states import Reg_token

from app.database.models import RegistrationType, FileType
from app.database.unit_of_work import UnitOfWork
from app.database.managers import UserManager
from app.database.repositories import UserRepository, FileRepository
from app.database.session import async_session

from app.utils.validation import validate_email, validate_phone
from app.utils.logging_config import get_logger


router = Router(name="token_registration")

logger = get_logger(__name__)



@router.callback_query(F.data == 'user_has_token')
async def reg_has_token(callback: CallbackQuery, state: FSMContext):
    """Начало регистрации по токену"""
    logger.info(f"Пользователь {callback.from_user.id} начал регистрацию по токену")

    try:
        await callback.answer('')
        await state.set_state(Reg_token.token)
        await callback.message.answer('Хорошо! Введите этот токен. Обращайте внимание на большие и маленькие буквы')
        logger.debug(f"Пользователь {callback.from_user.id} перешел в состояние ввода токена")

    except Exception as e:
        logger.error(f"Ошибка начала регистрации по токену: {e}", exc_info=True)

@router.message(Reg_token.token)
async def reg_is_token_right(message: Message, state: FSMContext):
    """Проверка токена"""
    token = message.text.strip()
    logger.info(f"Пользователь {message.from_user.id} ввел токен: {token[:8]}...")

    try:
        async with async_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_token(token)

            if not user:
                logger.warning(f"Неверный токен от пользователя {message.from_user.id}: {token[:8]}...")
                await message.answer(
                    'Данного токена не существует. Введите верный токен.',
                    reply_markup=kb.inline_in_menu
                )
                return

            if user.telegram_id:
                logger.warning(f"Токен уже использован пользователем {message.from_user.id}: {token[:8]}...")
                await message.answer(
                    'Этот токен уже использован и находится в управлении. Обратитесь к администратору.',
                    reply_markup=kb.inline_in_menu
                )
                return

            creator_name = "администратор"
            if user.created_by_id:
                creator = await user_repo.get_by_id(user.created_by_id)
                if creator:
                    creator_name = creator.full_name
                    if user.registration_type == RegistrationType.ADMIN:
                        creator_name = f'администратор {creator_name}'

            await state.update_data(token=token)

            logger.info(f"Токен верный, пользователь найден: ID={user.id}, имя={user.full_name}")

            await message.answer(
                "Это верный токен!\n\n"
                f"Вас зарегистрировал: {creator_name}\n"
                f"При регистрации были указаны фамилия и имя: {user.full_name}\n",
                reply_markup=kb.inline_is_token_right
            )

    except Exception as e:
        logger.error(f"Ошибка проверки токена: {e}", exc_info=True)
        await message.answer(
            'Произошла ошибка. Попробуйте снова или обратитесь к администратору',
            reply_markup=kb.inline_in_menu
        )

@router.callback_query(F.data == 'user_has_wrong_token')
async def reg_token_wrong(callback: CallbackQuery, state: FSMContext):
    """Повторный ввод токена"""
    logger.info(f"Пользователь {callback.from_user.id} вводит токен повторно")

    try:
        await callback.answer('')
        await state.set_state(Reg_token.token)
        await callback.message.answer('Попробуйте ввести верный токен еще раз:')

    except Exception as e:
        logger.error(f"Ошибка повторного ввода токена: {e}", exc_info=True)

@router.callback_query(F.data == 'user_has_right_token')
async def reg_token_right(callback: CallbackQuery, state: FSMContext):
    """Токен верный, переход к вводу email"""
    logger.info(f"Пользователь {callback.from_user.id} подтвердил верный токен")
    try:
        await callback.answer('')
        await state.set_state(Reg_token.pd_consent)

        # Операция чтения - получаем file_id
        async with async_session() as session:
            file_repo = FileRepository(session)
            file_id = await file_repo.get_file_id(FileType.CPD)

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
                    reply_markup=kb.inline_pd_consent_token
                )
                return

            # Получаем полную запись для логирования
            file_record = await file_repo.get_file_record(FileType.CPD)
            file_info = f"{file_record.file_name} ({file_record.file_size} байт)" if file_record else "неизвестно"

            await callback.message.answer_document(
                document=file_id,
                caption=(
                    'Прекрасно!\n'
                    'Пожалуйста, ознакомьтесь с согласием на обработку персональных данных.\n'
                    'Для продолжения регистрации необходимо принять условия.'
                ),
                reply_markup=kb.inline_pd_consent_token
            )

            logger.info(
                f"PDF согласия на обработку персональных данных успешно отправлен "
                f"пользователю {callback.from_user.id}. Файл: {file_info}"
            )

    except Exception as e:
        logger.error(f"Ошибка согласия на обработку персональных данных: {e}", exc_info=True)

@router.callback_query(F.data == 'pd_consent_token_false')
async def reg_token_consest_false(callback: CallbackQuery, state: FSMContext):
    """Согласие не дано, отмена регистрации"""
    await callback.message.answer(
            'К сожалению, регистрация без согласия на обработку персональных'
            'данных невозможна. Для продолжения регистрации необходимо принять условия.',
            reply_markup=kb.inline_pd_consent_token)

@router.callback_query(F.data == 'pd_consent_token_true')
async def reg_token_consest_true(callback: CallbackQuery, state: FSMContext):
    """Согласие дано, переход к вводу email"""
    logger.info(f"Пользователь {callback.from_user.id} дал согласие на обработку персональных данных")
    try:
        await callback.answer('')
        await state.set_state(Reg_token.email)
        await callback.message.answer(
            'Давайте укажем те данные, которых у вас не хватает.\n\n'
            'Пожалуйста, введите вашу электронную почту\n'
        )
        logger.debug(f"Пользователь {callback.from_user.id} перешел к вводу email")

    except Exception as e:
        logger.error(f"Ошибка перехода к вводу email: {e}", exc_info=True)

@router.message(Reg_token.email)
async def reg_token_email(message: Message, state: FSMContext):
    """Ввод email при регистрации по токену"""
    logger.info(f"Пользователь {message.from_user.id} ввел email: {message.text}")

    try:
        validated_email = validate_email(message.text)
        logger.debug(f"Email валидирован: {validated_email}")

        await state.update_data(email=validated_email)
        await state.set_state(Reg_token.phone)
        await message.answer('Введите ваш номер телефона')

    except ValueError as e:
        logger.warning(f"Невалидный email от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка обработки email: {e}", exc_info=True)

@router.message(Reg_token.phone)
async def reg_token_end(message: Message, state: FSMContext):
    """Завершение регистрации по токену"""
    logger.info(f"Пользователь {message.from_user.id} ввел телефон: {message.text}")

    try:
        validated_phone = validate_phone(message.text)
        logger.debug(f"Телефон валидирован: {validated_phone[:3]}...{validated_phone[-3:]}")

        await state.update_data(phone=validated_phone)
        await state.set_state(Reg_token.end_reg)
        await message.answer('Регистрация завершается...')

    except ValueError as e:
        logger.warning(f"Невалидный телефон от пользователя {message.from_user.id}: {message.text}")
        await message.answer(str(e))
        return

    try:
        data = await state.get_data()
        token = data.get('token')

        if not token:
            logger.error("Токен не найден в данных состояния")
            await message.answer('Ошибка: токен не найден. Начните регистрацию заново.')
            await state.clear()
            return

        # Операция записи - привязка Telegram и обновление данных
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_manager = UserManager(uow.session)
                user_repo = UserRepository(uow.session)

                logger.info(f"Привязка Telegram ID {message.from_user.id} к пользователю по токену {token[:8]}...")

                linked_user = await user_manager.link_telegram_to_user(token, message.from_user.id)

                if not linked_user:
                    logger.warning(f"Не удалось привязать пользователя по токену {token[:8]}...")
                    await message.answer(
                        'Токен недействителен или уже использован. Обратитесь к администратору.',
                        reply_markup=kb.inline_in_menu
                    )
                    await state.clear()
                    return

                update_data = {}
                if 'email' in data:
                    update_data['email'] = data['email']
                if 'phone' in data:
                    update_data['phone_number'] = data['phone']

                if update_data:
                    logger.debug(f"Обновление данных пользователя {linked_user.id}: {list(update_data.keys())}")
                    await user_repo.update(linked_user.id, **update_data)

                # Получаем обновленного пользователя
                updated_user = await user_repo.get_by_id(linked_user.id)

                birth_date_str = ""
                if updated_user.date_of_birth:
                    birth_date_str = updated_user.date_of_birth.strftime("%d.%m.%Y")

                logger.info(f"Пользователь {updated_user.id} успешно зарегистрирован по токену")

                await message.answer(
                    "Теперь вы сами управляете своими данными!\n\n"
                    "Проверьте данные:\n"
                    f"Фамилия, имя: {updated_user.full_name}\n"
                    f"Дата рождения: {birth_date_str}\n"
                    f"Вес: {updated_user.weight} кг\n"
                    f"Адрес: {updated_user.address}\n"
                    f"Телефон: {updated_user.phone_number}\n"
                    f"Email: {updated_user.email}",
                    reply_markup=await kb.registration_data_menu_builder()
                )

        await state.clear()
        logger.debug(f"Состояние очищено для пользователя {message.from_user.id}")

    except ValueError as e:
        logger.error(f"Ошибка валидации при регистрации по токену: {e}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка завершения регистрации по токену: {e}", exc_info=True)
        await state.clear()
        await message.answer(
            'Произошла ошибка при регистрации. Попробуйте позже или обратитесь к администратору.',
            reply_markup=kb.inline_in_menu
        )
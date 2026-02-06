from datetime import datetime, date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from pydantic import BaseModel, Field, EmailStr

import app.user_panel.keyboards as kb

from app.user_panel.states import Reg_user, Reg_token, Reg_child
from app.database.requests import DatabaseManager, FileManager
from app.database.models import UserRole, RegistrationType, async_session, FileType
from app.utils.validation import (validate_email, validate_phone, validate_name,
                                  validate_surname, validate_birthdate,
                                  validate_weight, validate_address
                                  )
from app.utils.logging_config import get_logger


router = Router(name="registration")

logger = get_logger(__name__)


class User(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Имя")
    surname: str = Field(..., min_length=1, max_length=50, description="Фамилия")
    date_of_birth: str = Field(..., description="Дата рождения")
    age: int = Field(..., ge=0, le=150, description="Возраст")
    weight: int = Field(..., gt=0, le=300, description="Вес в кг")
    address: str = Field(..., min_length=1, max_length=150, description="Адрес проживания")
    phone: str = Field(..., description="Номер телефона")
    email: EmailStr = Field(..., description="Email адрес")

class Child(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Имя")
    surname: str = Field(..., min_length=1, max_length=50, description="Фамилия")
    date_of_birth: str = Field(..., description="Дата рождения")
    age: int = Field(..., ge=0, le=150, description="Возраст")
    weight: int = Field(..., gt=0, le=300, description="Вес в кг")
    address: str = Field(..., min_length=1, max_length=150, description="Адрес проживания")
    parent_id: int = Field(..., ge=0, description="ID родителя")


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


@router.message(F.text == 'Личный кабинет')
async def registration_data(message: Message, state: FSMContext):
    """Обработчик личного кабинета - объединенная логика"""
    user_telegram_id = message.from_user.id
    logger.info(f"Пользователь {user_telegram_id} открыл личный кабинет")
    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            user = await db.get_user_by_telegram_id(user_telegram_id)
            if user:
                logger.debug(f"Пользователь {user_telegram_id} зарегистрирован, показываем кабинет")
                has_children = await db.user_has_children(user.id)
                keyboard = await kb.registration_data_menu_builder(has_children=has_children)
                user_info = (
                    f"Ваш личный кабинет\n\n"
                    f"Имя: {user.full_name or 'Не указано'}\n"
                    f"Телефон: {user.phone_number or 'Не указано'}\n"
                    f"Email: {user.email or 'Не указано'}\n"
                )
                if has_children:
                    children = await db.get_children_users(user.id)
                    user_info += f"\nДетей зарегистрировано: {len(children)}"
                await message.answer(user_info, reply_markup=keyboard)
            else:
                logger.debug(f"Пользователь {user_telegram_id} не зарегистрирован, начало регистрации")
                await state.set_state(Reg_user.is_token)
                await message.answer(
                    'Для начала давайте зарегистрируемся!\n\n'
                    'Если вас ранее регистрировал другой человек, то выдается '
                    'специальный токен (набор символов). Есть ли он у вас?',
                    reply_markup=kb.inline_is_token
                )
    except Exception as e:
        logger.error(f"Ошибка в личном кабинете для пользователя {user_telegram_id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при открытии личного кабинета. Попробуйте еще раз.",
            reply_markup=kb.main
        )

@router.callback_query(F.data == 'child_choice')
async def child_choice(callback: CallbackQuery):
    """Показать список детей с данными для редактирования"""
    user_telegram_id = callback.from_user.id

    try:
        async with async_session() as session:
            db = DatabaseManager(session)
            user = await db.get_user_by_telegram_id(user_telegram_id)

            if not user:
                await callback.answer("Пользователь не найден", show_alert=True)
                return

            children = await db.get_children_users(user.id)

            if not children:
                await callback.answer("У вас нет зарегистрированных детей", show_alert=True)
                return

            # Создаем сообщение с информацией о детях
            message_text = "Ваши дети\n\n"

            for i, child in enumerate(children, 1):
                message_text += f"{i}. {child.full_name}\n"

                if hasattr(child, 'verification_token') and child.verification_token:
                    message_text += f"   Токен: {child.verification_token}\n"

                if hasattr(child, 'date_of_birth') and child.date_of_birth:
                    birth_date = child.date_of_birth
                    if isinstance(birth_date, str):
                        message_text += f"   Дата рождения: {birth_date}\n"
                    else:
                        message_text += f"   Дата рождения: {birth_date.strftime('%d.%m.%Y')}\n"

                if hasattr(child, 'address') and child.address:
                    message_text += f"   Адрес: {child.address}\n"

                if hasattr(child, 'weight') and child.weight:
                    message_text += f"   Вес: {child.weight} кг\n"

                message_text += "\n"

            message_text += "\nВыберите ребенка для редактирования:"

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            for child in children:
                builder.button(
                    text=f"{child.full_name}",
                    callback_data=f"edit_child:{child.id}"
                )
            builder.button(text="Добавить ребенка", callback_data="reg_child")
            builder.button(text="Назад в кабинет", callback_data="back_to_cabinet")
            builder.button(text="В главное меню", callback_data="back_to_main")

            builder.adjust(1)

            try:
                await callback.message.edit_text(
                    message_text,
                    reply_markup=builder.as_markup()
                )
            except Exception:
                await callback.message.answer(
                    message_text,
                    reply_markup=builder.as_markup()
                )

    except Exception as e:
        logger.error(f"Ошибка показа данных детей: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data == 'back_to_cabinet')
async def back_to_cabinet(callback: CallbackQuery):
    """Вернуться в личный кабинет"""
    user_id = callback.from_user.id

    try:
        async with async_session() as session:
            db = DatabaseManager(session)

            user = await db.get_user_by_telegram_id(user_id)
            if not user:
                await callback.answer("Ошибка", show_alert=True)
                return

            has_children = await db.user_has_children(user.id)
            keyboard = await kb.registration_data_menu_builder(has_children=has_children)

            user_info = (
                f"Ваш личный кабинет\n\n"
                f"Имя: {user.full_name or 'Не указано'}\n"
                f"Телефон: {user.phone_number or 'Не указано'}\n"
                f"Email: {user.email or 'Не указано'}\n"
            )

            if has_children:
                children = await db.get_children_users(user.id)
                user_info += f"\nДетей зарегистрировано: {len(children)}"

            await callback.message.edit_text(
                user_info,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Ошибка возврата в кабинет: {e}")
        await callback.answer("Ошибка", show_alert=True)


# ===== РЕГИСТРАЦИЯ ПО ТОКЕНУ =====


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
            db = DatabaseManager(session)
            user = await db.get_user_by_token(token)

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
                creator = await db.get_user_by_id(user.created_by_id)
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
                    reply_markup=kb.inline_pd_consent_token
                )
                return

            # Получаем полную запись для логирования
            file_record = await file_manager.get_file_record(FileType.CPD)
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

        async with async_session() as session:
            db = DatabaseManager(session)

            logger.info(f"Привязка Telegram ID {message.from_user.id} к пользователю по токену {token[:8]}...")

            linked_user = await db.link_telegram_to_user(token, message.from_user.id)

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
                success_update = await db.update_user_data(
                    telegram_id=message.from_user.id,
                    **update_data
                )

            updated_user = await db.get_user_by_telegram_id(message.from_user.id)

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


# ===== РЕГИСТРАЦИЯ РЕБЕНКА =====


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
            file_manager = FileManager(session)
            file_id = await file_manager.get_file_id(FileType.CPD_MINOR)

            db = DatabaseManager(session)
            user = await db.get_user_by_telegram_id(message.from_user.id)
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
            file_record = await file_manager.get_file_record(FileType.CPD_MINOR)
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

def get_age(birth_date: str) -> int:
    """Получает дату в формате %d.%m.%Y и возвращает возраст в годах"""
    today = date.today()
    _date = datetime.strptime(birth_date, "%d.%m.%Y").date()
    age = today.year - _date.year
    if today.month < _date.month or (today.month == _date.month and today.day < _date.day):
        age -= 1
    return age

@router.message(Reg_child.date_of_birth)
async def reg_child_age(message: Message, state: FSMContext):
    """Ввод даты рождения ребенка"""
    logger.info(f"Пользователь {message.from_user.id} ввел дату рождения ребенка: '{message.text}'")

    try:
        validated_date = validate_birthdate(message.text)
        age = get_age(validated_date)

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

        final_child = Child(**child_data)
        full_child_name = final_child.surname + ' ' + final_child.name
        date_of_birth = datetime.strptime(final_child.date_of_birth, "%d.%m.%Y").date()

        logger.info(f"Создание ребенка: {full_child_name}, дата рождения: {date_of_birth}")

        async with async_session() as session:
            db = DatabaseManager(session)

            child, child_token = await db.create_child_user(
                child_name=full_child_name,
                parent_telegram_id=message.from_user.id,
                date_of_birth=date_of_birth,
                weight=final_child.weight,
                address=final_child.address
            )

            if child:
                logger.info(f"Ребенок создан: ID={child.id}, имя='{child.full_name}', токен={child_token}")
            else:
                logger.error("Ошибка создания ребенка: объект не возвращен")
                raise ValueError('Ошибка создания ребенка')

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


# ===== РЕГИСТРАЦИЯ БЕЗ ТОКЕНА =====


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
        age = get_age(validated_date)

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
async def reg_phone(message: Message, state: FSMContext):
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
'''
Роутер для добавления клиента администратором
'''
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import app.admin_panel.keyboards_adm as kb_adm

from app.admin_panel.states_adm import AdminAddClient
from app.database.managers import UserManager
from app.database.unit_of_work import UnitOfWork
from app.database.session import async_session
from app.database.repositories import UserRepository
from app.middlewares import AdminMiddleware
from app.utils.validation import (
    validate_name,
    validate_surname,
    validate_phone,
    validate_birthdate,
    validate_weight
)
from app.utils.datetime_utils import calculate_age
from app.utils.logging_config import get_logger


router = Router(name="admin_add_client")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

logger = get_logger(__name__)


@router.message(F.text == "Добавить клиента")
async def add_client_start(message: Message, state: FSMContext):
    """Начало добавления клиента администратором"""
    logger.info(f"Администратор {message.from_user.id} начал добавление клиента")

    try:
        await state.set_state(AdminAddClient.waiting_for_name)
        await message.answer(
            'Вы добавляете нового клиента.\n'
            'Этот клиент не будет привязан к Telegram и сможет записываться на экскурсии только через администратора.\n\n'
            'Введите имя клиента:',
            reply_markup=kb_adm.cancel_button()
        )
    except Exception as e:
        logger.error(f"Ошибка начала добавления клиента: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.message(AdminAddClient.waiting_for_name)
async def add_client_surname(message: Message, state: FSMContext):
    """Ввод фамилии клиента"""
    logger.info(f"Администратор {message.from_user.id} ввел имя клиента: '{message.text}'")

    try:
        validated_name = validate_name(message.text)
        await state.update_data(name=validated_name)
        await state.set_state(AdminAddClient.waiting_for_surname)

        await message.answer('Введите фамилию клиента:',
                             reply_markup=kb_adm.cancel_button())
    except ValueError as e:
        logger.warning(f"Невалидное имя от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка при вводе имени: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.message(AdminAddClient.waiting_for_surname)
async def add_client_phone(message: Message, state: FSMContext):
    """Ввод телефона клиента"""
    logger.info(f"Администратор {message.from_user.id} ввел фамилию клиента: '{message.text}'")

    try:
        validated_surname = validate_surname(message.text)
        await state.update_data(surname=validated_surname)
        await state.set_state(AdminAddClient.waiting_for_phone)

        await message.answer(
            'Введите номер телефона клиента в формате +7XXXXXXXXXX или 8XXXXXXXXXX:',
            reply_markup=kb_adm.cancel_button()
        )
    except ValueError as e:
        logger.warning(f"Невалидная фамилия от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка при вводе фамилии: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.message(AdminAddClient.waiting_for_phone)
async def add_client_birthdate(message: Message, state: FSMContext):
    """Ввод и проверка телефона, переход к дате рождения"""
    logger.info(f"Администратор {message.from_user.id} ввел телефон клиента: '{message.text}'")

    try:
        validated_phone = validate_phone(message.text)

        # Проверка уникальности телефона
        async with async_session() as session:
            user_repo = UserRepository(session)
            existing_user = await user_repo.get_by_phone(validated_phone)

            if existing_user:
                logger.warning(f"Попытка добавить существующий номер {validated_phone}")
                await message.answer(
                    f'Клиент с номером {validated_phone} уже существует в системе.\n'
                    f'Используйте поиск клиента для работы с ним.',
                    reply_markup=kb_adm.clients_submenu()
                )
                await state.clear()
                return

        await state.update_data(phone=validated_phone)
        await state.set_state(AdminAddClient.waiting_for_birthdate)

        await message.answer(
            'Введите дату рождения клиента в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ\n'
            '(например, 09.05.1945 или 09.05.45)\n\n'
            'Это необходимо для расчета скидок и определения возрастной категории.\n\n'
            'Если вы не знаете точную дату рождения, введите примерную.\n'
            'Учтите, что если вы вводите дату рождения, предполагающую несовершеннолетний возраст, '
            'то клиент сможет самостоятельно управлять аккаунтом через токен только при достижении 18 лет',
            reply_markup=kb_adm.cancel_button()
        )

    except ValueError as e:
        logger.warning(f"Невалидный телефон от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e),
            reply_markup=kb_adm.cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при вводе телефона: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.",
                    reply_markup=kb_adm.clients_submenu())
        await state.clear()


@router.message(AdminAddClient.waiting_for_birthdate)
async def add_client_weight(message: Message, state: FSMContext):
    """Ввод даты рождения, переход к весу"""
    logger.info(f"Администратор {message.from_user.id} ввел дату рождения: '{message.text}'")

    try:
        validated_date = validate_birthdate(message.text)
        age = calculate_age(validated_date)

        await state.update_data(birthdate=validated_date)
        await state.update_data(age=age)
        await state.set_state(AdminAddClient.waiting_for_weight)

        await message.answer(
            'Введите примерный вес клиента в килограммах (целое число от 1 до 299).\n\n'
            'Это необходимо для расчета вместимости лодки.',
            reply_markup=kb_adm.cancel_button()
        )

    except ValueError as e:
        logger.warning(f"Невалидная дата рождения от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e),
            reply_markup=kb_adm.cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при вводе даты рождения: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.",
                    reply_markup=kb_adm.clients_submenu())
        await state.clear()


@router.message(AdminAddClient.waiting_for_weight)
async def add_client_confirmation(message: Message, state: FSMContext):
    """Ввод веса и переход к подтверждению"""
    logger.info(f"Администратор {message.from_user.id} ввел вес: '{message.text}'")

    try:
        validated_weight = validate_weight(message.text)
        await state.update_data(weight=validated_weight)

        # Получаем все данные для подтверждения
        data = await state.get_data()
        age = data.get('age', 'неизвестно')

        # Формируем сообщение с данными
        confirmation_text = (
            f"Проверьте данные клиента:\n\n"
            f"Имя: {data['name']}\n"
            f"Фамилия: {data['surname']}\n"
            f"Телефон: {data['phone']}\n"
            f"Дата рождения: {data['birthdate'].strftime('%d.%m.%Y')}\n"
            f"Возраст: {age} лет\n"
            f"Вес: {data['weight']} кг\n\n"
            f"Всё верно?"
        )

        await state.set_state(AdminAddClient.waiting_for_confirmation)
        await message.answer(
            confirmation_text,
            reply_markup=kb_adm.add_client_confirmation_keyboard(data)
        )

    except ValueError as e:
        logger.warning(f"Невалидный вес от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e),
                    reply_markup=kb_adm.cancel_button())
    except Exception as e:
        logger.error(f"Ошибка при вводе веса: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте позже.",
                    reply_markup=kb_adm.clients_submenu())
        await state.clear()


@router.callback_query(F.data == "confirm_add_client", AdminAddClient.waiting_for_confirmation)
async def confirm_add_client(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и сохранение клиента"""
    logger.info(f"Администратор {callback.from_user.id} подтверждает добавление клиента")

    try:
        await callback.answer()

        data = await state.get_data()
        admin_id = callback.from_user.id

        # Получаем ID администратора в системе
        async with async_session() as session:
            user_repo = UserRepository(session)
            admin = await user_repo.get_by_telegram_id(admin_id)

        # Создаем клиента
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                user_manager = UserManager(uow.session)
                user, token = await user_manager.create_user_by_admin(
                    full_name=f"{data['surname']} {data['name']}",
                    phone_number=data['phone'],
                    admin_id=admin.id,
                    date_of_birth=data['birthdate'],
                    weight=data['weight']
                )

        # Формируем виртуальный телефон для отображения
        virtual_phone = f"{data['phone']}:{token}:by_admin"

        await callback.message.answer(
            f"Клиент успешно добавлен!\n\n"
            f"Данные клиента:\n"
            f"Имя: {data['name']}\n"
            f"Фамилия: {data['surname']}\n"
            f"Телефон: {data['phone']}\n"
            f"Дата рождения: {data['birthdate'].strftime('%d.%m.%Y')}\n"
            f"Возраст: {data.get('age')} лет\n"
            f"Вес: {data['weight']} кг\n\n"
            f"Токен для регистрации:\n"
            f"<code>{token}</code>\n\n"
            f"Виртуальный телефон (для записей через администратора):\n"
            f"<code>{virtual_phone}</code>\n\n"
            f"Передайте этот токен клиенту. При вводе токена в боте он сможет "
            f"привязать свой Telegram и управлять аккаунтом самостоятельно.",
            reply_markup=kb_adm.clients_submenu()
        )
        await callback.message.delete()
        logger.info(f"Клиент {user.id} успешно создан администратором {admin_id}, токен: {token}")
        await state.clear()

    except ValueError as e:
        logger.error(f"Ошибка валидации при создании клиента: {e}")
        await callback.message.answer(
            f"Ошибка при создании клиента: {e}",
            reply_markup=kb_adm.clients_submenu()
        )
        await callback.message.delete()
        await state.clear()
    except Exception as e:
        logger.error(f"Неизвестная ошибка при создании клиента: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при сохранении клиента. Попробуйте позже.",
            reply_markup=kb_adm.clients_submenu()
        )
        await callback.message.delete()
        await state.clear()


@router.callback_query(F.data == "edit_client_data", AdminAddClient.waiting_for_confirmation)
async def edit_client_data(callback: CallbackQuery, state: FSMContext):
    """Возврат к редактированию данных"""
    logger.info(f"Администратор {callback.from_user.id} хочет изменить данные клиента")

    await callback.answer()
    await state.set_state(AdminAddClient.waiting_for_name)

    await callback.message.answer(
        "Введите имя клиента заново:",
        reply_markup=kb_adm.cancel_button()
    )
    await callback.message.delete()


@router.callback_query(F.data == "cancel_add_client", AdminAddClient.waiting_for_confirmation)
async def cancel_add_client(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления клиента"""
    logger.info(f"Администратор {callback.from_user.id} отменил добавление клиента")

    await callback.answer()
    await state.clear()

    await callback.message.answer(
        "Добавление клиента отменено.",
        reply_markup=kb_adm.clients_submenu()
    )
    await callback.message.delete()


@router.message(F.text == "Отмена", AdminAddClient.waiting_for_name)
@router.message(F.text == "Отмена", AdminAddClient.waiting_for_surname)
@router.message(F.text == "Отмена", AdminAddClient.waiting_for_phone)
@router.message(F.text == "Отмена", AdminAddClient.waiting_for_birthdate)
@router.message(F.text == "Отмена", AdminAddClient.waiting_for_weight)
async def cancel_any_state(message: Message, state: FSMContext):
    """Отмена на любом этапе через кнопку Отмена"""
    logger.info(f"Администратор {message.from_user.id} отменил операцию")

    await state.clear()
    await message.answer(
        "Добавление клиента отменено.",
        reply_markup=kb_adm.clients_submenu()
    )
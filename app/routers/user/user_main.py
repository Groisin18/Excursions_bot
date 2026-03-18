from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction

from app.user_panel.keyboards import (
    main_menu, feedback, about_us, questions
)
from app.utils.logging_config import get_logger

ADMIN_LOGIN = '@EkaterinkaMinyaylova'

router = Router(name="user")

logger = get_logger(__name__)


@router.message(CommandStart())
async def start_command(message: Message):
    """Обработка команды /start"""
    logger.info(f"Новый пользователь запустил бота: {message.from_user.id} "
                f"({message.from_user.username or 'без username'})")
    try:
        await message.bot.send_chat_action(
            chat_id=message.from_user.id,
            action=ChatAction.TYPING
        )
        await message.answer(
            text='Приветствуем! Добро пожаловать в наш бот! Выберите необходимый пункт меню',
            reply_markup=main_menu()
        )
        logger.info(f"Приветственное сообщение отправлено пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при запуске бота. Попробуйте еще раз нажать /start.")


@router.message(Command("help"))
async def help_command(message: Message):
    """Обработка команды /help"""
    logger.info(f"Пользователь {message.from_user.id} запросил помощь")
    try:
        await message.reply(
            'Привет! Это команда /help.\n'
            '/admin - админ-панель\n'
            '/adminhelp - список команд админа',
            reply_markup=main_menu()
        )
        logger.debug(f"Справочное сообщение отправлено пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке справки пользователю {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'back_to_main')
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    logger.info(f"Пользователь {callback.from_user.id} вернулся в главное меню")
    try:
        current_state = await state.get_state()
        if current_state:
            logger.debug(f"Пользователь {callback.from_user.id} вышел из состояния: {current_state}")
        await state.clear()
        await callback.answer()
        await callback.message.answer(
            'Выберите необходимый пункт меню',
            reply_markup=main_menu()
        )
        logger.debug(f"Главное меню показано пользователю {callback.from_user.id}")
    except Exception as e:
        await callback.answer()
        logger.error(f"Ошибка возврата в главное меню для пользователя {callback.from_user.id}: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text == 'Назад в меню')
async def back_to_main_menu(message: Message):
    """Возврат в главное меню"""
    logger.info(f"Пользователь {message.from_user.id} вернулся в главное меню")
    try:
        await message.answer(
            "Вы вернулись в главное меню",
            reply_markup=main_menu()
        )
        logger.debug(f"Главное меню показано пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка возврата в главное меню для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text == 'Отзывы')
async def reviews(message: Message):
    """Показать отзывы"""
    logger.info(f"Пользователь {message.from_user.id} запросил отзывы")
    try:
        await message.answer(
            'Отзывы о наших экскурсиях вы можете посмотреть в нашей группе.\n'
            'Там же есть много фотографий с экскурсий.\n'
            'Если вы уже бывали у нас, обязательно оставьте свое мнение!',
            reply_markup=feedback()
        )
        logger.debug(f"Ссылки на отзывы отправлены пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка показа отзывов для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text == 'О нас')
async def about_us(message: Message):
    """Информация о компании"""
    logger.info(f"Пользователь {message.from_user.id} запросил информацию о компании")
    try:
        await message.answer(
            'Экскурсии по Ангаре из г. Братск до местных природных достопримечательностей\n\n'
            'Обязательно посетите наши ресурсы:\n'
            ' - Беседа с живыми отзывами и фотографиями\n'
            ' - Группа ВКонтакте\n'
            ' - Наш уютный и познавательный Телеграм-канал',
            reply_markup=about_us()
        )
        logger.debug(f"Информация о компании отправлена пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка показа информации о компании для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text == 'Основные вопросы')
async def questions(message: Message):
    """Показать FAQ"""
    logger.info(f"Пользователь {message.from_user.id} открыл раздел вопросов")
    try:
        await message.answer(
            'Ответы на основные вопросы.\n\n'
            'Если у вас есть другой вопрос, можете задать его нашему администратору\n'
            f'{ADMIN_LOGIN}',
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            'Выберите вопрос:',
            reply_markup=questions()
        )
        logger.debug(f"FAQ показан пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка показа FAQ для пользователя {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'qu_startplace')
async def qu_startplace(callback: CallbackQuery):
    """Ответ на вопрос о месте старта"""
    logger.info(f"Пользователь {callback.from_user.id} выбрал вопрос о месте старта")
    await callback.answer()
    try:
        await callback.message.edit_text(
            'Осенние экскурсии:\n'
            'Стартуем от адреса Пирогова 10.\n'
            'Одеваемся теплее, важна многослойность. '
            'Теплая, удобная обувь. Перчатки или варежки.\n'
            'Экскурсия будет на автомобиле с прогулками по значимым местам района.\n\n'
            'Летние экскурсии:\n'
            'Доезжаете до кафе "Ладушки" по адресу Пирогова 13,'
            ' и оттуда мы вместе отправляемся на пирс.'
            'Сам пирс находится в конце острова Тенга.\n'
            'Точные координаты пирса: 56.390966, 101.839879'
            'Далее на нашем судне отправляемся на экскурсию.',
            reply_markup=questions()
        )
        logger.debug(f"Ответ о месте старта отправлен пользователю {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа о месте старта: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'qu_things_witn')
async def qu_things_witn(callback: CallbackQuery):
    """Ответ на вопрос о вещах с собой"""
    logger.info(f"Пользователь {callback.from_user.id} выбрал вопрос о вещах с собой")
    await callback.answer()
    try:
        await callback.message.edit_text(
            'На Ангаре холодно.\n'
            'По одежде штаны, кофта, головной убор, кроссовки на удобной подошве.\n'
            'Куртка (желательно, непромокаемая).\n'
            'Носки высокие, чтобы можно было в них заправить штаны.\n'
            'Можно взять внешний аккумулятор (Power Bank).\n'
            'Можете взять свой маленький термос с чаем, '
            'но у нас будут свои, поэтому без чая не останетесь =)\n',
            reply_markup=questions()
        )
        logger.debug(f"Ответ о вещах с собой отправлен пользователю {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа о вещах с собой: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'qu_discount')
async def qu_discount(callback: CallbackQuery):
    """Ответ на вопрос о скидках"""
    logger.info(f"Пользователь {callback.from_user.id} выбрал вопрос о скидках")
    await callback.answer()
    try:
        await callback.message.edit_text(
            'У нас есть скидки детям:\n'
            'Дети до 3 лет бесплатно.\n'
            '4-7 лет - скидка 60%;\n'
            '8-12 лет - скидка 40%;\n'
            '13 лет и старше - полная стоимость билета.\n\n'
            'А в нашей группе иногда бывают скидочные промокоды :)',
            reply_markup=questions()
        )
        logger.debug(f"Ответ о скидках отправлен пользователю {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа о скидках: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.callback_query(F.data == 'qu_self_co')
async def qu_self_co(callback: CallbackQuery):
    """Ответ на вопрос об индивидуальных экскурсиях"""
    logger.info(f"Пользователь {callback.from_user.id} выбрал вопрос об индивидуальных экскурсиях")
    await callback.answer()
    try:
        await callback.message.edit_text(
            'Хотите отдохнуть только своей компанией?\n'
            'Мы готовы предоставить вам экскурсию.\n'
            'Если вы хотите пойти на экскурсию исключительно своей компанией,'
            ' то напишите администратору:\n'
            f'{ADMIN_LOGIN}\n'
            'Мы выберем подходящий маршрут, день и время.\n'
            'Доступны и будние дни, и выходные.\n\n'
            'Индивидуальные экскурсии проводятся компаниям от 4 человек.',
            reply_markup=questions()
        )
        logger.debug(f"Ответ об индивидуальных экскурсиях отправлен пользователю {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа об индивидуальных экскурсиях: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text.contains('админ') | F.text.contains('администратор'))
async def mention_admin(message: Message):
    """Автоматический ответ при упоминании администратора"""
    logger.info(f"Пользователь {message.from_user.id} упомянул администратора в сообщении")

    try:
        await message.answer(
            'Для связи с администратором используйте контакт:\n'
            f'{ADMIN_LOGIN}\n\n'
            'Или выберите нужный пункт в меню.',
            reply_markup=main_menu()
        )

        logger.debug(f"Ответ об администраторе отправлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка отправки ответа об администраторе: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )

@router.message(F.text.contains('цена') | F.text.contains('стоимость'))
async def mention_price(message: Message):
    """Автоматический ответ при упоминании цены"""
    logger.info(f"Пользователь {message.from_user.id} спросил о цене")

    try:
        await message.answer(
            'Стоимость экскурсий зависит от выбранного маршрута и количества человек.\n'
            'Выберите "Наши экскурсии" в меню, чтобы увидеть доступные варианты.\n\n'
            f'Для индивидуального расчета стоимости свяжитесь с администратором: {ADMIN_LOGIN}',
            reply_markup=main_menu()
        )

        logger.debug(f"Ответ о стоимости отправлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка отправки ответа о стоимости: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu()
        )


@router.callback_query(F.data == "back_to_main_with_info")
async def back_to_main_with_info(callback: CallbackQuery):
    """
    Возврат в главное меню с информацией о необходимости оплаты.
    Вызывается сразу после создания бронирования.
    """
    user_telegram_id = callback.from_user.id
    logger.info(f"Пользователь {user_telegram_id} возвращается в главное меню после бронирования")

    try:
        await callback.answer()

        info_text = (
            "Бронирование создано!\n\n"
            "Важно: оплатить нужно в течение 24 часов, иначе бронь автоматически отменится.\n\n"
            "Вы всегда можете:\n"
            "• Оплатить бронь в разделе 'Личный кабинет' → 'Мои бронирования'\n"
            "• Отменить бронь там же, если передумаете\n\n"
            "Спасибо, что выбираете нас!"
        )

        await callback.message.answer(
            info_text,
            reply_markup=main_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}", exc_info=True)
        await callback.message.answer(
            "Возврат в главное меню",
            reply_markup=main_menu()
        )
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from pydantic import BaseModel, Field
from typing import Optional

from app.utils.validation import Validators
from app.admin_panel.states_adm import (NewExcursion, RedactExcursion)
from app.database.requests import DatabaseManager
from app.database.models import async_session
from app.admin_panel.keyboards_adm import (
    excursions_submenu, err_add_exc, exc_redaction_builder,
    excursions_list_keyboard, excursion_actions_menu, inline_end_add_exc,
    admin_main_menu,
)
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger


logger = get_logger(__name__)


router = Router(name="admin_excursions")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


class ExcursionModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название экскурсии")
    description: Optional[str] = Field(None, description="Описание экскурсии")
    base_duration_minutes: int = Field(..., gt=0, description="Базовая продолжительность в минутах")
    base_price: int = Field(..., gt=0, description="Базовая цена в рублях")
    child_discount: int = Field(default=0, ge=0, le=100, description="Скидка для детей в процентах")
    is_active: bool = Field(default=True, description="Активна ли экскурсия")


# ===== УПРАВЛЕНИЕ ЭКСКУРСИЯМИ =====

@router.callback_query(F.data == "back_to_exc_menu")
async def excursions_management(callback:CallbackQuery):
    """Меню управления экскурсиями"""
    logger.debug(f"Администратор {callback.from_user.id} вернулся в меню управления экскурсиями")

    try:
        await callback.message.answer(
            "Управление экскурсиями:",
            reply_markup=excursions_submenu()
        )
        await callback.answer()
        logger.debug(f"Меню управления экскурсиями показано администратору {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка показа меню управления экскурсиями: {e}", exc_info=True)

@router.message(F.text == "Список видов экскурсий")
async def show_excursions(message: Message):
    """Показать все экскурсии"""
    logger.info(f"Администратор {message.from_user.id} запросил список экскурсий")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursions = await db_manager.get_all_excursions()

            if not excursions:
                logger.debug("Экскурсии не найдены в базе данных")
                await message.answer("Экскурсии не найдены")
                return

            logger.info(f"Найдено экскурсий: {len(excursions)}")
            response = "Доступные экскурсии:\n\n"
            for excursion in excursions:
                status = "Активна" if excursion.is_active else "Неактивна"
                response += (
                    f"ID: {excursion.id}\n"
                    f"Название: {excursion.name}\n"
                    f"Длительность: {excursion.base_duration_minutes} мин.\n"
                    f"Цена: {excursion.base_price} руб.\n"
                    f"Статус: {status}\n"
                    f"---\n"
                )

            await message.answer(response)
            logger.debug(f"Список экскурсий отправлен администратору {message.from_user.id}")

            await message.answer('Выберите экскурсию для дополнительных действий',
                                reply_markup=excursions_list_keyboard(excursions, active_only=False))
            logger.debug(f"Клавиатура выбора экскурсий показана администратору {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка экскурсий: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка экскурсий")

@router.callback_query(F.data.startswith('excursion_actions:'))
async def exc_actions(callback:CallbackQuery):
    """Действия с конкретной экскурсией"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} открыл действия для экскурсии {exc_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursion = await db_manager.get_excursion_by_id(exc_id)

            if not excursion:
                logger.warning(f"Экскурсия {exc_id} не найдена")
                await callback.message.answer("Экскурсия не найдена")
                return

            status = "Активна" if excursion.is_active else "Неактивна"
            logger.debug(f"Показана информация об экскурсии {exc_id}: {excursion.name}")

            await callback.message.answer(
                    f"ID: {excursion.id}\n"
                    f"Название: {excursion.name}\n"
                    f"Длительность: {excursion.base_duration_minutes} мин.\n"
                    f"Цена: {excursion.base_price} руб.\n"
                    f"Статус: {status}\n",
                    reply_markup=excursion_actions_menu(exc_id))

    except Exception as e:
        logger.error(f"Ошибка получения информации об экскурсии {exc_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при получении информации об экскурсии")


@router.message(F.text == "Назад")
async def back_from_excursions_submenu(message: Message, state: FSMContext):
    """Возврат из подменю экскурсий в главное меню"""
    logger.debug(f"Администратор {message.from_user.id} нажал 'Назад' в подменю экскурсий")

    try:
        await state.clear()
        await message.answer(
            "Главное меню администратора:",
            reply_markup=admin_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка возврата из подменю: {e}", exc_info=True)


# ===== НОВЫЙ ВИД ЭКСКУРСИИ =====

@router.callback_query(F.data == "create_excursion")
async def new_excursion(callback:CallbackQuery, state: FSMContext):
    """Создание новой экскурсии"""
    logger.info(f"Администратор {callback.from_user.id} начал создание новой экскурсии")

    try:
        await state.set_state(NewExcursion.name)
        await callback.message.answer('Введите название экскурсии')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние ввода названия")
    except Exception as e:
        logger.error(f"Ошибка начала создания экскурсии: {e}", exc_info=True)

@router.message(F.text == "Новый вид экскурсии")
async def new_excursion_message(message: Message, state: FSMContext):
    """Создание новой экскурсии"""
    logger.info(f"Администратор {message.from_user.id} начал создание новой экскурсии")

    try:
        await state.set_state(NewExcursion.name)
        await message.answer('Введите название экскурсии')
        logger.debug(f"Администратор {message.from_user.id} перешел в состояние ввода названия")
    except Exception as e:
        logger.error(f"Ошибка начала создания экскурсии: {e}", exc_info=True)

@router.message(NewExcursion.name)
async def reg_ex_name(message: Message, state: FSMContext):
    """Ввод названия экскурсии"""
    logger.info(f"Администратор {message.from_user.id} ввел название: '{message.text}'")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            exc_name = message.text
            excursion_exists = await db_manager.get_excursion_by_name(exc_name)

            if excursion_exists:
                logger.warning(f"Попытка создания дублирующей экскурсии: '{exc_name}' (ID: {excursion_exists.id})")
                await state.clear()
                await message.answer(f'Экскурсия с названием "{exc_name}" уже есть в базе данных под номером {excursion_exists.id}',
                                    reply_markup=excursions_submenu()
                                    )
            else:
                logger.debug(f"Название '{exc_name}' доступно для использования")
                await state.update_data(name=exc_name)
                await state.set_state(NewExcursion.description)
                await message.answer('Введите описание экскурсии')

    except Exception as e:
        logger.error(f"Ошибка проверки названия экскурсии: {e}", exc_info=True)
        await message.answer("Произошла ошибка при проверке названия")

@router.message(NewExcursion.description)
async def reg_ex_description(message: Message, state: FSMContext):
    """Ввод описания экскурсии"""
    exc_description = message.text
    logger.info(f"Администратор {message.from_user.id} ввел описание (длина: {len(exc_description)} символов)")

    try:
        await state.update_data(description=exc_description)
        await state.set_state(NewExcursion.base_duration_minutes)
        logger.debug(f"Описание сохранено, переход к вводу продолжительности")

        await message.answer('Введите примерную продолжительность экскурсии (от 10 минут до 48 часов)\n'
                             'Продолжительность должна быть кратной 10 минутам\n'
                             'Примеры:\n90 (90 минут),\n4:30 (4 часа 30 минут),\n2.00 (2 часа ровно)')
    except Exception as e:
        logger.error(f"Ошибка обработки описания: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке описания")

@router.message(NewExcursion.base_duration_minutes)
async def reg_exc_base_duration(message: Message, state: FSMContext):
    """Ввод продолжительности экскурсии"""
    logger.info(f"Администратор {message.from_user.id} ввел продолжительность: '{message.text}'")

    try:
        exc_base_duration = Validators.validate_excursion_duration(message.text)
        logger.debug(f"Продолжительность валидирована: {exc_base_duration} минут")

        await state.update_data(base_duration_minutes=exc_base_duration)
        await state.set_state(NewExcursion.base_price)
        await message.answer('Введите стоимость экскурсии в рублях (без скидок)')

    except ValueError as e:
        logger.warning(f"Невалидная продолжительность от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка обработки продолжительности: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке продолжительности")

@router.message(NewExcursion.base_price)
async def reg_exc_base_price(message: Message, state: FSMContext):
    """Ввод стоимости экскурсии"""
    logger.info(f"Администратор {message.from_user.id} ввел стоимость: '{message.text}'")

    try:
        exc_base_price = Validators.validate_amount_rub(message.text)
        logger.debug(f"Стоимость валидирована: {exc_base_price} руб.")

        await state.update_data(base_price=exc_base_price)
        await state.set_state(NewExcursion.child_discount)
        await message.answer('Введите размер скидки для детей (число от 0 до 100 процентов)')

    except ValueError as e:
        logger.warning(f"Невалидная стоимость от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Ошибка обработки стоимости: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке стоимости")

async def handle_registration(message, excursion):
    """Сохранение экскурсии в БД"""
    logger.info(f"Сохранение экскурсии '{excursion.name}' в базу данных")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursion = await db_manager.create_excursion(
                name=excursion.name,
                description=excursion.description,
                base_duration_minutes=excursion.base_duration_minutes,
                base_price=excursion.base_price,
                child_discount=excursion.child_discount,
                is_active=True
            )

            if excursion:
                logger.info(f"Экскурсия создана: ID={excursion.id}, название='{excursion.name}'")
                return excursion
            else:
                logger.error("Ошибка создания экскурсии: объект не возвращен")
                raise ValueError('Ошибка создания экскурсии!')

    except Exception as e:
        logger.error(f"Ошибка сохранения экскурсии в БД: {e}", exc_info=True)
        raise

@router.message(NewExcursion.child_discount)
async def reg_ex_child_discount(message: Message, state: FSMContext):
    """Ввод скидки для детей и завершение создания"""
    logger.info(f"Администратор {message.from_user.id} ввел скидку: '{message.text}'")

    try:
        exc_child_discount = Validators.validate_discount(message.text)
        logger.debug(f"Скидка валидирована: {exc_child_discount}%")

        await state.update_data(child_discount=exc_child_discount)
        await state.set_state(NewExcursion.end_reg)
        await message.answer('Создание экскурсии завершается...')

    except ValueError as e:
        logger.warning(f"Невалидная скидка от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
        return

    try:
        # Финальная проверка всей модели
        exc_data = await state.get_data()
        logger.debug(f"Данные для создания экскурсии: {exc_data}")

        final_exc = ExcursionModel(**exc_data)
        logger.info(f"Создание экскурсии: {final_exc.name}")

        # Сохраняем в БД
        exc = await handle_registration(message, final_exc)
        exc_id = exc.id

        logger.info(f"Экскурсия успешно создана: ID={exc_id}")

        await message.answer(
            "Создание экскурсии завершено!\n\n"
            "Данные:\n"
            f" - Название: {final_exc.name}\n"
            f' - Описание:\n"{final_exc.description}"\n'
            f" - Длительность в минутах: {final_exc.base_duration_minutes} минут\n"
            f" - Стоимость: {final_exc.base_price} рублей\n"
            f" - Скидка для детей: {final_exc.child_discount}%\n",
            reply_markup=inline_end_add_exc(exc_id)
            )

        await state.clear()
        logger.debug(f"Состояние FSM очищено для администратора {message.from_user.id}")

    except ValueError as e:
        logger.error(f"Ошибка валидации при создании экскурсии: {e}")
        await message.answer(str(e),
                            reply_markup=err_add_exc())
        await state.clear()
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании экскурсии: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка при создании экскурсии",
                            reply_markup=err_add_exc())
        await state.clear()


# ===== РЕДАКТИРОВАНИЕ ВИДА ЭКСКУРСИИ =====

@router.callback_query(F.data.startswith('redact_exc_data:'))
async def redact_exc_data(callback:CallbackQuery):
    """Показать данные экскурсии для редактирования"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} открыл редактирование экскурсии {exc_id}")

    await callback.answer('')

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            exc = await db_manager.get_excursion_by_id(exc_id)

            if not exc:
                logger.warning(f"Экскурсия {exc_id} не найдена для редактирования")
                await callback.message.answer("Экскурсия не найдена")
                return

            logger.debug(f"Данные экскурсии {exc_id} показаны для редактирования")

            await callback.message.answer(
                "Данные экскурсии на текущий момент:\n"
                f" - Название: {exc.name}\n"
                f' - Описание:\n"{exc.description}"\n'
                f" - Длительность в минутах: {exc.base_duration_minutes} минут\n"
                f" - Стоимость: {exc.base_price} рублей\n"
                f" - Скидка для детей: {exc.child_discount}%\n"
                f" - Статус: {'Активна' if exc.is_active else 'Не активна'}\n"
                "Выберите пункт, который хотите поменять",
                reply_markup=exc_redaction_builder(exc_id))

    except Exception as e:
        logger.error(f"Ошибка получения данных экскурсии {exc_id}: {e}", exc_info=True)
        await callback.message.answer("Ошибка при получении данных экскурсии")

@router.callback_query(F.data.startswith('redact_exc_name:'))
async def redact_name_one(callback:CallbackQuery, state:FSMContext):
    """Начало редактирования названия"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование названия экскурсии {exc_id}")

    await callback.answer('Редактируем название')

    try:
        await state.update_data(excursion_id=exc_id)
        await state.set_state(RedactExcursion.name)
        await callback.message.answer('Введите новое название')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние редактирования названия")
    except Exception as e:
        logger.error(f"Ошибка начала редактирования названия: {e}", exc_info=True)

@router.message(RedactExcursion.name)
async def redact_name_two(message: Message, state: FSMContext):
    """Завершение редактирования названия"""
    logger.info(f"Администратор {message.from_user.id} ввел новое название: '{message.text}'")

    try:
        new_name = message.text
        data = await state.get_data()
        exc_id = data.get('excursion_id')

        logger.debug(f"Проверка нового названия для экскурсии {exc_id}")

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            excursion_exists = await db_manager.get_excursion_by_name(new_name)

            if excursion_exists and excursion_exists.id != exc_id:
                logger.warning(f"Попытка переименования в существующее название: '{new_name}' (ID: {excursion_exists.id})")
                await message.answer(f'Экскурсия с названием "{new_name}" уже есть в базе данных (id:{excursion_exists.id}).\n\n'
                                    'Пожалуйста, ведите другое название')
            else:
                excursion = await db_manager.get_excursion_by_id(exc_id)
                success = await db_manager.update_excursion_data(
                    exc_id=exc_id,
                    name=new_name
                    )

                if success:
                    updated_exc = await db_manager.get_excursion_by_id(exc_id)
                    logger.info(f"Название экскурсии {exc_id} обновлено на '{new_name}'")

                    await message.answer(
                    "Название обновено!\n\n"
                    "Актуальные данные экскурсии:\n"
                    f" - Название: {updated_exc.name}\n"
                    f' - Описание:\n"{updated_exc.description}"\n'
                    f" - Длительность в минутах: {updated_exc.base_duration_minutes} минут\n"
                    f" - Стоимость: {updated_exc.base_price} рублей\n"
                    f" - Скидка для детей: {updated_exc.child_discount}%\n"
                    f" - Статус: {'Активна' if updated_exc.is_active else 'Не активна'}\n",
                    reply_markup=inline_end_add_exc(exc_id)
                    )
                else:
                    logger.warning(f"Не удалось обновить название экскурсии {exc_id}")
                    await message.answer("Ошибка обновления",
                                        reply_markup=inline_end_add_exc(exc_id))

                await state.clear()
                logger.debug(f"Состояние очищено для администратора {message.from_user.id}")

    except ValueError as e:
        logger.error(f"Ошибка валидации при редактировании названия: {e}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании названия: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data.startswith('redact_exc_description:'))
async def redact_description_one(callback:CallbackQuery, state:FSMContext):
    """Начало редактирования описания"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование описания экскурсии {exc_id}")

    await callback.answer('Редактируем описание')

    try:
        await state.update_data(excursion_id=exc_id)
        await state.set_state(RedactExcursion.description)
        await callback.message.answer('Введите новое описание')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние редактирования описания")
    except Exception as e:
        logger.error(f"Ошибка начала редактирования описания: {e}", exc_info=True)

@router.message(RedactExcursion.description)
async def redact_description_two(message: Message, state: FSMContext):
    """Завершение редактирования описания"""
    logger.info(f"Администратор {message.from_user.id} ввел новое описание (длина: {len(message.text)} символов)")

    try:
        new_description = message.text
        data = await state.get_data()
        exc_id = data.get('excursion_id')

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_excursion_data(
                exc_id=exc_id,
                description=new_description
                )

            if success:
                updated_exc = await db_manager.get_excursion_by_id(exc_id)
                logger.info(f"Описание экскурсии {exc_id} обновлено")

                await message.answer(
                "Описание обновено!\n\n"
                "Актуальные данные экскурсии:\n"
                f" - Название: {updated_exc.name}\n"
                f' - Описание:\n"{updated_exc.description}"\n'
                f" - Длительность в минутах: {updated_exc.base_duration_minutes} минут\n"
                f" - Стоимость: {updated_exc.base_price} рублей\n"
                f" - Скидка для детей: {updated_exc.child_discount}%\n"
                f" - Статус: {'Активна' if updated_exc.is_active else 'Не активна'}\n",
                reply_markup=inline_end_add_exc(exc_id)
                )
            else:
                logger.warning(f"Не удалось обновить описание экскурсии {exc_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=inline_end_add_exc(exc_id))

        await state.clear()
        logger.debug(f"Состояние очищено для администратора {message.from_user.id}")

    except ValueError as e:
        logger.error(f"Ошибка валидации при редактировании описания: {e}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании описания: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data.startswith('redact_exc_duration:'))
async def redact_duration_one(callback:CallbackQuery, state:FSMContext):
    """Начало редактирования продолжительности"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование продолжительности экскурсии {exc_id}")

    await callback.answer('Редактируем продолжительность')

    try:
        await state.update_data(excursion_id=exc_id)
        await state.set_state(RedactExcursion.base_duration_minutes)
        await callback.message.answer('Введите новую продолжительность')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние редактирования продолжительности")
    except Exception as e:
        logger.error(f"Ошибка начала редактирования продолжительности: {e}", exc_info=True)

@router.message(RedactExcursion.base_duration_minutes)
async def redact_duration_two(message: Message, state: FSMContext):
    """Завершение редактирования продолжительности"""
    logger.info(f"Администратор {message.from_user.id} ввел новую продолжительность: '{message.text}'")

    try:
        new_duration = Validators.validate_excursion_duration(message.text)
        logger.debug(f"Новая продолжительность валидирована: {new_duration} минут")

        data = await state.get_data()
        exc_id = data.get('excursion_id')

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_excursion_data(
                exc_id=exc_id,
                base_duration_minutes=new_duration
                )

            if success:
                updated_exc = await db_manager.get_excursion_by_id(exc_id)
                logger.info(f"Продолжительность экскурсии {exc_id} обновлена на {new_duration} минут")

                await message.answer(
                "Продолжительность обновена!\n\n"
                "Актуальные данные экскурсии:\n"
                f" - Название: {updated_exc.name}\n"
                f' - Описание:\n"{updated_exc.description}"\n'
                f" - Длительность в минутах: {updated_exc.base_duration_minutes} минут\n"
                f" - Стоимость: {updated_exc.base_price} рублей\n"
                f" - Скидка для детей: {updated_exc.child_discount}%\n"
                f" - Статус: {'Активна' if updated_exc.is_active else 'Не активна'}\n",
                reply_markup=inline_end_add_exc(exc_id)
                )
            else:
                logger.warning(f"Не удалось обновить продолжительность экскурсии {exc_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=inline_end_add_exc(exc_id))

        await state.clear()
        logger.debug(f"Состояние очищено для администратора {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидная продолжительность от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании продолжительности: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data.startswith('redact_exc_price:'))
async def redact_price_one(callback:CallbackQuery, state:FSMContext):
    """Начало редактирования стоимости"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование стоимости экскурсии {exc_id}")

    await callback.answer('Редактируем стоимость')

    try:
        await state.update_data(excursion_id=exc_id)
        await state.set_state(RedactExcursion.base_price)
        await callback.message.answer('Введите новую стоимость')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние редактирования стоимости")
    except Exception as e:
        logger.error(f"Ошибка начала редактирования стоимости: {e}", exc_info=True)

@router.message(RedactExcursion.base_price)
async def redact_price_two(message: Message, state: FSMContext):
    """Завершение редактирования стоимости"""
    logger.info(f"Администратор {message.from_user.id} ввел новую стоимость: '{message.text}'")

    try:
        new_price = Validators.validate_amount_rub(message.text)
        logger.debug(f"Новая стоимость валидирована: {new_price} руб.")

        data = await state.get_data()
        exc_id = data.get('excursion_id')

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_excursion_data(
                exc_id=exc_id,
                base_price=new_price
                )

            if success:
                updated_exc = await db_manager.get_excursion_by_id(exc_id)
                logger.info(f"Стоимость экскурсии {exc_id} обновлена на {new_price} руб.")

                await message.answer(
                "Стоимость обновена!\n\n"
                "Актуальные данные экскурсии:\n"
                f" - Название: {updated_exc.name}\n"
                f' - Описание:\n"{updated_exc.description}"\n'
                f" - Длительность в минутах: {updated_exc.base_duration_minutes} минут\n"
                f" - Стоимость: {updated_exc.base_price} рублей\n"
                f" - Скидка для детей: {updated_exc.child_discount}%\n"
                f" - Статус: {'Активна' if updated_exc.is_active else 'Не активна'}\n",
                reply_markup=inline_end_add_exc(exc_id)
                )
            else:
                logger.warning(f"Не удалось обновить стоимость экскурсии {exc_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=inline_end_add_exc(exc_id))

        await state.clear()
        logger.debug(f"Состояние очищено для администраторa {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидная стоимость от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании стоимости: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

@router.callback_query(F.data.startswith('redact_exc_discount:'))
async def redact_discount_one(callback:CallbackQuery, state:FSMContext):
    """Начало редактирования скидки"""
    exc_id = int(callback.data.split(':')[1])
    logger.info(f"Администратор {callback.from_user.id} начал редактирование скидки экскурсии {exc_id}")

    await callback.answer('Редактируем скидку для детей')

    try:
        await state.update_data(excursion_id=exc_id)
        await state.set_state(RedactExcursion.child_discount)
        await callback.message.answer('Введите новую скидку')
        logger.debug(f"Администратор {callback.from_user.id} перешел в состояние редактирования скидки")
    except Exception as e:
        logger.error(f"Ошибка начала редактирования скидки: {e}", exc_info=True)

@router.message(RedactExcursion.child_discount)
async def redact_discount_two(message: Message, state: FSMContext):
    """Завершение редактирования скидки"""
    logger.info(f"Администратор {message.from_user.id} ввел новую скидку: '{message.text}'")

    try:
        new_discount = Validators.validate_discount(message.text)
        logger.debug(f"Новая скидка валидирована: {new_discount}%")

        data = await state.get_data()
        exc_id = data.get('excursion_id')

        async with async_session() as session:
            db_manager = DatabaseManager(session)
            success = await db_manager.update_excursion_data(
                exc_id=exc_id,
                child_discount=new_discount
                )

            if success:
                updated_exc = await db_manager.get_excursion_by_id(exc_id)
                logger.info(f"Скидка экскурсии {exc_id} обновлена на {new_discount}%")

                await message.answer(
                "Скидка обновлена!\n\n"
                "Актуальные данные экскурсии:\n"
                f" - Название: {updated_exc.name}\n"
                f' - Описание:\n"{updated_exc.description}"\n'
                f" - Длительность в минутах: {updated_exc.base_duration_minutes} минут\n"
                f" - Стоимость: {updated_exc.base_price} рублей\n"
                f" - Скидка для детей: {updated_exc.child_discount}%\n"
                f" - Статус: {'Активна' if updated_exc.is_active else 'Не активна'}\n",
                reply_markup=inline_end_add_exc(exc_id)
                )
            else:
                logger.warning(f"Не удалось обновить скидку экскурсии {exc_id}")
                await message.answer("Ошибка обновления",
                                    reply_markup=inline_end_add_exc(exc_id))

        await state.clear()
        logger.debug(f"Состояние очищено для администратора {message.from_user.id}")

    except ValueError as e:
        logger.warning(f"Невалидная скидка от администратора {message.from_user.id}: {message.text}")
        await message.answer(str(e))
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании скидки: {e}", exc_info=True)
        await message.answer("Произошла непредвиденная ошибка")
        await state.clear()

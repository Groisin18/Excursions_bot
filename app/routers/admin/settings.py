from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import DatabaseManager, FileManager, FileType
from app.database.models import UserRole, User, TelegramFile
from app.database.session import async_session

from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger
from app.admin_panel.states_adm import UploadConcent
import app.admin_panel.keyboards_adm as kb



logger = get_logger(__name__)


router = Router(name="admin_settings")
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

# ===== НАСТРОЙКИ =====

@router.message(F.text == "Управление администраторами")
async def manage_admins(message: Message):
    """Управление администраторами"""
    logger.info(f"Администратор {message.from_user.id} открыл управление администраторами")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)

            result = await session.execute(
                select(User).where(User.role == UserRole.admin)
            )
            admins = result.scalars().all()

            logger.info(f"Найдено администраторов: {len(admins)}")
            response = "Текущие администраторы:\n\n"
            for admin in admins:
                response += (
                    f"Имя: {admin.full_name}\n"
                    f"Телефон: {admin.phone_number}\n"
                    f"Telegram ID: {admin.telegram_id}\n"
                    f"---\n"
                )

            response += "\nДля назначения нового администратора или изменения статуса имеющихся используйте команду /promote"
            await message.answer(response)
            logger.debug(f"Список администраторов отправлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка получения списка администраторов: {e}", exc_info=True)
        await message.answer("Ошибка при получении списка администраторов")


@router.message(F.text == "Настройки базы данных")
async def settings_database(message: Message):
    """Настройки базы данных"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки базы данных")

    try:
        # Можно использовать существующую команду /optimize_db
        await message.answer(
            "Настройки базы данных:\n\n"
            "Доступные команды:\n"
            "/optimize_db - оптимизация базы данных\n"
            "/reset_db - сброс сессий БД (принудительно)\n"
            "/debug - отладка состояния БД"
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


# ===== МЕНЮ НАСТРОЕК ФАЙЛОВ =====

@router.message(F.text == "Файлы согласия на обработку ПД")
async def settings_concents(message: Message):
    """Настройки файлов согласия на обработку ПД"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки файлов согласия на обработку ПД")

    # Получаем информацию о текущих файлах
    async with async_session() as session:
        file_manager = FileManager(session)

        # Получаем все типы файлов
        adult_file = await file_manager.get_file_record(FileType.CPD)
        minor_file = await file_manager.get_file_record(FileType.CPD_MINOR)

        # Считаем все файлы в базе
        all_files = await file_manager.get_all_file_records()
        other_files_count = len([f for f in all_files if f.file_type == FileType.OTHER])

        adult_info = f"Есть ({adult_file.file_name})" if adult_file else "Нет"
        minor_info = f"Есть ({minor_file.file_name})" if minor_file else "Нет"

        text = (
            "Управление файлами в базе данных\n\n"
            "Текущие файлы согласия:\n"
            f"• Согласие для взрослых: {adult_info}\n"
            f"• Согласие для несовершеннолетних: {minor_info}\n\n"
            f"Прочих файлов в базе: {other_files_count}\n\n"
            "Выберите действие:"
        )

    await message.answer(text, reply_markup=kb.concent_files_menu())


@router.callback_query(F.data == "concent_view_all_files")
async def concent_view_all_files(callback: CallbackQuery):
    """Просмотр всех файлов в базе"""
    await callback.answer()

    async with async_session() as session:
        file_manager = FileManager(session)
        all_files = await file_manager.get_all_file_records()

        if not all_files:
            text = "В базе данных нет файлов."
            await callback.message.edit_text(text, reply_markup=kb.concent_back_menu())
            return

        # Группируем по типам
        files_by_type = {}
        for file in all_files:
            if file.file_type not in files_by_type:
                files_by_type[file.file_type] = []
            files_by_type[file.file_type].append(file)

        text = "Все файлы в базе данных:\n\n"

        for file_type, files in files_by_type.items():
            type_name = {
                FileType.CPD: "Согласие для взрослых",
                FileType.CPD_MINOR: "Согласие для несовершеннолетних",
                FileType.OTHER: "Прочие файлы"
            }.get(file_type, str(file_type.value))

            text += f"=== {type_name} ===\n"

            for i, file in enumerate(files, 1):
                upload_date = file.uploaded_at.strftime("%d.%m.%Y %H:%M") if file.uploaded_at else "неизвестно"
                text += (
                    f"{i}. {file.file_name}\n"
                    f"   Размер: {file.file_size} байт\n"
                    f"   Загружен: {upload_date}\n"
                    f"   File ID: {file.file_telegram_id[:30]}...\n"
                )

            text += "\n"

        text += f"Всего файлов: {len(all_files)}"

        # Если сообщение слишком длинное, разбиваем на части
        if len(text) > 4000:
            parts = []
            current_part = ""
            lines = text.split('\n')

            for line in lines:
                if len(current_part) + len(line) + 1 > 4000:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'

            if current_part:
                parts.append(current_part)

            for i, part in enumerate(parts, 1):
                if i == 1:
                    await callback.message.edit_text(part, reply_markup=kb.concent_back_menu())
                else:
                    await callback.message.answer(part)
        else:
            await callback.message.edit_text(text, reply_markup=kb.concent_back_menu())


@router.callback_query(F.data == "concent_view_files")
async def concent_view_files(callback: CallbackQuery):
    """Меню выбора файла для просмотра"""
    await callback.answer()

    async with async_session() as session:
        file_manager = FileManager(session)

        # Получаем информацию о файлах
        adult_file = await file_manager.get_file_record(FileType.CPD)
        minor_file = await file_manager.get_file_record(FileType.CPD_MINOR)
        all_files = await file_manager.get_all_file_records()
        other_files_count = len([f for f in all_files if f.file_type == FileType.OTHER])

        # Формируем текст
        text = "Выберите файл для просмотра:\n\n"

        if adult_file:
            adult_date = adult_file.uploaded_at.strftime("%d.%m.%Y") if adult_file.uploaded_at else "неизвестно"
            text += f"• Согласие для взрослых: {adult_file.file_name} ({adult_date})\n"
        else:
            text += "• Согласие для взрослых: не загружено\n"

        if minor_file:
            minor_date = minor_file.uploaded_at.strftime("%d.%m.%Y") if minor_file.uploaded_at else "неизвестно"
            text += f"• Согласие для несовершеннолетних: {minor_file.file_name} ({minor_date})\n"
        else:
            text += "• Согласие для несовершеннолетних: не загружено\n"

        if other_files_count > 0:
            text += f"• Других файлов: {other_files_count}\n"

        # Используем новую функцию для клавиатуры
        keyboard = kb.concent_file_selection_menu(
            adult_file=adult_file,
            minor_file=minor_file,
            other_files_count=other_files_count
        )

        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("concent_send_"))
async def concent_send_file(callback: CallbackQuery):
    """Отправка файла по типу"""
    await callback.answer()

    file_type_value = callback.data.replace("concent_send_", "")

    try:
        file_type = FileType(file_type_value)
    except ValueError:
        await callback.message.answer(f"Неизвестный тип файла: {file_type_value}")
        return

    async with async_session() as session:
        file_manager = FileManager(session)
        file_record = await file_manager.get_file_record(file_type)

        if not file_record:
            await callback.message.answer(f"Файл типа {file_type.value} не найден в базе данных.")
            return

        try:
            # Отправляем файл
            await callback.message.answer_document(
                document=file_record.file_telegram_id,
                caption=f"{file_record.file_name}\nЗагружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}"
            )

            # Показываем информацию о файле
            info_text = (
                f"Файл отправлен:\n\n"
                f"Тип: {file_type.value}\n"
                f"Название: {file_record.file_name}\n"
                f"Размер: {file_record.file_size} байт\n"
                f"Загружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}\n"
                f"File ID: {file_record.file_telegram_id[:50]}..."
            )

            await callback.message.answer(info_text, reply_markup=kb.concent_back_menu())

        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}", exc_info=True)
            await callback.message.answer(
                f"Ошибка при отправке файла. Возможно, file_id устарел.\n"
                f"Попробуйте загрузить файл заново.",
                reply_markup=kb.concent_back_menu()
            )


@router.callback_query(F.data == "concent_view_other_files")
async def concent_view_other_files(callback: CallbackQuery):
    """Просмотр других файлов"""
    await callback.answer()

    async with async_session() as session:
        file_manager = FileManager(session)
        all_files = await file_manager.get_all_file_records()
        other_files = [f for f in all_files if f.file_type == FileType.OTHER]

        if not other_files:
            await callback.message.answer("Нет других файлов в базе данных.", reply_markup=kb.concent_back_menu())
            return

        # Создаем клавиатуру с другими файлами
        builder = InlineKeyboardBuilder()

        for file in other_files:
            short_name = file.file_name[:30] + "..." if len(file.file_name) > 30 else file.file_name
            upload_date = file.uploaded_at.strftime("%d.%m.%Y") if file.uploaded_at else "??"
            builder.button(
                text=f"{short_name} ({upload_date})",
                callback_data=f"concent_send_other_{file.id}"
            )

        builder.button(text="Назад", callback_data="concent_view_files")
        builder.adjust(1)

        text = f"Другие файлы ({len(other_files)}):\n\n"

        for i, file in enumerate(other_files, 1):
            upload_date = file.uploaded_at.strftime("%d.%m.%Y %H:%M") if file.uploaded_at else "неизвестно"
            text += f"{i}. {file.file_name}\n   Загружен: {upload_date}\n   Размер: {file.file_size} байт\n\n"

        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("concent_send_other_"))
async def concent_send_other_file(callback: CallbackQuery):
    """Отправка конкретного другого файла по ID"""
    await callback.answer()

    try:
        file_id = int(callback.data.replace("concent_send_other_", ""))
    except ValueError:
        await callback.message.answer("Ошибка: некорректный ID файла.")
        return

    async with async_session() as session:
        file_manager = FileManager(session)

        # Находим файл по ID
        stmt = select(TelegramFile).where(TelegramFile.id == file_id, TelegramFile.file_type == FileType.OTHER)
        result = await session.execute(stmt)
        file_record = result.scalar_one_or_none()

        if not file_record:
            await callback.message.answer("Файл не найден в базе данных.")
            return

        try:
            # Отправляем файл
            await callback.message.answer_document(
                document=file_record.file_telegram_id,
                caption=f"{file_record.file_name}\nЗагружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}"
            )

            # Показываем информацию
            info_text = (
                f"Файл отправлен:\n\n"
                f"Название: {file_record.file_name}\n"
                f"Размер: {file_record.file_size} байт\n"
                f"Загружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}\n"
                f"File ID: {file_record.file_telegram_id[:50]}..."
            )

            await callback.message.answer(info_text, reply_markup=kb.concent_back_menu())

        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}", exc_info=True)
            await callback.message.answer(
                f"Ошибка при отправке файла: {e}",
                reply_markup=kb.concent_back_menu()
            )


@router.callback_query(F.data.in_(["concent_no_file_adult", "concent_no_file_minor"]))
async def concent_no_file(callback: CallbackQuery):
    """Обработчик для отсутствующих файлов"""
    await callback.answer()

    file_type = "для взрослых" if callback.data == "concent_no_file_adult" else "для несовершеннолетних"

    await callback.message.answer(
        f"Файл согласия {file_type} не загружен.\n"
        f"Используйте меню 'Загрузить/заменить файл' для добавления.",
        reply_markup=kb.concent_back_menu()
    )

@router.callback_query(F.data == "concent_upload_menu")
async def concent_upload_menu_callback(callback: CallbackQuery):
    """Меню загрузки файлов"""
    await callback.answer()

    text = (
        "Выберите тип файла для загрузки:\n\n"
        "При загрузке нового файла старый будет заменен автоматически.\n"
        "Отправьте файл после выбора типа."
    )

    await callback.message.edit_text(text, reply_markup=kb.concent_upload_menu())

@router.callback_query(F.data.in_(["concent_upload_adult", "concent_upload_minor", "concent_upload_other"]))
async def start_concent_upload(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки файла"""
    await callback.answer()

    # Определяем тип файла
    if callback.data == "concent_upload_adult":
        file_type = FileType.CPD
        file_type_name = "Согласие для взрослых"
    elif callback.data == "concent_upload_minor":
        file_type = FileType.CPD_MINOR
        file_type_name = "Согласие для несовершеннолетних"
    else:  # concent_upload_other
        file_type = FileType.OTHER
        file_type_name = "Прочий файл"

    await state.update_data(file_type=file_type, file_type_name=file_type_name)
    await state.set_state(UploadConcent.waiting_for_file)

    text = (
        f"Отправьте файл для типа: {file_type_name}\n\n"
        "Требования:\n"
        "• Можно загружать любые файлы\n"
        "• Для согласий рекомендуется PDF\n"
        "• Максимальный размер: 50 MB\n"
        "• Старый файл этого типа будет заменен"
    )

    await callback.message.edit_text(text, reply_markup=kb.concent_back_menu())


@router.message(UploadConcent.waiting_for_file, F.document)
async def process_concent_upload(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    data = await state.get_data()
    file_type = data.get('file_type')
    file_type_name = data.get('file_type_name', 'Файл')

    document = message.document

    # Проверяем размер
    if document.file_size > 50 * 1024 * 1024:  # 50 MB
        await message.answer(
            f"Ошибка: файл слишком большой (максимум 50 MB).\n"
            f"Текущий размер: {document.file_size / (1024*1024):.1f} MB.\n"
            f"Попробуйте еще раз или нажмите 'Назад'.",
            reply_markup=kb.concent_back_menu()
        )
        return

    try:
        async with async_session() as session:
            file_manager = FileManager(session)

            # Проверяем, есть ли старый файл
            old_file = await file_manager.get_file_record(file_type)

            # Сохраняем файл в базу
            await file_manager.save_file_id(
                file_type=file_type,
                file_telegram_id=document.file_id,
                file_name=document.file_name,
                file_size=document.file_size,
                uploaded_by=message.from_user.id
            )

            logger.info(f"Администратор {message.from_user.id} загрузил файл {file_type.value}: {document.file_name}")

            # Формируем ответ
            response = (
                f"Файл успешно загружен!\n\n"
                f"Тип: {file_type_name}\n"
                f"Название: {document.file_name}\n"
                f"Размер: {document.file_size} байт\n"
                f"MIME тип: {document.mime_type or 'не указан'}\n"
                f"File ID: {document.file_id[:50]}..."
            )

            if old_file:
                old_date = old_file.uploaded_at.strftime("%d.%m.%Y %H:%M") if old_file.uploaded_at else "неизвестно"
                response += (
                    f"\n\nСтарый файл заменен:\n"
                    f"• Название: {old_file.file_name}\n"
                    f"• Размер: {old_file.file_size} байт\n"
                    f"• Загружен: {old_date}"
                )

            await message.answer(response, reply_markup=kb.concent_back_menu())

    except Exception as e:
        logger.error(f"Ошибка при сохранении файла: {e}", exc_info=True)
        await message.answer(
            f"Ошибка при сохранении файла: {e}\n"
            f"Попробуйте еще раз или обратитесь к разработчику.",
            reply_markup=kb.concent_back_menu()
        )

    finally:
        await state.clear()


@router.message(UploadConcent.waiting_for_file)
async def process_wrong_file_type(message: Message, state: FSMContext):
    """Обработка некорректного типа сообщения"""
    data = await state.get_data()
    file_type_name = data.get('file_type_name', 'Файл')

    await message.answer(
        f"Пожалуйста, отправьте файл как документ (не фото/видео).\n"
        f"Вы загружаете: {file_type_name}\n\n"
        f"Отправьте файл или нажмите 'Назад'.",
        reply_markup=kb.concent_back_menu()
    )


@router.callback_query(F.data == "concent_files")
async def concent_files_callback(callback: CallbackQuery):
    """Обработчик возврата в меню файлов"""
    await callback.answer()

    async with async_session() as session:
        file_manager = FileManager(session)

        adult_file = await file_manager.get_file_record(FileType.CPD)
        minor_file = await file_manager.get_file_record(FileType.CPD_MINOR)
        all_files = await file_manager.get_all_file_records()
        other_files_count = len([f for f in all_files if f.file_type == FileType.OTHER])

        adult_info = f"Есть ({adult_file.file_name})" if adult_file else "Нет"
        minor_info = f"Есть ({minor_file.file_name})" if minor_file else "Нет"

        text = (
            "Управление файлами в базе данных\n\n"
            "Текущие файлы согласия:\n"
            f"• Согласие для взрослых: {adult_info}\n"
            f"• Согласие для несовершеннолетних: {minor_info}\n\n"
            f"Прочих файлов в базе: {other_files_count}\n\n"
            "Выберите действие:"
        )

    await callback.message.edit_text(text, reply_markup=kb.concent_files_menu())


@router.callback_query(F.data == "admin_settings")
async def settings_main_callback(callback: CallbackQuery):
    """Переход в настройки"""
    logger.info(f"Администратор {callback.message.from_user.id} вернулся в меню настроек")

    try:
        await callback.message.answer(
            "Настройки системы:",
            reply_markup=kb.settings_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия настроек: {e}", exc_info=True)
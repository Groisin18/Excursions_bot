from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.unit_of_work import UnitOfWork
from app.database.repositories import (
    UserRepository, FileRepository, SettingsRepository
)
from app.database.models import UserRole, FileType
from app.database.session import async_session

from app.admin_panel.states_adm import UploadConcent
from app.middlewares import AdminMiddleware
from app.utils.logging_config import get_logger

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
            user_repo = UserRepository(session)

            admins = await user_repo.get_users_by_role(UserRole.admin)

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
        await message.answer("Ошибка при получении списка администраторов", reply_markup=kb.settings_submenu())


# ===== МЕНЮ НАСТРОЕК ФАЙЛОВ =====

@router.message(F.text == "Файлы согласия на обработку ПД")
async def settings_concents(message: Message):
    """Настройки файлов согласия на обработку ПД"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки файлов согласия на обработку ПД")

    try:
        async with async_session() as session:
            file_repo = FileRepository(session)

            adult_file = await file_repo.get_file_record(FileType.CPD)
            minor_file = await file_repo.get_file_record(FileType.CPD_MINOR)

            all_files = await file_repo.get_all_file_records()
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

    except Exception as e:
        logger.error(f"Ошибка получения информации о файлах согласия: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении информации о файлах", reply_markup=kb.settings_submenu())

@router.callback_query(F.data == "concent_view_all_files")
async def concent_view_all_files(callback: CallbackQuery):
    """Просмотр всех файлов в базе"""
    logger.info(f"Администратор {callback.from_user.id} запросил просмотр всех файлов")
    await callback.answer()

    try:
        async with async_session() as session:
            file_repo = FileRepository(session)
            all_files = await file_repo.get_all_file_records()

            if not all_files:
                text = "В базе данных нет файлов."
                await callback.message.edit_text(text, reply_markup=kb.concent_back_menu())
                return

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

    except Exception as e:
        logger.error(f"Ошибка при просмотре всех файлов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке списка файлов", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data == "concent_view_files")
async def concent_view_files(callback: CallbackQuery):
    """Меню выбора файла для просмотра"""
    logger.info(f"Администратор {callback.from_user.id} открыл меню выбора файла для просмотра")
    await callback.answer()

    try:
        async with async_session() as session:
            file_repo = FileRepository(session)

            adult_file = await file_repo.get_file_record(FileType.CPD)
            minor_file = await file_repo.get_file_record(FileType.CPD_MINOR)
            all_files = await file_repo.get_all_file_records()
            other_files_count = len([f for f in all_files if f.file_type == FileType.OTHER])

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

            keyboard = kb.concent_file_selection_menu(
                adult_file=adult_file,
                minor_file=minor_file,
                other_files_count=other_files_count
            )

            await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при загрузке меню выбора файла: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке меню", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data.startswith("concent_send_"))
async def concent_send_file(callback: CallbackQuery):
    """Отправка файла по типу"""
    logger.info(f"Администратор {callback.from_user.id} запросил отправку файла")
    await callback.answer()

    try:
        file_type_value = callback.data.replace("concent_send_", "")

        try:
            file_type = FileType(file_type_value)
        except ValueError:
            await callback.message.answer(f"Неизвестный тип файла: {file_type_value}", reply_markup=kb.concent_back_menu())
            return

        async with async_session() as session:
            file_repo = FileRepository(session)
            file_record = await file_repo.get_file_record(file_type)

            if not file_record:
                await callback.message.answer(f"Файл типа {file_type.value} не найден в базе данных.", reply_markup=kb.concent_back_menu())
                return

            try:
                await callback.message.answer_document(
                    document=file_record.file_telegram_id,
                    caption=f"{file_record.file_name}\nЗагружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}"
                )

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

    except Exception as e:
        logger.error(f"Ошибка в обработчике отправки файла: {e}", exc_info=True)
        await callback.message.answer("Произошла непредвиденная ошибка", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data == "concent_view_other_files")
async def concent_view_other_files(callback: CallbackQuery):
    """Просмотр других файлов"""
    logger.info(f"Администратор {callback.from_user.id} запросил просмотр других файлов")
    await callback.answer()

    try:
        async with async_session() as session:
            file_repo = FileRepository(session)
            all_files = await file_repo.get_all_file_records()
            other_files = [f for f in all_files if f.file_type == FileType.OTHER]

            if not other_files:
                await callback.message.answer("Нет других файлов в базе данных.", reply_markup=kb.concent_back_menu())
                return

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

    except Exception as e:
        logger.error(f"Ошибка при просмотре других файлов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке списка файлов", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data.startswith("concent_send_other_"))
async def concent_send_other_file(callback: CallbackQuery):
    """Отправка конкретного другого файла по ID"""
    logger.info(f"Администратор {callback.from_user.id} запросил отправку другого файла")
    await callback.answer()

    try:
        try:
            file_id = int(callback.data.replace("concent_send_other_", ""))
        except ValueError:
            await callback.message.answer("Ошибка: некорректный ID файла.", reply_markup=kb.concent_back_menu())
            return

        async with async_session() as session:
            file_repo = FileRepository(session)

            file_record = await file_repo.get_by_id_and_type(file_id, FileType.OTHER)

            if not file_record:
                await callback.message.answer("Файл не найден в базе данных.", reply_markup=kb.concent_back_menu())
                return

            try:
                await callback.message.answer_document(
                    document=file_record.file_telegram_id,
                    caption=f"{file_record.file_name}\nЗагружен: {file_record.uploaded_at.strftime('%d.%m.%Y %H:%M') if file_record.uploaded_at else 'неизвестно'}"
                )

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

    except Exception as e:
        logger.error(f"Ошибка в обработчике отправки другого файла: {e}", exc_info=True)
        await callback.message.answer("Произошла непредвиденная ошибка", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data.in_(["concent_no_file_adult", "concent_no_file_minor"]))
async def concent_no_file(callback: CallbackQuery):
    """Обработчик для отсутствующих файлов"""
    await callback.answer()

    try:
        file_type = "для взрослых" if callback.data == "concent_no_file_adult" else "для несовершеннолетних"

        await callback.message.answer(
            f"Файл согласия {file_type} не загружен.\n"
            f"Используйте меню 'Загрузить/заменить файл' для добавления.",
            reply_markup=kb.concent_back_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке отсутствующего файла: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data == "concent_upload_menu")
async def concent_upload_menu_callback(callback: CallbackQuery):
    """Меню загрузки файлов"""
    logger.info(f"Администратор {callback.from_user.id} открыл меню загрузки файлов")
    await callback.answer()

    try:
        text = (
            "Выберите тип файла для загрузки:\n\n"
            "При загрузке нового файла старый будет заменен автоматически.\n"
            "Отправьте файл после выбора типа."
        )

        await callback.message.edit_text(text, reply_markup=kb.concent_upload_menu())

    except Exception as e:
        logger.error(f"Ошибка при открытии меню загрузки файлов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при открытии меню", reply_markup=kb.concent_back_menu())

@router.callback_query(F.data.in_(["concent_upload_adult", "concent_upload_minor", "concent_upload_other"]))
async def start_concent_upload(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки файла"""
    logger.info(f"Администратор {callback.from_user.id} начал загрузку файла")
    await callback.answer()

    try:
        if callback.data == "concent_upload_adult":
            file_type = FileType.CPD
            file_type_name = "Согласие для взрослых"
        elif callback.data == "concent_upload_minor":
            file_type = FileType.CPD_MINOR
            file_type_name = "Согласие для несовершеннолетних"
        else:
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

    except Exception as e:
        logger.error(f"Ошибка при начале загрузки файла: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при начале загрузки файла", reply_markup=kb.concent_back_menu())
        await state.clear()

@router.message(UploadConcent.waiting_for_file, F.document)
async def process_concent_upload(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    logger.info(f"Администратор {message.from_user.id} загружает файл")

    try:
        data = await state.get_data()
        file_type = data.get('file_type')
        file_type_name = data.get('file_type_name', 'Файл')

        document = message.document

        if document.file_size > 50 * 1024 * 1024:
            await message.answer(
                f"Ошибка: файл слишком большой (максимум 50 MB).\n"
                f"Текущий размер: {document.file_size / (1024*1024):.1f} MB.\n"
                f"Попробуйте еще раз или нажмите 'Назад'.",
                reply_markup=kb.concent_back_menu()
            )
            return

        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                file_repo = FileRepository(uow.session)

                old_file = await file_repo.get_file_record(file_type)

                await file_repo.save_file_id(
                    file_type=file_type,
                    file_telegram_id=document.file_id,
                    file_name=document.file_name,
                    file_size=document.file_size,
                    uploaded_by=message.from_user.id
                )

                logger.info(f"Администратор {message.from_user.id} загрузил файл {file_type.value}: {document.file_name}")

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
            f"Ошибка при сохранении файла. Попробуйте еще раз.",
            reply_markup=kb.concent_back_menu()
        )
    finally:
        await state.clear()

@router.message(UploadConcent.waiting_for_file)
async def process_wrong_file_type(message: Message, state: FSMContext):
    """Обработка некорректного типа сообщения"""
    logger.warning(f"Администратор {message.from_user.id} отправил не документ во время загрузки файла")

    try:
        data = await state.get_data()
        file_type_name = data.get('file_type_name', 'Файл')

        await message.answer(
            f"Пожалуйста, отправьте файл как документ (не фото/видео).\n"
            f"Вы загружаете: {file_type_name}\n\n"
            f"Отправьте файл или нажмите 'Назад'.",
            reply_markup=kb.concent_back_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке некорректного типа файла: {e}", exc_info=True)
        await message.answer("Произошла ошибка", reply_markup=kb.concent_back_menu())
        await state.clear()

@router.callback_query(F.data == "concent_files")
async def concent_files_callback(callback: CallbackQuery):
    """Обработчик возврата в меню файлов"""
    logger.info(f"Администратор {callback.from_user.id} вернулся в меню файлов")
    await callback.answer()

    try:
        async with async_session() as session:
            file_repo = FileRepository(session)

            adult_file = await file_repo.get_file_record(FileType.CPD)
            minor_file = await file_repo.get_file_record(FileType.CPD_MINOR)
            all_files = await file_repo.get_all_file_records()
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

    except Exception as e:
        logger.error(f"Ошибка при возврате в меню файлов: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при загрузке меню", reply_markup=kb.settings_submenu())

@router.callback_query(F.data == "admin_settings")
async def settings_main_callback(callback: CallbackQuery):
    """Переход в настройки"""
    logger.info(f"Администратор {callback.from_user.id} вернулся в меню настроек")
    await callback.answer()

    try:
        await callback.message.answer(
            "Настройки системы:",
            reply_markup=kb.settings_submenu()
        )
    except Exception as e:
        logger.error(f"Ошибка открытия настроек: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при открытии настроек",
            reply_markup=kb.settings_submenu()
        )


# ===== НАСТРОЙКИ ОТПРАВКИ ЧЕКОВ И СИСТЕМЫ НАЛОГООБЛОЖЕНИЯ =====

# ===== НАСТРОЙКИ ЧЕКОВ 54-ФЗ =====

# Ключи настроек
SETTING_SEND_RECEIPT = "send_receipt"
SETTING_VAT_RATE = "vat_rate"
SETTING_TAX_SYSTEM = "tax_system_code"

# Значения по умолчанию
DEFAULT_SEND_RECEIPT = "false"
DEFAULT_VAT_RATE = "0"
DEFAULT_TAX_SYSTEM = "1"


async def _get_receipt_settings(session) -> tuple:
    """Получить текущие настройки чеков"""
    settings_repo = SettingsRepository(session)

    send_receipt = await settings_repo.get_bool(
        SETTING_SEND_RECEIPT,
        default=False
    )
    vat_rate = await settings_repo.get_int(
        SETTING_VAT_RATE,
        default=0
    )
    tax_system = await settings_repo.get_int(
        SETTING_TAX_SYSTEM,
        default=1
    )

    return send_receipt, vat_rate, tax_system

@router.message(F.text == "Настройки чеков 54-ФЗ")
async def receipt_settings_menu(message: Message):
    """Меню настроек чеков 54-ФЗ"""
    logger.info(f"Администратор {message.from_user.id} открыл настройки чеков")

    try:
        async with async_session() as session:
            send_receipt, vat_rate, tax_system = await _get_receipt_settings(session)

            text = (
                "Настройки чеков по 54-ФЗ\n\n"
                "Здесь можно настроить параметры отправки чеков через YooKassa.\n\n"
                "Доступные опции:\n"
                "• Отправка чеков - включить/выключить\n"
                "• Ставка НДС - выбор ставки для экскурсионных услуг\n"
                "• Система налогообложения - выбор режима для чека\n\n"
                "Текущие настройки:"
            )

            await message.answer(
                text,
                reply_markup=kb.receipt_settings_menu(send_receipt, vat_rate, tax_system)
            )

    except Exception as e:
        logger.error(f"Ошибка открытия настроек чеков: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при открытии настроек",
            reply_markup=kb.settings_submenu()
        )

@router.callback_query(F.data == "receipt_settings")
async def receipt_settings_callback(callback: CallbackQuery):
    """Возврат в меню настроек чеков"""
    logger.info(f"Администратор {callback.from_user.id} вернулся в настройки чеков")
    await callback.answer()

    try:
        async with async_session() as session:
            send_receipt, vat_rate, tax_system = await _get_receipt_settings(session)

            await callback.message.edit_text(
                "Настройки чеков по 54-ФЗ\n\n"
                "Доступные опции:\n"
                "• Отправка чеков - включить/выключить\n"
                "• Ставка НДС - выбор ставки для экскурсионных услуг\n"
                "• Система налогообложения - выбор режима для чека\n\n"
                "Текущие настройки:",
                reply_markup=kb.receipt_settings_menu(send_receipt, vat_rate, tax_system)
            )

    except Exception as e:
        logger.error(f"Ошибка возврата в настройки чеков: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка",
            reply_markup=kb.settings_submenu()
        )

@router.callback_query(F.data == "receipt_toggle_send")
async def receipt_toggle_send(callback: CallbackQuery):
    """Переключение отправки чеков"""
    logger.info(f"Администратор {callback.from_user.id} переключает отправку чеков")
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                settings_repo = SettingsRepository(uow.session)
                user_repo = UserRepository(uow.session)
                user = await user_repo.get_by_telegram_id(callback.from_user.id)
                admin_user_id = user.id

                current = await settings_repo.get_bool(SETTING_SEND_RECEIPT, default=False)
                new_value = "false" if current else "true"

                await settings_repo.set(
                    key=SETTING_SEND_RECEIPT,
                    value=new_value,
                    description="Включение/выключение отправки чеков по 54-ФЗ",
                    updated_by=admin_user_id
                )

                logger.info(f"Отправка чеков изменена: {current} -> {not current}")

                send_receipt, vat_rate, tax_system = await _get_receipt_settings(session)

                await callback.message.edit_text(
                    "Настройки чеков по 54-ФЗ\n\n"
                    "Доступные опции:\n"
                    "• Отправка чеков - включить/выключить\n"
                    "• Ставка НДС - выбор ставки для экскурсионных услуг\n"
                    "• Система налогообложения - выбор режима для чека\n\n"
                    "Текущие настройки:",
                    reply_markup=kb.receipt_settings_menu(send_receipt, vat_rate, tax_system)
                )

    except Exception as e:
        logger.error(f"Ошибка переключения отправки чеков: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при изменении настройки")

@router.callback_query(F.data == "receipt_set_vat")
async def receipt_set_vat_menu(callback: CallbackQuery):
    """Меню выбора ставки НДС"""
    logger.info(f"Администратор {callback.from_user.id} открыл выбор ставки НДС")
    await callback.answer()

    try:
        async with async_session() as session:
            settings_repo = SettingsRepository(session)
            current_rate = await settings_repo.get_int(SETTING_VAT_RATE, default=0)

            text = (
                "Выберите ставку НДС для экскурсионных услуг:\n\n"
                "• 0% - без НДС (освобождение, упрощенка)\n"
                "• 5% - пониженная ставка (УСН)\n"
                "• 7% - пониженная ставка (УСН)\n"
                "• 10% - льготная ставка\n"
                "• 22% - основная ставка с 2026 года\n\n"
                f"Текущая ставка: {current_rate}%"
            )

            await callback.message.edit_text(
                text,
                reply_markup=kb.vat_rate_selection_menu(current_rate)
            )

    except Exception as e:
        logger.error(f"Ошибка открытия выбора ставки НДС: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data.startswith("receipt_set_vat_"))
async def receipt_set_vat_value(callback: CallbackQuery):
    """Установка ставки НДС"""
    vat_rate = int(callback.data.split("_")[-1])
    logger.info(f"Администратор {callback.from_user.id} установил ставку НДС: {vat_rate}%")
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                settings_repo = SettingsRepository(uow.session)
                user_repo = UserRepository(uow.session)
                user = await user_repo.get_by_telegram_id(callback.from_user.id)
                admin_user_id = user.id

                await settings_repo.set(
                    key=SETTING_VAT_RATE,
                    value=str(vat_rate),
                    description="Ставка НДС для чеков",
                    updated_by=admin_user_id
                )

                send_receipt, _, tax_system = await _get_receipt_settings(session)

                await callback.message.edit_text(
                    "Настройки чеков по 54-ФЗ\n\n"
                    "Доступные опции:\n"
                    "• Отправка чеков - включить/выключить\n"
                    "• Ставка НДС - выбор ставки для экскурсионных услуг\n"
                    "• Система налогообложения - выбор режима для чека\n\n"
                    "Текущие настройки:",
                    reply_markup=kb.receipt_settings_menu(send_receipt, vat_rate, tax_system)
                )

    except Exception as e:
        logger.error(f"Ошибка установки ставки НДС: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при сохранении настройки")

@router.callback_query(F.data == "receipt_set_tax")
async def receipt_set_tax_menu(callback: CallbackQuery):
    """Меню выбора системы налогообложения"""
    logger.info(f"Администратор {callback.from_user.id} открыл выбор системы налогообложения")
    await callback.answer()

    try:
        async with async_session() as session:
            settings_repo = SettingsRepository(session)
            current_code = await settings_repo.get_int(SETTING_TAX_SYSTEM, default=1)

            text = (
                "Выберите систему налогообложения:\n\n"
                "1 - Общая система налогообложения (ОСН)\n"
                "2 - Упрощенная (УСН, доходы)\n"
                "3 - Упрощенная (УСН, доходы минус расходы)\n"
                "4 - Единый налог на вмененный доход (ЕНВД)\n"
                "5 - Единый сельскохозяйственный налог (ЕСН)\n"
                "6 - Патентная система налогообложения\n\n"
                f"Текущий режим: код {current_code}"
            )

            await callback.message.edit_text(
                text,
                reply_markup=kb.tax_system_selection_menu(current_code)
            )

    except Exception as e:
        logger.error(f"Ошибка открытия выбора системы налогообложения: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка")

@router.callback_query(F.data.startswith("receipt_set_tax_"))
async def receipt_set_tax_value(callback: CallbackQuery):
    """Установка системы налогообложения"""
    tax_code = int(callback.data.split("_")[-1])
    logger.info(f"Администратор {callback.from_user.id} установил систему налогообложения: {tax_code}")
    await callback.answer()

    try:
        async with async_session() as session:
            async with UnitOfWork(session) as uow:
                settings_repo = SettingsRepository(uow.session)
                user_repo = UserRepository(uow.session)
                user = await user_repo.get_by_telegram_id(callback.from_user.id)
                admin_user_id = user.id

                await settings_repo.set(
                    key=SETTING_TAX_SYSTEM,
                    value=str(tax_code),
                    description="Система налогообложения для чеков",
                    updated_by=admin_user_id
                )

                send_receipt, vat_rate, _ = await _get_receipt_settings(session)

                await callback.message.edit_text(
                    "Настройки чеков по 54-ФЗ\n\n"
                    "Доступные опции:\n"
                    "• Отправка чеков - включить/выключить\n"
                    "• Ставка НДС - выбор ставки для экскурсионных услуг\n"
                    "• Система налогообложения - выбор режима для чека\n\n"
                    "Текущие настройки:",
                    reply_markup=kb.receipt_settings_menu(send_receipt, vat_rate, tax_code)
                )

    except Exception as e:
        logger.error(f"Ошибка установки системы налогообложения: {e}", exc_info=True)
        await callback.message.answer("Произошла ошибка при сохранении настройки")

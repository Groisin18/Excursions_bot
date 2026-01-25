from app.database.requests import DatabaseManager
from app.database.models import async_session, UserRole
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def is_user_admin(telegram_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    logger.debug(f"Проверка прав администратора для пользователя {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(telegram_id)
            is_admin = user and user.role == UserRole.admin

            if user:
                logger.debug(f"Пользователь {telegram_id}: {user.full_name}, роль: {user.role.value}, is_admin: {is_admin}")
            else:
                logger.debug(f"Пользователь {telegram_id} не найден в базе, is_admin: {is_admin}")

            return is_admin

    except Exception as e:
        logger.error(f"Ошибка при проверке прав администратора для пользователя {telegram_id}: {e}", exc_info=True)
        return False


async def is_user_captain(telegram_id: int) -> bool:
    """Проверка, является ли пользователь капитаном"""
    logger.debug(f"Проверка прав капитана для пользователя {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(telegram_id)
            is_captain = user and user.role == UserRole.captain

            if user:
                logger.debug(f"Пользователь {telegram_id}: {user.full_name}, роль: {user.role.value}, is_captain: {is_captain}")
            else:
                logger.debug(f"Пользователь {telegram_id} не найден в базе, is_captain: {is_captain}")

            return is_captain

    except Exception as e:
        logger.error(f"Ошибка при проверке прав капитана для пользователя {telegram_id}: {e}", exc_info=True)
        return False


async def get_user_role(telegram_id: int) -> UserRole:
    """Получить роль пользователя"""
    logger.debug(f"Получение роли пользователя {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            user = await db_manager.get_user_by_telegram_id(telegram_id)

            if user:
                logger.debug(f"Роль пользователя {telegram_id}: {user.role.value}")
                return user.role
            else:
                logger.debug(f"Пользователь {telegram_id} не найден, роль: None")
                return None

    except Exception as e:
        logger.error(f"Ошибка при получении роли пользователя {telegram_id}: {e}", exc_info=True)
        return None


async def check_id(telegram_id):
    '''Проверяет, есть ли пользователь с данным id в базе данных'''
    logger.debug(f"Проверка существования пользователя по ID: {telegram_id}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            exists = await db_manager.check_user_exists(telegram_id)
            logger.debug(f"Пользователь с ID {telegram_id} существует: {exists}")
            return exists

    except Exception as e:
        logger.error(f"Ошибка при проверке существования пользователя {telegram_id}: {e}", exc_info=True)
        return False


async def check_phone(phone):
    '''Проверяет, есть ли пользователь с данным телефоном в базе данных'''
    # Маскируем телефон для логов
    masked_phone = phone[:3] + "***" + phone[-3:] if len(phone) > 6 else "***"
    logger.debug(f"Проверка существования пользователя по телефону: {masked_phone}")

    try:
        async with async_session() as session:
            db_manager = DatabaseManager(session)
            exists = await db_manager.check_phone_exists(phone)
            logger.debug(f"Пользователь с телефоном {masked_phone} существует: {exists}")
            return exists

    except Exception as e:
        logger.error(f"Ошибка при проверке существования пользователя по телефону {masked_phone}: {e}", exc_info=True)
        return False
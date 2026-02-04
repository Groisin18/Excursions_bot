"""
Инициализация всех роутеров приложения
"""

from .admin.admin_main import router as admin_main_router
from .admin.statistic import router as admin_statistic_router
from .admin.excursions import router as admin_excursions_router
from .admin.promocodes import router as admin_promocodes_router
from .admin.schedule import router as admin_schedule_router
from .admin.slots import router as admin_slots_router
from .admin.new_slot import router as admin_new_slot_router
from .admin.bookings import router as admin_bookings_router
from .admin.clients import router as admin_clients_routher
from .admin.captains import router as admin_captains_router
from .admin.finances import router as admin_finances_router
from .admin.notification import router as admin_notification_router
from .admin.settings import router as admin_settings_router

from .user.user_main import router as user_main_router
from .user.user_excursions import router as user_excursions_router
from .user.user_booking import router as user_bookings_router
from .user.test_payment import router as test_payment_router
from .user.registration import router as registration_router
from .user.redaction_userdata import router as redaction_userdata_router

from .fallback import router as fallback_router


__all__ = [
    'admin_main_router',
    'admin_statistic_router',
    'admin_excursions_router',
    'admin_promocodes_router',
    'admin_schedule_router',
    'admin_slots_router',
    'admin_new_slot_router',
    'admin_bookings_router',
    'admin_clients_routher',
    'admin_captains_router',
    'admin_finances_router',
    'admin_notification_router',
    'admin_settings_router',
    'user_main_router',
    'user_excursions_router',
    'user_bookings_router',
    'test_payment_router',
    'registration_router',
    'redaction_userdata_router',
    'fallback_router',
]

def setup_routers(dp):
    """
    Настройка всех роутеров в правильном порядке
    Порядок важен: более специфичные роутеры должны быть первыми
    """
    # Админские роутеры (с проверкой прав доступа)
    dp.include_router(admin_statistic_router)
    dp.include_router(admin_excursions_router)
    dp.include_router(admin_promocodes_router)
    dp.include_router(admin_schedule_router)
    dp.include_router(admin_slots_router)
    dp.include_router(admin_new_slot_router)
    dp.include_router(admin_bookings_router)
    dp.include_router(admin_clients_routher)
    dp.include_router(admin_captains_router)
    dp.include_router(admin_finances_router)
    dp.include_router(admin_notification_router)
    dp.include_router(admin_settings_router)
    dp.include_router(admin_main_router)

    # Пользовательские роутеры
    dp.include_router(user_excursions_router)
    dp.include_router(user_bookings_router)
    dp.include_router(test_payment_router)
    dp.include_router(registration_router)
    dp.include_router(redaction_userdata_router)
    dp.include_router(user_main_router)

    # Фолбэк роутер (всегда последний)
    dp.include_router(fallback_router)
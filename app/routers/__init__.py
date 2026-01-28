"""
Инициализация всех роутеров приложения
"""

from .user_router import router as user_router
from .admin.admin_main_router import router as admin_main_router
from .admin.statistic import router as admin_statistic_router
from .admin.excursions import router as admin_excursions_router
from .admin.promocodes import router as admin_promocodes_router
from .admin.schedule import router as admin_schedule_router
from .admin.slots import router as admin_slots_router
from .admin.slots import router as admin_new_slot_router
from .admin.bookings import router as admin_bookings_router
from .admin.clients import router as admin_clients_routher
from .admin.captains import router as admin_captains_router
from .admin.finances import router as admin_finances_router
from .admin.notification import router as admin_notification_router
from .admin.settings import router as admin_settings_router
from .payment_router import router as payment_router
from .registration_router import router as registration_router
from .redaction_router import router as redaction_router
from .fallback_router import router as fallback_router


__all__ = [
    'user_router',
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
    'payment_router',
    'registration_router',
    'redaction_router',
    'fallback_router',
]

def setup_routers(dp):
    """
    Настройка всех роутеров в правильном порядке
    Порядок важен: более специфичные роутеры должны быть первыми
    """
    # Админские роутеры (с проверкой прав доступа)
    dp.include_router(admin_main_router)
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

    # Пользовательские роутеры
    dp.include_router(payment_router)
    dp.include_router(registration_router)
    dp.include_router(redaction_router)
    dp.include_router(user_router)

    # Фолбэк роутер (всегда последний)
    dp.include_router(fallback_router)
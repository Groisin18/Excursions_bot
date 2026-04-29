"""
Инициализация всех роутеров приложения
"""

from .admin.add_client import router as admin_add_client_router
from .admin.admin_main import router as admin_main_router
from .admin.bookings import router as admin_bookings_router
from .admin.captains import router as admin_captains_router
from .admin.client_redaction import router as admin_client_redaction_routher
from .admin.clients import router as admin_clients_routher
from .admin.create_booking import router as admin_create_booking_router
from .admin.excursions import router as admin_excursions_router
from .admin.finances import router as admin_finances_router
from .admin.new_slot import router as admin_new_slot_router
from .admin.notification import router as admin_notification_router
from .admin.promocode_edit import router as admin_promocode_edit_router
from .admin.promocodes import router as admin_promocodes_router
from .admin.refunds import router as admin_refunds_router
from .admin.schedule import router as admin_schedule_router
from .admin.settings import router as admin_settings_router
from .admin.slots import router as admin_slots_router
from .admin.statistic import router as admin_statistic_router

from .captain.captain_main import router as captain_main_router

from .user.account.main_router import router as account_main_router
from .user.user_create_booking import router as user_create_booking_router
from .user.user_excursions import router as user_excursions_router
from .user.user_main import router as user_main_router
from .user.user_payment import router as user_payment_router

from .fallback import router as fallback_router


__all__ = [
    'admin_main_router',
    'admin_statistic_router',
    'admin_excursions_router',
    'admin_promocodes_router',
    'admin_promocode_edit_router',
    'admin_schedule_router',
    'admin_slots_router',
    'admin_new_slot_router',
    'admin_bookings_router',
    'admin_create_booking_router',
    'admin_clients_routher',
    'admin_add_client_router',
    'admin_client_redaction_routher',
    'admin_captains_router',
    'admin_finances_router',
    'admin_notification_router',
    'admin_settings_router',
    'admin_refunds_router',

    'captain_main_router',

    'user_main_router',
    'user_excursions_router',
    'user_create_booking_router',
    'user_payment_router',
    'account_main_router',

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

    dp.include_router(admin_promocode_edit_router)
    dp.include_router(admin_promocodes_router)

    dp.include_router(admin_schedule_router)

    dp.include_router(admin_new_slot_router)
    dp.include_router(admin_slots_router)

    dp.include_router(admin_create_booking_router)
    dp.include_router(admin_bookings_router)

    dp.include_router(admin_add_client_router)
    dp.include_router(admin_client_redaction_routher)
    dp.include_router(admin_clients_routher)

    dp.include_router(admin_captains_router)

    dp.include_router(admin_finances_router)
    dp.include_router(admin_refunds_router)

    dp.include_router(admin_notification_router)

    dp.include_router(admin_settings_router)

    dp.include_router(admin_main_router)

    # Роутер капитана
    dp.include_router(captain_main_router)

    # Пользовательские роутеры
    dp.include_router(user_excursions_router)

    dp.include_router(user_create_booking_router)

    dp.include_router(user_payment_router)

    dp.include_router(account_main_router)

    dp.include_router(user_main_router)

    # Фолбэк роутер (всегда последний)
    dp.include_router(fallback_router)
"""
Константы для ключей Redis.
Все ключи организованы по префиксам для удобства поиска и избежания коллизий.
"""

# ========== FSM СОСТОЯНИЯ (автоматически управляются aiogram) ==========
# Эти ключи используются RedisStorage автоматически, но мы их определяем для документации
FSM_KEY_PREFIX = "fsm"  # Префикс для всех ключей FSM
FSM_DATA_KEY = "data"    # Ключ для данных состояния
FSM_STATE_KEY = "state"  # Ключ для имени состояния


# ========== БЛОКИРОВКИ (Locks) ==========
# Используются для предотвращения одновременного редактирования
class Locks:
    """Блокировки для различных сущностей"""
    PREFIX = "lock"

    @staticmethod
    def booking(booking_id: int) -> str:
        """Блокировка бронирования"""
        return f"{Locks.PREFIX}:booking:{booking_id}"

    @staticmethod
    def slot(slot_id: int) -> str:
        """Блокировка слота (чтобы два админа не редактировали одновременно)"""
        return f"{Locks.PREFIX}:slot:{slot_id}"

    @staticmethod
    def user(user_id: int) -> str:
        """Блокировка пользователя"""
        return f"{Locks.PREFIX}:user:{user_id}"

    @staticmethod
    def excursion(excursion_id: int) -> str:
        """Блокировка экскурсии"""
        return f"{Locks.PREFIX}:excursion:{excursion_id}"


# ========== КЭШИРОВАНИЕ (Cache) ==========
# Данные, которые редко меняются, но часто запрашиваются
class Cache:
    """Ключи для кэширования данных"""
    PREFIX = "cache"
    TTL = {
        'excursions': 300,      # 5 минут
        'captains': 600,        # 10 минут
        'clients_search': 60,   # 1 минута
        'schedule': 300,        # 5 минут
    }

    @staticmethod
    def excursions(active_only: bool = True) -> str:
        """Список экскурсий"""
        status = "active" if active_only else "all"
        return f"{Cache.PREFIX}:excursions:{status}"

    @staticmethod
    def captains(all_: bool = False) -> str:
        """Список капитанов"""
        return f"{Cache.PREFIX}:captains:{'all' if all_ else 'active'}"

    @staticmethod
    def client_search(query: str) -> str:
        """Результаты поиска клиентов"""
        # Хэшируем запрос для безопасности и ограничения длины
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        return f"{Cache.PREFIX}:client:search:{query_hash}"

    @staticmethod
    def schedule(date_str: str = None) -> str:
        """Расписание на дату"""
        if date_str:
            return f"{Cache.PREFIX}:schedule:date:{date_str}"
        return f"{Cache.PREFIX}:schedule:week"

    @staticmethod
    def excursion_slots(excursion_id: int, date_from: str = None) -> str:
        """Слоты для конкретной экскурсии"""
        if date_from:
            return f"{Cache.PREFIX}:excursion:{excursion_id}:slots:{date_from}"
        return f"{Cache.PREFIX}:excursion:{excursion_id}:slots"

    @staticmethod
    def booking_info(booking_id: int) -> str:
        """Информация о бронировании"""
        return f"{Cache.PREFIX}:booking:{booking_id}"


# ========== ОЧЕРЕДИ ЗАДАЧ (Queues) ==========
# Для отложенных и фоновых задач
class Queues:
    """Очереди для различных типов задач"""
    PREFIX = "queue"

    # Названия очередей
    NOTIFICATIONS = f"{PREFIX}:notifications"        # Уведомления
    PAYMENT_SYNC = f"{PREFIX}:payment:sync"          # Синхронизация с YooKassa
    REPORTS = f"{PREFIX}:reports"                     # Генерация отчетов
    CLEANUP = f"{PREFIX}:cleanup"                      # Очистка данных


# ========== ОТЛОЖЕННЫЕ ЗАДАЧИ (Scheduled) ==========
# Задачи, которые нужно выполнить в определенное время
class Scheduled:
    """Ключи для отложенных задач"""
    PREFIX = "scheduled"

    @staticmethod
    def cancel_booking(booking_id: int, execute_at: str = None) -> str:
        """
        Ключ для автоотмены бронирования.
        execute_at - время выполнения в формате ISO для уникальности
        """
        if execute_at:
            return f"{Scheduled.PREFIX}:cancel:booking:{booking_id}:{execute_at}"
        return f"{Scheduled.PREFIX}:cancel:booking:{booking_id}"

    @staticmethod
    def reminder(booking_id: int, reminder_type: str, execute_at: str = None) -> str:
        """
        Ключ для напоминания.
        reminder_type: '24h', '3h', '1h'
        """
        if execute_at:
            return f"{Scheduled.PREFIX}:reminder:{booking_id}:{reminder_type}:{execute_at}"
        return f"{Scheduled.PREFIX}:reminder:{booking_id}:{reminder_type}"

    @staticmethod
    def payment_check(booking_id: int) -> str:
        """Проверка статуса оплаты"""
        return f"{Scheduled.PREFIX}:payment:check:{booking_id}"


# ========== ВРЕМЕННЫЕ ДАННЫЕ (Temporary) ==========
# Данные с коротким сроком жизни
class Temp:
    """Временные данные с TTL"""
    PREFIX = "temp"

    @staticmethod
    def booking_draft(user_id: int) -> str:
        """Черновик бронирования (если пользователь не завершил процесс)"""
        return f"{Temp.PREFIX}:booking:draft:{user_id}"

    @staticmethod
    def auth_code(phone: str) -> str:
        """Код подтверждения для входа"""
        return f"{Temp.PREFIX}:auth:code:{phone}"

    @staticmethod
    def payment_session(payment_id: str) -> str:
        """Сессия оплаты"""
        return f"{Temp.PREFIX}:payment:session:{payment_id}"

    @staticmethod
    def export_data(admin_id: int, export_type: str) -> str:
        """Временные данные для экспорта"""
        return f"{Temp.PREFIX}:export:{admin_id}:{export_type}"


# ========== СЧЕТЧИКИ И СТАТИСТИКА (Counters) ==========
class Stats:
    """Ключи для счетчиков и статистики"""
    PREFIX = "stats"

    @staticmethod
    def daily_bookings(date_str: str = None) -> str:
        """Количество бронирований за день"""
        from datetime import date
        if not date_str:
            date_str = date.today().isoformat()
        return f"{Stats.PREFIX}:daily:bookings:{date_str}"

    @staticmethod
    def captain_load(captain_id: int, date_str: str = None) -> str:
        """Загрузка капитана (количество бронирований)"""
        from datetime import date
        if not date_str:
            date_str = date.today().isoformat()
        return f"{Stats.PREFIX}:captain:{captain_id}:load:{date_str}"

    @staticmethod
    def excursion_popularity(excursion_id: int) -> str:
        """Популярность экскурсии (общее количество бронирований)"""
        return f"{Stats.PREFIX}:excursion:{excursion_id}:popularity"

    @staticmethod
    def user_visits(user_id: int) -> str:
        """Количество визитов пользователя"""
        return f"{Stats.PREFIX}:user:{user_id}:visits"


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def ttl_for(key_type: str) -> int:
    """
    Возвращает TTL для определенного типа ключей.
    Используется при установке значений с автоматическим удалением.
    """
    ttl_map = {
        # Кэш
        'excursions': Cache.TTL['excursions'],
        'captains': Cache.TTL['captains'],
        'client_search': Cache.TTL['clients_search'],
        'schedule': Cache.TTL['schedule'],

        # Временные данные
        'auth_code': 300,           # 5 минут
        'booking_draft': 3600,      # 1 час
        'payment_session': 1800,    # 30 минут
        'export_data': 600,         # 10 минут

        # Блокировки
        'lock': 30,                  # 30 секунд (максимальное время блокировки)
    }
    return ttl_map.get(key_type, 3600)  # По умолчанию 1 час


def pattern_for_key(key: str) -> str:
    """
    Возвращает паттерн для поиска всех ключей определенного типа.
    Например: pattern_for_key('lock:booking:*') -> 'lock:booking:*'
    """
    return f"{key}"


# Для удобства можно сгруппировать все классы в один объект
class RedisKeys:
    """Группировка всех ключей Redis"""
    locks = Locks
    cache = Cache
    queues = Queues
    scheduled = Scheduled
    temp = Temp
    stats = Stats

    @staticmethod
    def ttl(key_type: str) -> int:
        return ttl_for(key_type)


# Создаем глобальный экземпляр для удобного импорта
keys = RedisKeys()
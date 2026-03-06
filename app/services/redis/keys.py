"""
Константы для ключей Redis.
Каждый новый тип ключей добавляется по мере необходимости.
"""

# ========== FSM СОСТОЯНИЯ (используются RedisStorage) ==========
FSM_KEY_PREFIX = "fsm"
FSM_DATA_KEY = "data"
FSM_STATE_KEY = "state"


# ========== ЗАГОТОВКИ ДЛЯ БУДУЩИХ КЛЮЧЕЙ ==========
# Классы ниже - это каркас для планового расширения.
# Конкретные ключи добавляются только при реализации соответствующего функционала.

class Locks:
    """Блокировки (добавлять по мере внедрения)"""
    PREFIX = "lock"
    pass


class Cache:
    """Кэширование (добавлять по мере внедрения)"""
    PREFIX = "cache"
    pass


class Queues:
    """Очереди задач (добавлять по мере внедрения)"""
    PREFIX = "queue"
    pass


class Scheduled:
    """Отложенные задачи (добавлять по мере внедрения)"""
    PREFIX = "scheduled"
    pass


class Temp:
    """Временные данные (добавлять по мере внедрения)"""
    PREFIX = "temp"
    pass


class Stats:
    """Счетчики и статистика (добавлять по мере внедрения)"""
    PREFIX = "stats"
    pass


# Группировка для удобства импорта
class RedisKeys:
    """Группировка всех ключей Redis"""
    fsm_prefix = FSM_KEY_PREFIX
    fsm_data = FSM_DATA_KEY
    fsm_state = FSM_STATE_KEY

    locks = Locks
    cache = Cache
    queues = Queues
    scheduled = Scheduled
    temp = Temp
    stats = Stats


keys = RedisKeys()
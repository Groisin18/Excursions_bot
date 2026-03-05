import json
from datetime import date, datetime
from typing import Any, Dict, List, Union

class RedisJSONEncoder(json.JSONEncoder):
    """Encoder для сериализации date/datetime в JSON для Redis"""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return {
                '__type__': 'date',
                'value': obj.isoformat()
            }
        return super().default(obj)


def redis_object_hook(obj: Dict) -> Dict:
    """
    Object hook для декодирования JSON из Redis.
    Преобразует помеченные объекты обратно в date/datetime.
    """
    if '__type__' in obj and obj['__type__'] == 'date':
        try:
            value = obj['value']
            # Пробуем распарсить как datetime (если есть время)
            if 'T' in value:
                return datetime.fromisoformat(value)
            # Иначе как date
            return date.fromisoformat(value)
        except (ValueError, KeyError):
            # Если не получилось, возвращаем как есть
            return obj
    return obj


def dumps(obj: Any) -> str:
    """Сериализация объекта в JSON строку для Redis"""
    return json.dumps(obj, cls=RedisJSONEncoder)


def loads(data: str) -> Any:
    """Десериализация JSON строки из Redis в объект Python"""
    return json.loads(data, object_hook=redis_object_hook)


# Для обратной совместимости (если нужен простой encoder без object_hook)
class SimpleRedisJSONEncoder(json.JSONEncoder):
    """Простой encoder - преобразует date в строку без метаданных"""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def simple_dumps(obj: Any) -> str:
    """Простая сериализация (date -> строка, без восстановления)"""
    return json.dumps(obj, cls=SimpleRedisJSONEncoder)
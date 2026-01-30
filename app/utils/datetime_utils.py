from datetime import datetime


def get_weekday_name(date_obj: datetime) -> str:
    """Получить название дня недели на русском"""
    weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return weekdays[date_obj.weekday()]

def get_weekday_short_name(date_obj: datetime) -> str:
    """Получить название дня недели на русском"""
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return weekdays[date_obj.weekday()]
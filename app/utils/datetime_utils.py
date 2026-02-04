from datetime import datetime, date


def get_weekday_name(date_obj: datetime) -> str:
    """Получить название дня недели на русском"""
    weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return weekdays[date_obj.weekday()]


def get_weekday_short_name(date_obj: datetime) -> str:
    """Получить название дня недели на русском"""
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return weekdays[date_obj.weekday()]


def calculate_age(birth_date: date) -> int:
    """Вычисляет возраст по дате рождения"""
    if not birth_date:
        return None

    today = date.today()
    age = today.year - birth_date.year

    # Проверяем, был ли уже день рождения в этом году
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age
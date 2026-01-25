from datetime import datetime, timedelta
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_week_range(date: datetime) -> tuple:
    """Получение начала и конца недели для даты"""
    logger.debug(f"Вычисление недельного диапазона для даты: {date.strftime('%Y-%m-%d')}")

    try:
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)

        result = (start, end)
        logger.debug(f"Недельный диапазон: {start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")

        return result

    except Exception as e:
        logger.error(f"Ошибка при вычислении недельного диапазона для даты {date}: {e}", exc_info=True)
        # Возвращаем fallback значения
        fallback_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        fallback_end = fallback_start + timedelta(days=6)
        return fallback_start, fallback_end


def is_working_time(datetime_obj: datetime) -> bool:
    """Проверка рабочего времени (9:00-18:00)"""
    logger.debug(f"Проверка рабочего времени для: {datetime_obj.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        hour = datetime_obj.hour
        is_working = 9 <= hour < 18

        logger.debug(f"Время {datetime_obj.strftime('%H:%M')} - рабочие часы: {is_working}")
        return is_working

    except Exception as e:
        logger.error(f"Ошибка при проверке рабочего времени для {datetime_obj}: {e}", exc_info=True)
        # В случае ошибки считаем что не рабочее время
        return False


def format_duration(minutes: int) -> str:
    """Форматирование длительности в читаемый вид"""
    logger.debug(f"Форматирование длительности: {minutes} минут")

    try:
        if minutes < 60:
            result = f"{minutes} мин"
        else:
            hours = minutes // 60
            mins = minutes % 60
            result = f"{hours} ч {mins} мин" if mins > 0 else f"{hours} ч"

        logger.debug(f"Форматированная длительность: {result}")
        return result

    except Exception as e:
        logger.error(f"Ошибка форматирования длительности {minutes} минут: {e}", exc_info=True)
        return f"{minutes} мин"


def parse_date_string(date_str: str, format_str: str = "%Y-%m-%d") -> datetime:
    """Парсинг строки с датой"""
    logger.debug(f"Парсинг даты из строки: '{date_str}' с форматом '{format_str}'")

    try:
        parsed_date = datetime.strptime(date_str, format_str)
        logger.debug(f"Успешно распарсена дата: {parsed_date.strftime('%Y-%m-%d')}")
        return parsed_date

    except ValueError as e:
        logger.error(f"Ошибка парсинга даты '{date_str}' с форматом '{format_str}': {e}")
        raise
    except Exception as e:
        logger.error(f"Неизвестная ошибка при парсинге даты '{date_str}': {e}", exc_info=True)
        raise


def get_time_until_next_day(target_hour: int = 0) -> timedelta:
    """Получить время до следующего дня (или до указанного часа)"""
    logger.debug(f"Вычисление времени до следующего дня (час: {target_hour})")

    try:
        now = datetime.now()
        target_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)

        if now >= target_time:
            target_time += timedelta(days=1)

        time_until = target_time - now
        logger.debug(f"До следующего дня ({target_hour}:00) осталось: {time_until}")

        return time_until

    except Exception as e:
        logger.error(f"Ошибка вычисления времени до следующего дня: {e}", exc_info=True)
        return timedelta(hours=24)

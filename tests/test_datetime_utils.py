import pytest
from datetime import datetime
from app.utils.datetime_utils import get_weekday_name, get_weekday_short_name


def test_get_weekday_name():
    """Тест получения названия дня недели."""
    test_cases = [
        (datetime(2024, 1, 1), "понедельник"),  # Понедельник
        (datetime(2024, 1, 2), "вторник"),      # Вторник
        (datetime(2024, 1, 3), "среда"),        # Среда
        (datetime(2024, 1, 4), "четверг"),      # Четверг
        (datetime(2024, 1, 5), "пятница"),      # Пятница
        (datetime(2024, 1, 6), "суббота"),      # Суббота
        (datetime(2024, 1, 7), "воскресенье"),  # Воскресенье
    ]

    for date_obj, expected in test_cases:
        result = get_weekday_name(date_obj)
        assert result == expected


def test_get_weekday_short_name():
    """Тест получения короткого названия дня недели."""
    test_cases = [
        (datetime(2024, 1, 1), "Пн"),
        (datetime(2024, 1, 2), "Вт"),
        (datetime(2024, 1, 3), "Ср"),
        (datetime(2024, 1, 4), "Чт"),
        (datetime(2024, 1, 5), "Пт"),
        (datetime(2024, 1, 6), "Сб"),
        (datetime(2024, 1, 7), "Вс"),
    ]

    for date_obj, expected in test_cases:
        result = get_weekday_short_name(date_obj)
        assert result == expected


def test_weekday_functions_type():
    """Тест типов возвращаемых значений."""
    date_obj = datetime(2024, 1, 1)

    result1 = get_weekday_name(date_obj)
    result2 = get_weekday_short_name(date_obj)

    assert isinstance(result1, str)
    assert isinstance(result2, str)
    assert len(result2) <= 2  # Короткое название должно быть 2 символа


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
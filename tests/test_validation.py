"""
Тесты для модуля валидаторов (чистые функции)
"""

import re
import pytest
from datetime import date, time
from unittest.mock import patch, MagicMock

from app.utils.validation import (
    # Персональные данные
    validate_name,
    validate_surname,
    validate_address,
    validate_birthdate,
    validate_weight,

    # Контактные данные
    validate_phone,
    validate_email,

    # Бронирование и слоты
    validate_slot_date,
    validate_slot_time,
    validate_excursion_duration,

    # Финансовые операции
    validate_amount_rub,
    validate_discount,

    # Разное
    validate_token_format,
    generate_virtual_phone,
    parse_virtual_phone,
    validate_promocode,

    # Pydantic валидаторы
    pydantic_validate_name,
    pydantic_validate_surname,
    pydantic_validate_email,
    pydantic_validate_phone,
    pydantic_validate_birthdate,
)


# ==================== Тесты для validate_name ====================
class TestValidateName:
    """Тесты для валидации имени."""

    def test_valid_name(self):
        """Позитивные тесты с корректными именами."""
        test_cases = [
            ("иван", "Иван"),
            ("ИВАН", "Иван"),
            ("иван-петр", "Иван-Петр"),
            ("анна мария", "Анна Мария"),
            ("John", "John"),
            ("john doe", "John Doe"),
            ("ёлка", "Ёлка")
        ]

        for input_name, expected in test_cases:
            result = validate_name(input_name)
            assert result == expected

    def test_invalid_characters(self):
        """Тесты с недопустимыми символами."""
        invalid_names = [
            "иван123",
            "test@mail",
            "name_underscore",
            "имя!",
            "name#",
            ""
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="В имени допустимы только буквы, пробелы и дефисы"):
                validate_name(name)

    def test_length_validation(self):
        """Тесты проверки длины."""
        # Слишком короткое
        with pytest.raises(ValueError, match="Минимальная длина имени - 1 символ"):
            validate_name("   ")

        # Слишком длинное (51 символ)
        long_name = "а" * 51
        with pytest.raises(ValueError, match="Максимальная длина имени - 50 символов"):
            validate_name(long_name)

        # Граничное значение - 50 символов
        exact_length = "а" * 50
        result = validate_name(exact_length)
        assert len(result) == 50

    def test_whitespace_handling(self):
        """Тесты обработки пробелов."""
        assert validate_name("  иван  ") == "Иван"
        assert validate_name("  анна  мария  ") == "Анна  Мария"


# ==================== Тесты для validate_surname ====================
class TestValidateSurname:
    """Тесты для валидации фамилии."""

    def test_valid_surname(self):
        """Корректные фамилии."""
        assert validate_surname("иванов") == "Иванов"
        assert validate_surname("иванов-петров") == "Иванов-Петров"
        assert validate_surname("smith jones") == "Smith Jones"

    def test_invalid_surname(self):
        """Некорректные фамилии."""
        with pytest.raises(ValueError):
            validate_surname("123")
        with pytest.raises(ValueError):
            validate_surname("")


# ==================== Тесты для validate_address ====================
class TestValidateAddress:
    """Тесты для валидации адреса."""

    def test_valid_address(self):
        """Корректные адреса."""
        test_cases = [
            ("ул. Ленина, д. 10", "ул. Ленина, д. 10"),
            ("Москва, пр-т Мира 25-17", "Москва, пр-т Мира 25-17"),
            ("street 123, apt. 45", "street 123, apt. 45"),
            ("проспект 40-летия Победы, 123/4", "проспект 40-летия Победы, 123/4")
        ]

        for input_addr, expected in test_cases:
            result = validate_address(input_addr)
            assert result == expected

    def test_address_length(self):
        """Проверка длины адреса."""
        # Слишком короткий
        with pytest.raises(ValueError, match="Минимальная длина адреса - 5 символов"):
            validate_address("ул.")

        # Слишком длинный (151 символ)
        long_addr = "ул. " + "а" * 147
        with pytest.raises(ValueError, match="Максимальная длина адреса - 150 символов"):
            validate_address(long_addr)

    def test_invalid_characters(self):
        """Адреса с недопустимыми символами."""
        with pytest.raises(ValueError, match="Адрес содержит недопустимые символы"):
            validate_address("ул. Ленина @дом 10")

    def test_minimum_words(self):
        """Адрес должен содержать минимум 2 слова."""
        with pytest.raises(ValueError, match="Адрес должен содержать минимум 2 слова"):
            validate_address("Ленина")


# ==================== Тесты для validate_birthdate ====================
class TestValidateBirthdate:
    """Тесты для валидации даты рождения."""

    def test_valid_dates(self):
        """Корректные даты рождения."""
        test_cases = [
            ("01.01.1990", "01.01.1990"),
            ("1.1.90", "01.01.1990"),  # двухзначный год
            ("31.12.2020", "31.12.2020"),
            ("15.08.85", "15.08.1985"),
        ]

        for input_date, expected in test_cases:
            result = validate_birthdate(input_date)
            assert result == expected

    def test_invalid_formats(self):
        """Некорректные форматы."""
        invalid_dates = [
            "01-01-1990",
            "1990.01.01",
            "01/01/1990",
            "1 января 1990",
            "abc",
            ""
        ]

        for date_str in invalid_dates:
            with pytest.raises(ValueError, match="Неверный формат"):
                validate_birthdate(date_str)

    def test_invalid_calendar_dates(self):
        """Некорректные календарные даты."""
        with pytest.raises(ValueError, match="Некорректная дата"):
            validate_birthdate("31.02.2020")
        with pytest.raises(ValueError, match="Некорректная дата"):
            validate_birthdate("30.02.2020")

    def test_future_date(self):
        """Дата рождения не может быть в будущем."""
        from datetime import timedelta
        future_date = date.today() + timedelta(days=1)
        date_str = future_date.strftime("%d.%m.%Y")

        with pytest.raises(ValueError, match="не может быть в будущем"):
            validate_birthdate(date_str)

    def test_too_old_date(self):
        """Слишком ранние даты (до 1926 года)."""
        with pytest.raises(ValueError, match="Навряд ли вы родились так рано"):
            validate_birthdate("01.01.1925")

    def test_two_digit_year_conversion(self):
        """Тест преобразования двухзначных годов."""
        # Проверяем, что функция вообще работает с двухзначными годами
        try:
            result = validate_birthdate("01.01.90")
            # Проверяем формат
            assert re.match(r'\d{2}\.\d{2}\.\d{4}', result)
            day, month, year = result.split('.')
            # Год должен быть четырехзначным
            assert len(year) == 4
            assert year.isdigit()
        except ValueError:
            pass

        # Проверяем другой случай
        try:
            result = validate_birthdate("01.01.25")
            assert re.match(r'\d{2}\.\d{2}\.\d{4}', result)
        except ValueError as e:
            assert "не может быть в будущем" in str(e) or "Навряд ли" in str(e)


# ==================== Тесты для validate_slot_date ====================
class TestValidateSlotDate:
    """Тесты для валидации даты слота."""

    def test_valid_slot_date(self):
        """Корректные даты для слотов."""
        from datetime import timedelta
        tomorrow = date.today() + timedelta(days=1)
        date_str = tomorrow.strftime("%d.%m.%Y")

        result = validate_slot_date(date_str)
        assert isinstance(result, date)
        assert result == tomorrow

    def test_past_date(self):
        """Прошедшие даты не допускаются."""
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        date_str = yesterday.strftime("%d.%m.%Y")

        with pytest.raises(ValueError, match="Прошедшая дата не подходит"):
            validate_slot_date(date_str)

    def test_two_digit_year(self):
        """Двухзначные годы в дате слота."""
        with patch('app.utils.validation.date') as mock_date_class:
            mock_today = MagicMock(return_value=date(2024, 1, 1))
            mock_date_class.today = mock_today
            mock_date_class.side_effect = date

            result = validate_slot_date("01.02.24")
            assert result == date(2024, 2, 1)


# ==================== Тесты для validate_slot_time ====================
class TestValidateSlotTime:
    """Тесты для валидации времени слота."""

    def test_valid_times(self):
        """Корректное время."""
        test_cases = [
            ("12:00", time(12, 0)),
            ("1:30", time(1, 30)),
            ("23:59", time(23, 59)),
            ("0:00", time(0, 0)),
            ("9:05", time(9, 5))
        ]

        for time_str, expected in test_cases:
            result = validate_slot_time(time_str)
            assert result == expected

    def test_invalid_formats(self):
        """Некорректные форматы времени."""
        invalid_times = [
            "12-00",
            "12.00",
            "1200",
            "12:",
            ":30",
            "abc"
        ]

        for time_str in invalid_times:
            with pytest.raises(ValueError, match="Неверный формат"):
                validate_slot_time(time_str)

    def test_hour_range(self):
        """Проверка диапазона часов."""
        with pytest.raises(ValueError, match="Час должен быть в диапазоне от 0 до 23"):
            validate_slot_time("24:00")

    def test_minute_range(self):
        """Проверка диапазона минут."""
        with pytest.raises(ValueError, match="Минуты должны быть в диапазоне от 0 до 59"):
            validate_slot_time("12:60")


# ==================== Тесты для validate_weight ====================
class TestValidateWeight:
    """Тесты для валидации веса."""

    def test_valid_weight(self):
        """Корректный вес."""
        assert validate_weight("70") == 70
        assert validate_weight("1") == 1
        assert validate_weight("299") == 299

    def test_invalid_weight(self):
        """Некорректный вес."""
        with pytest.raises(ValueError, match="Вес должен быть целым числом"):
            validate_weight("abc")

        with pytest.raises(ValueError, match="Вес должен быть от 1 до 299 кг"):
            validate_weight("0")

        with pytest.raises(ValueError, match="Вес должен быть от 1 до 299 кг"):
            validate_weight("300")

        with pytest.raises(ValueError, match="Вес должен быть целым числом"):
            validate_weight("-50")


# ==================== Тесты для validate_phone ====================
class TestValidatePhone:
    """Тесты для валидации телефона."""

    def test_valid_phones(self):
        """Корректные номера телефонов."""
        test_cases = [
            ("+79161234567", "+79161234567"),
            ("89161234567", "+79161234567"),  # 8 в начале
            ("79161234567", "+79161234567"),  # 7 в начале
            ("+7 (916) 123-45-67", "+79161234567"),  # с символами
            ("8-916-123-45-67", "+79161234567"),
        ]

        for input_phone, expected in test_cases:
            result = validate_phone(input_phone)
            assert result == expected

    def test_invalid_phones(self):
        """Некорректные номера."""
        invalid_phones = [
            "1234567890",  # слишком короткий
            "+791612345678",  # слишком длинный
            "+38161234567",  # не российский код
            "телефон",
            "",
            "+7(916)123"  # неполный
        ]

        for phone in invalid_phones:
            with pytest.raises(ValueError, match="Неверный формат номера телефона"):
                validate_phone(phone)


# ==================== Тесты для validate_email ====================
class TestValidateEmail:
    """Тесты для валидации email."""

    def test_valid_emails(self):
        """Корректные email адреса."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@domain.org",
            "a@b.cd"
        ]

        for email in valid_emails:
            result = validate_email(email)
            assert result == email

    def test_invalid_emails(self):
        """Некорректные email адреса."""
        invalid_emails = [
            "test",
            "test@",
            "@domain.com",
            "test@domain",
            "test@.com",
            "test@domain..com",
            ""
        ]

        for email in invalid_emails:
            with pytest.raises(ValueError, match="Неверный формат email"):
                validate_email(email)


# ==================== Тесты для validate_excursion_duration ====================
class TestValidateExcursionDuration:
    """Тесты для валидации продолжительности экскурсии."""

    def test_valid_durations(self):
        """Корректные продолжительности (кратные 10 минутам)."""
        test_cases = [
            ("90", 90),  # только минуты
            ("1:30", 90),  # часы:минуты
            ("2 40", 160),  # часы пробел минуты
            ("1.30", 90),  # часы.минуты
            ("1,20", 80),  # часы,минуты
            ("10", 10),  # минимальная
            ("48:00", 2880),  # максимальная
            ("2-30", 150),  # часы-минуты
        ]

        for input_dur, expected in test_cases:
            result = validate_excursion_duration(input_dur)
            assert result == expected

    def test_invalid_formats(self):
        """Некорректные форматы."""
        invalid_durations = [
            "abc",
            "1:30:00",  # слишком много частей
            "",
            "  ",
        ]

        for duration in invalid_durations:
            with pytest.raises(ValueError):
                validate_excursion_duration(duration)

    def test_minimum_duration(self):
        """Минимальная продолжительность 10 минут."""
        with pytest.raises(ValueError, match="не менее 10 минут"):
            validate_excursion_duration("9")
        with pytest.raises(ValueError, match="не менее 10 минут"):
            validate_excursion_duration("0:09")

    def test_maximum_duration(self):
        """Максимальная продолжительность 48 часов."""
        with pytest.raises(ValueError, match="не должна превышать 48 часов"):
            validate_excursion_duration("48:01")
        with pytest.raises(ValueError, match="не должна превышать 48 часов"):
            validate_excursion_duration("2881")

    def test_multiple_of_ten(self):
        """Продолжительность должна быть кратной 10 минутам."""
        with pytest.raises(ValueError, match="кратной 10 минутам"):
            validate_excursion_duration("11")
        with pytest.raises(ValueError, match="кратной 10 минутам"):
            validate_excursion_duration("1:31")

    def test_minute_validation(self):
        """Минуты должны быть от 0 до 59."""
        with pytest.raises(ValueError, match="Минуты должны быть от 00 до 59"):
            validate_excursion_duration("1:60")


# ==================== Тесты для validate_amount_rub ====================
class TestValidateAmountRub:
    """Тесты для валидации суммы в рублях."""

    def test_valid_amounts(self):
        """Корректные суммы."""
        test_cases = [
            ("1000", 1000),
            ("1500.50", 1500),
            ("1500.49", 1500),
            ("1 000", 1000),
            ("2 000,00", 2000),
            ("1500.00", 1500),
            (1000, 1000),
            (1500.50, 1500),
        ]

        for input_amount, expected in test_cases:
            result = validate_amount_rub(input_amount)
            assert result == expected

    def test_invalid_amounts(self):
        """Некорректные суммы."""
        invalid_amounts = [
            "abc",
            "",
            "10.10.10",
            "-100",
        ]

        for amount in invalid_amounts:
            with pytest.raises(ValueError):
                validate_amount_rub(amount)

    def test_minimum_amount(self):
        """Минимальная сумма 1 рубль."""
        with pytest.raises(ValueError, match="Минимальная сумма - 1 рубль"):
            validate_amount_rub("0")
        with pytest.raises(ValueError, match="Минимальная сумма - 1 рубль"):
            validate_amount_rub("0.99")

    def test_maximum_amount(self):
        """Максимальная сумма 20,000 рублей."""
        with pytest.raises(ValueError, match="Максимальная сумма - 20 000 рублей"):
            validate_amount_rub("20001")

        result = validate_amount_rub("20000")
        assert result == 20000


# ==================== Тесты для validate_discount ====================
class TestValidateDiscount:
    """Тесты для валидации скидки."""

    def test_valid_discounts(self):
        """Корректные скидки."""
        assert validate_discount("0") == 0
        assert validate_discount("50") == 50
        assert validate_discount("100") == 100
        assert validate_discount(75) == 75

    def test_invalid_discounts(self):
        """Некорректные скидки."""
        with pytest.raises(ValueError, match="не может быть отрицательной"):
            validate_discount("-10")

        with pytest.raises(ValueError, match="не может превышать 100%"):
            validate_discount("101")

        with pytest.raises(ValueError):
            validate_discount("abc")

        with pytest.raises(ValueError):
            validate_discount("")


# ==================== Тесты для validate_promo_code ====================
class TestValidatePromoCode:
    """Тесты для валидации промокода."""

    def test_valid_promo_codes(self):
        """Корректные промокоды."""
        test_cases = [
            ("SUMMER2024", "SUMMER2024"),
            ("WELCOME10", "WELCOME10"),
            ("BLACKFRIDAY", "BLACKFRIDAY"),
            ("ABC123", "ABC123"),
            ("A" * 20, "A" * 20),  # максимальная длина
            ("ABCD", "ABCD"),  # минимальная длина
        ]

        for code, expected in test_cases:
            result = validate_promocode(code)
            assert result == expected

    def test_case_normalization(self):
        """Проверка приведения к верхнему регистру."""
        assert validate_promocode("summer2024") == "SUMMER2024"
        assert validate_promocode("Summer2024") == "SUMMER2024"

    def test_invalid_length(self):
        """Некорректная длина промокода."""
        with pytest.raises(ValueError, match="минимум 4 символа"):
            validate_promocode("ABC")

        with pytest.raises(ValueError, match="максимум 20 символов"):
            validate_promocode("A" * 21)
    def test_short_promo_codes(self):
        """Слишком короткие промокоды."""
        short_codes = [
            "",
            "A",
            "AB",
            "ABC",
            "123",
        ]

        for code in short_codes:
            with pytest.raises(ValueError, match="Код промокода должен содержать минимум"):
                validate_promocode(code)

    def test_invalid_characters(self):
        """Недопустимые символы в промокоде."""
        invalid_codes = [
            "test@code",
            "code-with-dash",
            "code with spaces",
            "code_underscore",
            "тест"
        ]

        for code in invalid_codes:
            with pytest.raises(ValueError, match="Код промокода может содержать только"):
                validate_promocode(code)

    def test_only_digits(self):
        """Промокод не может состоять только из цифр."""
        with pytest.raises(ValueError, match="Промокод не может состоять только из цифр"):
            validate_promocode("123456")


# ==================== Тесты для token и virtual phone ====================
class TestTokenAndVirtualPhone:
    """Тесты для токенов и виртуальных номеров."""

    def test_validate_token_format(self):
        """Валидация формата токена."""
        valid_tokens = [
            "abc123DEF456ghi789JKL012mno345PQR678",
            "test-token_with_underscore-and-dash123",
            "A" * 32,  # минимальная длина
            "a" * 100,  # длинный токен
        ]

        for token in valid_tokens:
            assert validate_token_format(token) is True

        invalid_tokens = [
            "short",  # слишком короткий
            "invalid@token",  # недопустимый символ
            "token with spaces",
            "",
            "a" * 31,  # 31 символ (меньше 32)
        ]

        for token in invalid_tokens:
            assert validate_token_format(token) is False

    def test_generate_virtual_phone(self):
        """Генерация виртуального номера."""
        parent_phone = "+79161234567"
        token = "abc123"

        result = generate_virtual_phone(parent_phone, token)
        assert result == "+79161234567:abc123:child"

    def test_parse_virtual_phone(self):
        """Парсинг виртуального номера."""
        virtual = "+79161234567:abc123:child"
        parent, token = parse_virtual_phone(virtual)

        assert parent == "+79161234567"
        assert token == "abc123"

    def test_parse_invalid_virtual_phone(self):
        """Парсинг некорректного виртуального номера."""
        invalid_virtuals = [
            "+79161234567:abc123",  # нет :child
            "+79161234567:abc123:invalid",
            "not_a_virtual_phone",
            "",
        ]

        for virtual in invalid_virtuals:
            parent, token = parse_virtual_phone(virtual)
            assert parent is None
            assert token is None


# ==================== Тесты для Pydantic валидаторов ====================
class TestPydanticValidators:
    """Тесты для Pydantic валидаторов."""

    def test_pydantic_name_validator(self):
        """Pydantic валидатор для имени."""
        assert pydantic_validate_name("иван") == "Иван"
        assert pydantic_validate_name("JOHN") == "John"

        with pytest.raises(ValueError):
            pydantic_validate_name("123")

    def test_pydantic_surname_validator(self):
        """Pydantic валидатор для фамилии."""
        assert pydantic_validate_surname("иванов") == "Иванов"
        assert pydantic_validate_surname("smith") == "Smith"

    def test_pydantic_email_validator(self):
        """Pydantic валидатор для email."""
        assert pydantic_validate_email("test@example.com") == "test@example.com"

        with pytest.raises(ValueError):
            pydantic_validate_email("invalid")

    def test_pydantic_phone_validator(self):
        """Pydantic валидатор для телефона."""
        assert pydantic_validate_phone("+79161234567") == "+79161234567"

        with pytest.raises(ValueError):
            pydantic_validate_phone("invalid")

    def test_pydantic_birthdate_validator(self):
        """Pydantic валидатор для даты рождения."""
        assert pydantic_validate_birthdate("01.01.1990") == "01.01.1990"

        with pytest.raises(ValueError):
            pydantic_validate_birthdate("invalid")


# ==================== Тесты с моками для логгера ====================
class TestLogging:
    """Тесты для проверки логирования."""

    def test_logging_in_validation(self):
        """Проверка, что валидация логирует вызовы."""
        with patch('app.utils.validation.logger') as mock_logger:
            mock_logger.debug = MagicMock()
            mock_logger.warning = MagicMock()

            validate_name("иван")
            assert mock_logger.debug.called

    def test_error_logging(self):
        """Проверка логирования ошибок."""
        with patch('app.utils.validation.logger') as mock_logger:
            mock_logger.warning = MagicMock()

            try:
                validate_name("123")
            except ValueError:
                pass

            assert mock_logger.warning.called


# ==================== Параметризованные тесты ====================
@pytest.mark.parametrize("name,expected", [
    ("иван", "Иван"),
    ("АННА", "Анна"),
    ("john doe", "John Doe"),
    ("ёлка", "Ёлка"),
])
def test_validate_name_parametrized(name, expected):
    """Параметризованные тесты для validate_name."""
    result = validate_name(name)
    assert result == expected


@pytest.mark.parametrize("phone,expected", [
    ("+79161234567", "+79161234567"),
    ("89161234567", "+79161234567"),
    ("7 916 123 45 67", "+79161234567"),
])
def test_validate_phone_parametrized(phone, expected):
    """Параметризованные тесты для validate_phone."""
    result = validate_phone(phone)
    assert result == expected


@pytest.mark.parametrize("promo_code,expected", [
    ("SUMMER2024", "SUMMER2024"),
    ("welcome10", "WELCOME10"),
    ("ABC123DEF", "ABC123DEF"),
])
def test_validate_promo_code_parametrized(promo_code, expected):
    """Параметризованные тесты для validate_promo_code."""
    result = validate_promocode(promo_code)
    assert result == expected


# ==================== Тесты для краевых случаев ====================
class TestEdgeCases:
    """Тесты для краевых случаев."""

    def test_empty_strings(self):
        """Пустые строки во всех валидаторах."""
        validators = [
            (validate_name, ""),
            (validate_surname, ""),
            (validate_address, ""),
            (validate_birthdate, ""),
            (validate_slot_date, ""),
            (validate_slot_time, ""),
            (validate_weight, ""),
            (validate_phone, ""),
            (validate_email, ""),
            (validate_excursion_duration, ""),
            (validate_amount_rub, ""),
            (validate_discount, ""),
            (validate_promocode, ""),
        ]

        for validator, value in validators:
            with pytest.raises(ValueError):
                validator(value)

    def test_whitespace_only(self):
        """Только пробелы."""
        with pytest.raises(ValueError):
            validate_name("   ")
        with pytest.raises(ValueError):
            validate_address("     ")

    def test_none_values(self):
        """None значения."""
        with pytest.raises(ValueError, match="Введите сумму"):
            validate_amount_rub(None)

        with pytest.raises(ValueError, match="Введите размер скидки"):
            validate_discount(None)

    def test_extreme_values(self):
        """Экстремальные значения."""
        # Вес на границах
        assert validate_weight("1") == 1
        assert validate_weight("299") == 299

        # Скидка на границах
        assert validate_discount("0") == 0
        assert validate_discount("100") == 100

        # Сумма на границах
        assert validate_amount_rub("1") == 1
        assert validate_amount_rub("20000") == 20000

        # Промокод на границах длины
        assert validate_promocode("ABCD") == "ABCD"
        assert validate_promocode("A" * 20) == "A" * 20


# ==================== Интеграционные тесты ====================
class TestIntegration:
    """Интеграционные тесты для проверки совместной работы функций."""

    def test_full_user_validation(self):
        """Полная валидация данных пользователя."""
        user_data = {
            "name": "иван",
            "surname": "иванов",
            "email": "test@example.com",
            "phone": "+79161234567",
            "birthdate": "15.05.1990",
            "address": "ул. Ленина, д. 10",
            "weight": "70"
        }

        # Валидируем все поля
        validated_data = {
            "name": validate_name(user_data["name"]),
            "surname": validate_surname(user_data["surname"]),
            "email": validate_email(user_data["email"]),
            "phone": validate_phone(user_data["phone"]),
            "birthdate": validate_birthdate(user_data["birthdate"]),
            "address": validate_address(user_data["address"]),
            "weight": validate_weight(user_data["weight"])
        }

        assert validated_data["name"] == "Иван"
        assert validated_data["surname"] == "Иванов"
        assert validated_data["email"] == "test@example.com"
        assert validated_data["phone"] == "+79161234567"
        assert validated_data["birthdate"] == "15.05.1990"
        assert validated_data["address"] == "ул. Ленина, д. 10"
        assert validated_data["weight"] == 70

    def test_booking_validation(self):
        """Валидация данных для бронирования."""
        booking_data = {
            "slot_date": (date.today().replace(day=date.today().day + 1)).strftime("%d.%m.%Y"),
            "slot_time": "14:30",
            "duration": "1:30",
            "amount": "1500.50"
        }

        validated_date = validate_slot_date(booking_data["slot_date"])
        validated_time = validate_slot_time(booking_data["slot_time"])
        validated_duration = validate_excursion_duration(booking_data["duration"])
        validated_amount = validate_amount_rub(booking_data["amount"])

        assert isinstance(validated_date, date)
        assert isinstance(validated_time, time)
        assert validated_duration == 90
        assert validated_amount == 1500


if __name__ == "__main__":
    """Запуск тестов напрямую (для отладки)."""
    pytest.main([__file__, "-v"])
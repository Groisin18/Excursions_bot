"""
Модуль валидаторов
"""

import re
from datetime import datetime, date, time
from typing import Optional, Tuple, Union
from pydantic import EmailStr

from app.utils.logging_config import get_logger


logger = get_logger(__name__)


# ================ ПЕРСОНАЛЬНЫЕ ДАННЫЕ ================

def validate_name(v: str) -> str:
    """Валидация имени"""
    logger.debug(f"Валидация имени | входное значение: '{v}'")

    if not re.match(r'^[A-Za-zА-Яа-яЁё\s\-]+$', v):
        logger.warning("Ошибка валидации имени | недопустимые символы")
        raise ValueError('В имени допустимы только буквы, пробелы и дефисы')

    cleaned = v.strip()
    if len(cleaned) < 1:
        logger.warning("Ошибка валидации имени | слишком короткое значение")
        raise ValueError('Минимальная длина имени - 1 символ')

    if len(cleaned) > 50:
        logger.warning("Ошибка валидации имени | превышена максимальная длина")
        raise ValueError('Максимальная длина имени - 50 символов')

    result = cleaned.title()
    logger.debug(f"Имя успешно валидировано | результат: '{result}'")
    return result


def validate_surname(v: str) -> str:
    """Валидация фамилии"""
    logger.debug(f"Валидация фамилии | входное значение: '{v}'")

    if not re.match(r'^[A-Za-zА-Яа-яЁё\s\-]+$', v):
        logger.warning("Ошибка валидации фамилии | недопустимые символы")
        raise ValueError('В фамилии допустимы только буквы, пробелы и дефисы')

    cleaned = v.strip()
    if len(cleaned) < 1:
        logger.warning("Ошибка валидации фамилии | слишком короткое значение")
        raise ValueError('Минимальная длина фамилии - 1 символ')

    if len(cleaned) > 50:
        logger.warning("Ошибка валидации фамилии | превышена максимальная длина")
        raise ValueError('Максимальная длина фамилии - 50 символов')

    result = cleaned.title()
    logger.debug(f"Фамилия успешно валидирована | результат: '{result}'")
    return result


def validate_address(v: str) -> str:
    """Валидация адреса"""
    logger.debug(f"Валидация адреса | входное значение: '{v}'")

    cleaned = v.strip()

    if len(cleaned) < 5:
        logger.warning("Ошибка валидации адреса | слишком короткий адрес")
        raise ValueError('Минимальная длина адреса - 5 символов')

    if len(cleaned) > 150:
        logger.warning("Ошибка валидации адреса | превышена максимальная длина")
        raise ValueError('Максимальная длина адреса - 150 символов')

    if not re.match(r'^[A-Za-zА-Яа-яЁё0-9\s\-\.,/\(\)]+$', cleaned):
        logger.warning("Ошибка валидации адреса | недопустимые символы")
        raise ValueError('Адрес содержит недопустимые символы')

    if len(cleaned.split()) < 2:
        logger.warning("Ошибка валидации адреса | недостаточно слов")
        raise ValueError('Адрес должен содержать минимум 2 слова')

    logger.debug("Адрес успешно валидирован")
    return cleaned


def validate_birthdate(date_str: str) -> str:
    """Валидация даты рождения"""
    logger.debug(f"Валидация даты | входное значение: '{date_str}'")

    date_str = date_str.strip()
    date_pattern = r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$'
    match = re.match(date_pattern, date_str)

    if not match:
        logger.warning("Ошибка валидации даты | неверный формат")
        raise ValueError('Неверный формат. Ожидается ДД.ММ.ГГГГ или ДД.ММ.ГГ')

    day, month, year = match.groups()

    if len(year) == 2:
        current_year = date.today().year
        century = current_year // 100 * 100
        year_int = int(year)
        if year_int > current_year % 100:
            year = str(century - 100 + year_int)
        else:
            year = str(century + year_int)

    normalized_date = f"{int(day):02d}.{int(month):02d}.{year}"

    try:
        date_obj = datetime.strptime(normalized_date, "%d.%m.%Y").date()
    except ValueError:
        logger.warning("Ошибка валидации даты | некорректная календарная дата")
        raise ValueError('Некорректная дата')

    if date_obj > date.today():
        logger.warning("Ошибка валидации даты | дата в будущем")
        raise ValueError('Дата рождения не может быть в будущем')

    min_date = datetime.strptime('01.01.1926', "%d.%m.%Y").date()
    if date_obj < min_date:
        logger.warning("Ошибка валидации даты | слишком ранняя дата")
        raise ValueError(f'Навряд ли вы родились так рано, аж в {date_obj.year} году')

    result = date_obj.strftime("%d.%m.%Y")
    logger.debug(f"Дата успешно валидирована | результат: '{result}'")
    return result


def validate_weight(v: str) -> int:
    """Валидация веса"""
    logger.debug(f"Валидация веса | входное значение: '{v}'")

    if not v.isdigit():
        logger.warning("Ошибка валидации веса | значение не является числом")
        raise ValueError('Вес должен быть целым числом')

    weight_int = int(v)
    if weight_int < 1 or weight_int > 299:
        logger.warning("Ошибка валидации веса | значение вне допустимого диапазона")
        raise ValueError('Вес должен быть от 1 до 299 кг')

    logger.debug(f"Вес успешно валидирован | результат: {weight_int}")
    return weight_int


# ================ КОНТАКТНЫЕ ДАННЫЕ ================

def validate_phone(v: str) -> str:
    """Валидация телефона"""
    logger.debug(f"Валидация телефона | входное значение: '{v}'")

    phone_patterns = [
        r'^\+7\d{10}$',
        r'^8\d{10}$',
        r'^7\d{10}$',
    ]

    cleaned_phone = re.sub(r'[^\d+]', '', v)

    if cleaned_phone.startswith('8') and len(cleaned_phone) == 11:
        cleaned_phone = '+7' + cleaned_phone[1:]
    elif cleaned_phone.startswith('7') and len(cleaned_phone) == 11:
        cleaned_phone = '+' + cleaned_phone

    if not any(re.match(pattern, cleaned_phone) for pattern in phone_patterns):
        logger.warning("Ошибка валидации телефона | неверный формат номера")
        raise ValueError('Неверный формат номера телефона. Пример: +79161234567')

    logger.debug(f"Телефон успешно валидирован | результат: '{cleaned_phone}'")
    return cleaned_phone


def validate_email(email: str) -> str:
    """Валидация email"""
    logger.debug(f"Валидация email | входное значение: '{email}'")

    try:
        result = str(EmailStr._validate(email))
        logger.debug("Email успешно валидирован")
        return result
    except ValueError:
        logger.warning("Ошибка валидации email | неверный формат")
        raise ValueError("Неверный формат email. Пример: user@example.com")


# ================ БРОНИРОВАНИЕ И СЛОТЫ ================

def validate_slot_date(date_str: str) -> date:
    """Валидация даты для назначения слота/просмотра расписания"""
    logger.debug(f"Валидация даты для назначения слота/просмотра расписания | входное значение: '{date_str}'")

    date_str = date_str.strip()
    date_pattern = r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$'
    match = re.match(date_pattern, date_str)

    if not match:
        logger.warning("Ошибка валидации даты | неверный формат")
        raise ValueError('Неверный формат. Ожидается ДД.ММ.ГГГГ или ДД.ММ.ГГ')

    day, month, year = match.groups()

    if len(year) == 2:
        current_century = date.today().year // 100 * 100
        year_int = int(year)
        year = str(current_century + year_int)

    normalized_date = f"{int(day):02d}.{int(month):02d}.{year}"

    try:
        date_obj = date(year=int(year), month=int(month), day=int(day))
    except ValueError:
        logger.warning("Ошибка валидации даты | некорректная календарная дата")
        raise ValueError('Некорректная дата')

    if date_obj < date.today():
        logger.warning("Ошибка валидации даты | дата в прошлом")
        raise ValueError('Прошедшая дата не подходит')

    logger.debug(f"Дата успешно валидирована | результат: '{normalized_date}'")
    return date_obj


def validate_slot_time(time_str: str) -> time:
    """Валидация времени для назначения слота"""
    logger.debug(f"Валидация времени для назначения слота | входное значение: '{time_str}'")

    time_str = time_str.strip()
    time_pattern = r'^(\d{1,2}):(\d{2})$'
    match = re.match(time_pattern, time_str)

    if not match:
        logger.warning("Ошибка валидации времени | неверный формат")
        raise ValueError('Неверный формат. Ожидается ЧЧ:ММ (например, 1:00, 12:12, 5:30, 17:59)')

    hour, minute = match.groups()
    hour_int = int(hour)
    minute_int = int(minute)

    if hour_int < 0 or hour_int > 23:
        logger.warning(f"Ошибка валидации времени | некорректный час: {hour_int}")
        raise ValueError('Час должен быть в диапазоне от 0 до 23')

    if minute_int < 0 or minute_int > 59:
        logger.warning(f"Ошибка валидации времени | некорректная минута: {minute_int}")
        raise ValueError('Минуты должны быть в диапазоне от 0 до 59')

    normalized_time = f"{hour_int:02d}:{minute_int:02d}"
    result = time(hour=hour_int, minute=minute_int)

    logger.debug(f"Время успешно валидировано | результат: '{normalized_time}'")
    return result


def validate_excursion_duration(v: str) -> int:
    """Валидация продолжительности экскурсии"""
    logger.debug(f"Валидация продолжительности экскурсии | входное значение: '{v}'")

    v = v.strip()
    if not v:
        logger.warning("Ошибка валидации продолжительности | пустой ввод")
        raise ValueError(
            '📝 Введите продолжительность экскурсии.\n'
            'Форматы:\n'
            '• 90 (только минуты)\n'
            '• 1:30 (часы:минуты)\n'
            '• 2 45 (часы минуты)\n'
            '• 1.30 (часы.минуты)\n'
            '• 1,15 (часы,минуты)'
        )

    separators = [' ', ':', '-', '.', ',']
    normalized = v
    for sep in separators:
        normalized = normalized.replace(sep, ':')
    while '::' in normalized:
        normalized = normalized.replace('::', ':')

    parts = normalized.split(':')
    parts = [part for part in parts if part]

    if len(parts) == 1:
        if not parts[0].isdigit():
            logger.warning("Ошибка валидации продолжительности | некорректные минуты")
            raise ValueError('Допустимы только цифры и разделители (.,-: )')
        minutes = int(parts[0])

    elif len(parts) == 2:
        hours_str, minutes_str = parts

        if not hours_str.isdigit():
            logger.warning("Ошибка валидации продолжительности | часы не число")
            raise ValueError(f'Часы "{hours_str}" должны быть числом')

        if not minutes_str.isdigit():
            logger.warning("Ошибка валидации продолжительности | минуты не число")
            raise ValueError(f'Минуты "{minutes_str}" должны быть числом')

        hours = int(hours_str)
        minutes_val = int(minutes_str)

        if hours < 0:
            logger.warning("Ошибка валидации продолжительности | отрицательные часы")
            raise ValueError('Часы не могут быть отрицательными')

        if hours > 48:
            logger.warning("Ошибка валидации продолжительности | слишком большое количество часов")
            raise ValueError('Максимально - 48 часов')

        if minutes_val < 0 or minutes_val >= 60:
            logger.warning("Ошибка валидации продолжительности | минуты вне диапазона")
            raise ValueError('Минуты должны быть от 00 до 59')

        if len(minutes_str) == 1:
            minutes_val = int(minutes_str) * 10

        minutes = hours * 60 + minutes_val

    else:
        logger.warning("Ошибка валидации продолжительности | неверный формат ввода")
        raise ValueError(
            'Неверный формат. Используйте один разделитель.\n'
            'Примеры:\n'
            '• 90\n'
            '• 1:30\n'
            '• 2 45\n'
            '• 4-55\n'
            '• 1.15'
        )

    if minutes < 10:
        logger.warning("Ошибка валидации продолжительности | слишком короткая экскурсия")
        raise ValueError('Экскурсия должна длиться не менее 10 минут')

    if minutes > 2880:
        logger.warning("Ошибка валидации продолжительности | превышена максимальная длительность")
        raise ValueError('Экскурсия не должна превышать 48 часов (2880 минут)')

    if minutes % 10 != 0:
        lower = minutes // 10 * 10
        upper = lower + 10
        logger.warning("Ошибка валидации продолжительности | значение не кратно 10 минутам")
        raise ValueError(
            f'Продолжительность должна быть кратной 10 минутам.\n'
            f'Ваш ввод: {minutes} минут\n'
            f'Ближайшие значения: {lower} или {upper} минут'
        )

    logger.debug(f"Продолжительность экскурсии успешно валидирована | {minutes} минут")
    return minutes


# ================ ФИНАНСОВЫЕ ОПЕРАЦИИ ================

def validate_amount_rub(v: Union[str, int, float]) -> int:
    """Валидация суммы в рублях"""
    logger.debug(f"Валидация суммы | входное значение: '{v}'")

    if v is None:
        logger.warning("Ошибка валидации суммы | значение отсутствует")
        raise ValueError('Введите сумму')

    if isinstance(v, (int, float)):
        amount = float(v)
    else:
        v_str = str(v).strip()
        if not v_str:
            logger.warning("Ошибка валидации суммы | пустая строка")
            raise ValueError('Введите сумму')

        v_clean = v_str.upper()
        for remove in [
            'RUB', 'РУБ', 'Р', 'R', '₽', 'RUB.', 'РУБ.', 'Р.', 'R.',
            'РУБЛЕЙ', 'РУБЛЯ', 'руб', 'руб.', 'рубль', 'рубля', 'рублей'
        ]:
            v_clean = v_clean.replace(remove, '')

        v_clean = v_clean.strip()

        if ',' in v_clean and '.' in v_clean:
            parts = v_clean.split(',')
            integer_part = parts[0].replace('.', '')
            v_clean = integer_part + '.' + parts[1]
        elif ',' in v_clean:
            if v_clean.count(',') == 1 and len(v_clean.split(',')[1]) <= 2:
                v_clean = v_clean.replace(',', '.')
            else:
                v_clean = v_clean.replace(',', '')
        else:
            if '.' in v_clean:
                parts = v_clean.split('.')
                if not (len(parts) == 2 and len(parts[1]) <= 2):
                    v_clean = v_clean.replace('.', '')

        v_clean = v_clean.replace(' ', '')

        if not re.match(r'^\d+(\.\d{1,2})?$', v_clean):
            logger.warning("Ошибка валидации суммы | неверный формат")
            raise ValueError(
                'Неверный формат суммы. Используйте числа.\n'
                'Примеры: 1000, 1 000, 1500.50, 2 000,00'
            )

        try:
            amount = float(v_clean)
        except ValueError:
            logger.warning("Ошибка валидации суммы | не удалось преобразовать в число")
            raise ValueError('Не удалось преобразовать в число. Проверьте формат суммы')

    if amount < 1:
        logger.warning("Ошибка валидации суммы | сумма меньше 1 рубля")
        raise ValueError('Минимальная сумма - 1 рубль')

    if amount > 20000:
        logger.warning("Ошибка валидации суммы | превышен лимит")
        raise ValueError('Максимальная сумма - 20 000 рублей')

    amount_rub = round(amount)

    if amount_rub < 1:
        amount_rub = 1
    elif amount_rub > 20000:
        logger.warning("Ошибка валидации суммы | превышение лимита после округления")
        raise ValueError('Сумма превышает 20 000 рублей после округления')

    logger.debug(f"Сумма успешно валидирована | результат: {amount_rub} руб.")
    return amount_rub


def validate_discount(v: Union[str, int]) -> int:
    """Валидация скидки"""
    logger.debug(f"Валидация скидки | входное значение: '{v}'")

    if v is None:
        logger.warning("Ошибка валидации скидки | значение отсутствует")
        raise ValueError('Введите размер скидки')

    if isinstance(v, int):
        discount = v
    else:
        v_str = str(v).strip()
        if not v_str:
            logger.warning("Ошибка валидации скидки | пустая строка")
            raise ValueError('Введите размер скидки')

        v_clean = re.sub(r'[^\d\-]', '', v_str)

        if not v_clean or v_clean == '-':
            logger.warning("Ошибка валидации скидки | некорректное значение")
            raise ValueError('Введите целое число от 0 до 100')

        try:
            discount = int(v_clean)
        except ValueError:
            logger.warning("Ошибка валидации скидки | ошибка преобразования в число")
            raise ValueError('Введите целое число')

    if discount < 0:
        logger.warning("Ошибка валидации скидки | отрицательное значение")
        raise ValueError('Скидка не может быть отрицательной')

    if discount > 100:
        logger.warning("Ошибка валидации скидки | превышение 100%")
        raise ValueError('Скидка не может превышать 100%')

    logger.debug(f"Скидка успешно валидирована | результат: {discount}%")
    return discount


# ================ РАЗНОЕ ================

def generate_virtual_phone(parent_phone: str, token_suffix: str) -> str:
    """Генерация виртуального номера"""
    logger.debug(
        f"Генерация виртуального номера | родительский: '{parent_phone}', суффикс токена: '{token_suffix}'"
    )
    return f"{parent_phone}:{token_suffix}:child"


def parse_virtual_phone(virtual_phone: str) -> Tuple[Optional[str], Optional[str]]:
    """Парсинг виртуального номера"""
    logger.debug(f"Парсинг виртуального номера | входное значение: '{virtual_phone}'")

    parts = virtual_phone.split(":")
    if len(parts) == 3 and parts[2] == "child":
        logger.debug("Виртуальный номер успешно распознан")
        return parts[0], parts[1]

    logger.warning("Ошибка парсинга виртуального номера | неверный формат")
    return None, None


def validate_token_format(token: str) -> bool:
    """Валидация формата токена"""
    logger.debug(f"Валидация формата токена | входное значение: '{token}'")

    pattern = r'^[A-Za-z0-9_-]{32,}$'
    result = bool(re.match(pattern, token))

    logger.debug(f"Результат проверки формата токена: {result}")
    return result


def validate_promocode(code: str) -> str:
    """Валидация промокода"""
    logger.debug(f"Валидация промокода | входное значение: '{code}'")

    cleaned_code = code.strip().upper()

    logger.debug(f"Очищенный промокод: '{cleaned_code}'")

    if len(cleaned_code) < 4:
        logger.warning(f"Промокод слишком короткий: {len(cleaned_code)} символов")
        raise ValueError('Код промокода должен содержать минимум 4 символа')

    if len(cleaned_code) > 20:
        logger.warning(f"Промокод слишком длинный: {len(cleaned_code)} символов")
        raise ValueError('Код промокода должен содержать максимум 20 символов')

    pattern = r'^[A-Z0-9]+$'

    if not re.match(pattern, cleaned_code):
        logger.warning(f"Промокод содержит недопустимые символы: '{cleaned_code}'")
        raise ValueError(
            'Код промокода может содержать только:\n'
            '• Большие латинские буквы (A-Z)\n'
            '• Цифры (0-9)\n\n'
            'Примеры: SUMMER2024, WELCOME10, BLACKFRIDAY'
        )

    if cleaned_code.isdigit():
        logger.warning(f"Промокод состоит только из цифр: '{cleaned_code}'")
        raise ValueError('Промокод не может состоять только из цифр')

    logger.info(f"Промокод успешно валидирован: '{cleaned_code}'")
    return cleaned_code


# ================ PYDANTIC ВАЛИДАТОРЫ ================

def pydantic_validate_name(v: str) -> str:
    """Pydantic валидатор для имени"""
    return validate_name(v)


def pydantic_validate_surname(v: str) -> str:
    """Pydantic валидатор для фамилии"""
    return validate_surname(v)


def pydantic_validate_email(v: str) -> str:
    """Pydantic валидатор для email"""
    return validate_email(v)


def pydantic_validate_phone(v: str) -> str:
    """Pydantic валидатор для телефона"""
    return validate_phone(v)


def pydantic_validate_birthdate(v: str) -> str:
    """Pydantic валидатор для даты рождения"""
    return validate_birthdate(v)
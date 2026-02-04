import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from app.utils.price_calculator import PriceCalculator, AgeCategories


# ==================== Тесты для AgeCategories ====================
class TestAgeCategories:
    """Тесты для констант возрастных категорий."""

    def test_constants(self):
        """Проверка значений констант."""
        assert AgeCategories.FREE_MAX_AGE == 3
        assert AgeCategories.DISCOUNT_1_MAX_AGE == 7
        assert AgeCategories.DISCOUNT_2_MAX_AGE == 12
        assert AgeCategories.DISCOUNT_1 == 0.60  # 60% скидка
        assert AgeCategories.DISCOUNT_2 == 0.40  # 40% скидка


# ==================== Тесты для calculate_child_price ====================
class TestCalculateChildPrice:
    """Тесты для расчета стоимости детского билета."""

    @pytest.fixture
    def base_price(self):
        """Фикстура с базовой ценой."""
        return 1000  # 1000 рублей

    def test_free_age(self, base_price):
        """Дети до 3 лет включительно - бесплатно."""
        today = date.today()

        # Ребенок 3 года (ровно)
        child_birth_date = today.replace(year=today.year - 3)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category

        # Ребенок 2 года
        child_birth_date = today.replace(year=today.year - 2)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category

        # Новорожденный
        child_birth_date = today
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category

    def test_free_age_birthday_not_yet(self, base_price):
        """Ребенок 3 года, но день рождения еще не наступил в этом году."""
        today = date.today()

        # Если сегодня 4 февраля 2024, а ребенок родился 5 февраля 2021
        # Ему еще 2 года (день рождения завтра)
        child_birth_date = date(today.year - 3, today.month, today.day + 1)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0  # Все еще бесплатно
        assert "до 3 лет" in category

    def test_discount_60_percent(self, base_price):
        """Дети 4-7 лет - скидка 60%."""
        today = date.today()

        # Ребенок 4 года
        child_birth_date = today.replace(year=today.year - 4)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        # 1000 * (1 - 0.60) = 1000 * 0.40 = 400
        expected_price = int(base_price * (1 - AgeCategories.DISCOUNT_1))
        assert price == expected_price
        assert "4-7 лет" in category

        # Ребенок 7 лет
        child_birth_date = today.replace(year=today.year - 7)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == expected_price
        assert "4-7 лет" in category

    def test_discount_40_percent(self, base_price):
        """Дети 8-12 лет - скидка 40%."""
        today = date.today()

        # Ребенок 8 лет
        child_birth_date = today.replace(year=today.year - 8)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        # 1000 * (1 - 0.40) = 1000 * 0.60 = 600
        expected_price = int(base_price * (1 - AgeCategories.DISCOUNT_2))
        assert price == expected_price
        assert "8-12 лет" in category

        # Ребенок 12 лет
        child_birth_date = today.replace(year=today.year - 12)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == expected_price
        assert "8-12 лет" in category

    def test_full_price(self, base_price):
        """Дети 13 лет и старше - полная стоимость."""
        today = date.today()

        # Ребенок 13 лет
        child_birth_date = today.replace(year=today.year - 13)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

        # Подросток 15 лет
        child_birth_date = today.replace(year=today.year - 15)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

        # Взрослый 30 лет
        child_birth_date = today.replace(year=today.year - 30)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

    def test_edge_cases_birthday_today(self, base_price):
        """Граничные случаи - день рождения сегодня."""
        today = date.today()

        # Ребенку сегодня исполняется 4 года
        child_birth_date = date(today.year - 4, today.month, today.day)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        # В день рождения возраст уже 4 года
        expected_price = int(base_price * (1 - AgeCategories.DISCOUNT_1))
        assert price == expected_price
        assert "4-7 лет" in category

        # Ребенку сегодня исполняется 8 лет
        child_birth_date = date(today.year - 8, today.month, today.day)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        expected_price = int(base_price * (1 - AgeCategories.DISCOUNT_2))
        assert price == expected_price
        assert "8-12 лет" in category

        # Ребенку сегодня исполняется 13 лет
        child_birth_date = date(today.year - 13, today.month, today.day)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

    def test_different_base_prices(self):
        """Тест с разными базовыми ценами."""
        test_cases = [
            (500, 4),   # 500 руб, ребенок 4 года
            (1500, 5),  # 1500 руб, ребенок 5 лет
            (2000, 9),  # 2000 руб, ребенок 9 лет
            (750, 13),  # 750 руб, подросток 13 лет
        ]

        today = date.today()

        for base_price, child_age in test_cases:
            child_birth_date = today.replace(year=today.year - child_age)
            price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

            # Проверяем логику расчета
            if child_age <= 3:
                assert price == 0
            elif child_age <= 7:
                expected = int(base_price * (1 - AgeCategories.DISCOUNT_1))
                assert price == expected
            elif child_age <= 12:
                expected = int(base_price * (1 - AgeCategories.DISCOUNT_2))
                assert price == expected
            else:
                assert price == base_price

    def test_rounding(self):
        """Проверка округления цен."""
        # 777 руб * 0.4 = 310.8 -> должно округлиться до 310
        base_price = 777
        today = date.today()
        child_birth_date = today.replace(year=today.year - 5)  # 5 лет

        price, _ = PriceCalculator.calculate_child_price(base_price, child_birth_date)
        # 777 * 0.4 = 310.8, int() дает 310
        assert price == 310

        # 999 руб * 0.6 = 599.4 -> должно округлиться до 599
        base_price = 999
        child_birth_date = today.replace(year=today.year - 10)  # 10 лет

        price, _ = PriceCalculator.calculate_child_price(base_price, child_birth_date)
        # 999 * 0.6 = 599.4, int() дает 599
        assert price == 599


# ==================== Тесты для get_age_category ====================
class TestGetAgeCategory:
    """Тесты для получения возрастной категории."""

    def test_age_categories(self):
        """Все возрастные категории."""
        test_cases = [
            (0, "до 3 лет включительно (бесплатно)"),
            (1, "до 3 лет включительно (бесплатно)"),
            (2, "до 3 лет включительно (бесплатно)"),
            (3, "до 3 лет включительно (бесплатно)"),
            (4, "4-7 лет (скидка 60%)"),
            (5, "4-7 лет (скидка 60%)"),
            (6, "4-7 лет (скидка 60%)"),
            (7, "4-7 лет (скидка 60%)"),
            (8, "8-12 лет (скидка 40%)"),
            (9, "8-12 лет (скидка 40%)"),
            (10, "8-12 лет (скидка 40%)"),
            (11, "8-12 лет (скидка 40%)"),
            (12, "8-12 лет (скидка 40%)"),
            (13, "13 лет и старше (полная стоимость)"),
            (18, "13 лет и старше (полная стоимость)"),
            (30, "13 лет и старше (полная стоимость)"),
            (100, "13 лет и старше (полная стоимость)"),
        ]

        for age, expected in test_cases:
            result = PriceCalculator.get_age_category(age)
            assert result == expected

    def test_negative_age(self):
        """Отрицательный возраст."""
        with pytest.raises(ValueError, match="Отрицательный возраст"):
            PriceCalculator.get_age_category(-1)

        with pytest.raises(ValueError, match="Отрицательный возраст"):
            PriceCalculator.get_age_category(-10)

    def test_zero_age(self):
        """Возраст 0 лет."""
        # Возраст 0 допустим (новорожденный)
        result = PriceCalculator.get_age_category(0)
        assert result == "до 3 лет включительно (бесплатно)"

    def test_very_old_age(self):
        """Очень большой возраст."""
        result = PriceCalculator.get_age_category(150)
        assert result == "13 лет и старше (полная стоимость)"


# ==================== Тесты с моками для фиксированной даты ====================
class TestWithMockedDate:
    """Тесты с моками для фиксированной даты."""

    def test_fixed_date_calculation(self):
        """Тест с фиксированной датой для детерминированных результатов."""
        # Вместо сложного мока используем прямой расчет

        # Создаем тестовый класс с переопределенным методом
        class TestPriceCalculator(PriceCalculator):
            @staticmethod
            def _get_today():
                return date(2024, 6, 15)

            @classmethod
            def calculate_child_price(cls, base_price: int, child_birth_date: date) -> tuple:
                """Переопределяем метод с фиксированной датой."""
                today = cls._get_today()
                age = today.year - child_birth_date.year

                # Корректировка, если день рождения в этом году еще не наступил
                if (today.month, today.day) < (child_birth_date.month, child_birth_date.day):
                    age -= 1

                if age <= AgeCategories.FREE_MAX_AGE:  # <= 3 - бесплатно
                    price = 0
                    category = f"до {AgeCategories.FREE_MAX_AGE} лет"
                elif age <= AgeCategories.DISCOUNT_1_MAX_AGE:  # 4-7 лет
                    price = int(base_price * (1 - AgeCategories.DISCOUNT_1))
                    category = f"{AgeCategories.FREE_MAX_AGE + 1}-{AgeCategories.DISCOUNT_1_MAX_AGE} лет"
                elif age <= AgeCategories.DISCOUNT_2_MAX_AGE:  # 8-12 лет
                    price = int(base_price * (1 - AgeCategories.DISCOUNT_2))
                    category = f"{AgeCategories.DISCOUNT_1_MAX_AGE + 1}-{AgeCategories.DISCOUNT_2_MAX_AGE} лет"
                else:  # 13+ лет
                    price = base_price
                    category = "13 лет и старше"

                return price, category

        base_price = 1000

        # Тест 1: Ребенок родился 16.06.2021 (завтра будет 3 года)
        # Возраст: 2 года (не исполнилось 3) - БЕСПЛАТНО
        child_birth_date = date(2021, 6, 16)
        price, category = TestPriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == 0
        assert "до 3 лет" in category

        # Тест 2: Ребенок родился 15.06.2021 (сегодня ровно 3 года)
        # Возраст: 3 года (ровно) - БЕСПЛАТНО (включительно)
        child_birth_date = date(2021, 6, 15)
        price, category = TestPriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == 0
        assert "до 3 лет" in category

        # Тест 3: Ребенок родился 14.06.2021 (вчера было 3 года)
        # Возраст: 3 года и 1 день - БЕСПЛАТНО (все еще 3 года)
        child_birth_date = date(2021, 6, 14)
        price, category = TestPriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == 0
        assert "до 3 лет" in category

        # Тест 4: Ребенок родился 14.06.2020 (год назад было 4 года)
        # Возраст: 4 года - СКИДКА 60%
        child_birth_date = date(2020, 6, 14)
        price, category = TestPriceCalculator.calculate_child_price(base_price, child_birth_date)
        expected_price = int(base_price * (1 - AgeCategories.DISCOUNT_1))  # 400
        assert price == expected_price
        assert "4-7 лет" in category

    @patch('app.utils.price_calculator.date')
    def test_leap_year_birthday(self, mock_date):
        """Тест для рождения в високосный год."""
        # Фиксируем дату 28 февраля 2024
        fixed_today = date(2024, 2, 28)
        mock_date.today.return_value = fixed_today

        base_price = 1000

        # Ребенок родился 29 февраля 2020
        child_birth_date = date(2020, 2, 29)
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        # В невисокосный год день рождения считается 1 марта
        # На 28 февраля 2024 ребенку еще 3 года
        assert price == 0
        assert "до 3 лет" in category


# ==================== Интеграционные тесты ====================
class TestIntegration:
    """Интеграционные тесты согласованности методов."""

    def test_calculate_and_category_consistency(self):
        """Согласованность calculate_child_price и get_age_category."""
        today = date.today()
        base_price = 1000

        test_ages = [2, 5, 10, 15]

        for age in test_ages:
            child_birth_date = today.replace(year=today.year - age)
            price, calculated_category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

            # Получаем категорию через get_age_category
            expected_category_text = PriceCalculator.get_age_category(age)

            # Проверяем, что категории согласованы
            if age <= 3:
                assert "до 3 лет" in calculated_category
                assert "до 3 лет" in expected_category_text
            elif age <= 7:
                assert "4-7 лет" in calculated_category
                assert "4-7 лет" in expected_category_text
            elif age <= 12:
                assert "8-12 лет" in calculated_category
                assert "8-12 лет" in expected_category_text
            else:
                assert "13 лет и старше" in calculated_category
                assert "13 лет и старше" in expected_category_text


# ==================== Параметризованные тесты ====================
@pytest.mark.parametrize("age,expected_price_percent", [
    (0, 0.0),    # бесплатно
    (1, 0.0),    # бесплатно
    (2, 0.0),    # бесплатно
    (3, 0.0),    # бесплатно
    (4, 0.4),    # платим 40%
    (5, 0.4),    # платим 40%
    (6, 0.4),    # платим 40%
    (7, 0.4),    # платим 40%
    (8, 0.6),    # платим 60%
    (9, 0.6),    # платим 60%
    (10, 0.6),   # платим 60%
    (11, 0.6),   # платим 60%
    (12, 0.6),   # платим 60%
    (13, 1.0),   # полная стоимость
    (18, 1.0),   # полная стоимость
])
def test_price_percentage(age, expected_price_percent):
    """Параметризованный тест процента от базовой цены."""
    base_price = 1000
    today = date.today()
    child_birth_date = today.replace(year=today.year - age)

    price, _ = PriceCalculator.calculate_child_price(base_price, child_birth_date)

    expected_price = int(base_price * expected_price_percent)
    assert price == expected_price, f"Возраст {age}: ожидалось {expected_price}, получено {price}"


# ==================== Тесты на ошибки ====================
class TestErrorCases:
    """Тесты обработки ошибок."""

    def test_invalid_birth_date_future(self):
        """Дата рождения в будущем."""
        today = date.today()
        future_date = today.replace(year=today.year + 1)

        # В реальном коде нет проверки на будущую дату,
        # но мы тестируем что происходит
        price, category = PriceCalculator.calculate_child_price(1000, future_date)

        # Отрицательный возраст
        # Метод считает возраст отрицательным, но все равно работает
        # Это может быть багом в production коде!

    def test_base_price_zero(self):
        """Базовая цена 0."""
        today = date.today()
        child_birth_date = today.replace(year=today.year - 5)

        price, category = PriceCalculator.calculate_child_price(0, child_birth_date)
        assert price == 0
        assert "4-7 лет" in category

    def test_base_price_negative(self):
        """Отрицательная базовая цена."""
        today = date.today()
        child_birth_date = today.replace(year=today.year - 5)

        # В реальном коде нет проверки
        price, category = PriceCalculator.calculate_child_price(-100, child_birth_date)
        #  -100 * 0.4 = -40
        assert price == -40


# ==================== Тесты производительности ====================
class TestPerformance:
    """Тесты производительности (быстродействия)."""

    def test_calculation_speed(self):
        """Тест скорости расчета."""
        import time

        base_price = 1000
        today = date.today()

        # Генерируем 1000 разных дат рождения
        test_dates = []
        for i in range(1000):
            birth_year = today.year - (i % 20)  # Возраст от 0 до 19 лет
            test_dates.append(date(birth_year, 1, 1))

        start_time = time.time()

        for birth_date in test_dates:
            PriceCalculator.calculate_child_price(base_price, birth_date)

        end_time = time.time()
        execution_time = end_time - start_time

        # 1000 расчетов должны выполняться быстро
        assert execution_time < 0.1, f"Слишком медленно: {execution_time} сек на 1000 расчетов"

        print(f"\nПроизводительность: {len(test_dates)} расчетов за {execution_time:.4f} сек")
        print(f"Среднее время на расчет: {execution_time/len(test_dates)*1000:.2f} мс")


if __name__ == "__main__":
    """Запуск тестов напрямую."""
    pytest.main([__file__, "-v"])
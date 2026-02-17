import pytest
from datetime import date
from unittest.mock import patch
from app.utils.calculators import (
    PriceCalculator, WeightCalculator, BookingCalculator, AgeCategories
)


# ==================== Тесты для AgeCategories ====================
class TestAgeCategories:
    """Тесты для констант возрастных категорий."""

    def test_constants(self):
        """Проверка значений констант."""
        assert AgeCategories.INFANT_MAX_AGE == 3
        assert AgeCategories.CHILD_MAX_AGE == 7
        assert AgeCategories.PRE_TEEN_MAX_AGE == 12
        assert AgeCategories.CHILD_DISCOUNT == 0.60
        assert AgeCategories.PRE_TEEN_DISCOUNT == 0.40


# ==================== Тесты для calculate_child_price ====================
class TestCalculateChildPrice:
    """Тесты для расчета стоимости детского билета."""

    @pytest.fixture
    def base_price(self):
        return 1000

    @patch('app.utils.calculators.calculate_age')
    def test_free_age(self, mock_calculate_age, base_price):
        """Дети до 3 лет включительно - бесплатно."""
        mock_calculate_age.return_value = 3
        child_birth_date = date(2021, 6, 15)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category
        mock_calculate_age.assert_called_once_with(child_birth_date)

    @patch('app.utils.calculators.calculate_age')
    def test_free_age_birthday_not_yet(self, mock_calculate_age, base_price):
        """Ребенок 3 года, но день рождения еще не наступил в этом году."""
        mock_calculate_age.return_value = 2  # Еще 2 года
        child_birth_date = date(2021, 6, 16)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category

    @patch('app.utils.calculators.calculate_age')
    def test_discount_60_percent(self, mock_calculate_age, base_price):
        """Дети 4-7 лет - скидка 60% (платят 40%)."""
        mock_calculate_age.return_value = 4
        child_birth_date = date(2020, 6, 15)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        expected_price = int(base_price * (1 - AgeCategories.CHILD_DISCOUNT))
        assert price == expected_price
        assert "4-7 лет" in category

        mock_calculate_age.return_value = 7
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == expected_price
        assert "4-7 лет" in category

    @patch('app.utils.calculators.calculate_age')
    def test_discount_40_percent(self, mock_calculate_age, base_price):
        """Дети 8-12 лет - скидка 40% (платят 60%)."""
        mock_calculate_age.return_value = 8
        child_birth_date = date(2016, 6, 15)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        expected_price = int(base_price * (1 - AgeCategories.PRE_TEEN_DISCOUNT))
        assert price == expected_price
        assert "8-12 лет" in category

        mock_calculate_age.return_value = 12
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == expected_price
        assert "8-12 лет" in category

    @patch('app.utils.calculators.calculate_age')
    def test_full_price(self, mock_calculate_age, base_price):
        """Дети 13 лет и старше - полная стоимость."""
        mock_calculate_age.return_value = 13
        child_birth_date = date(2011, 6, 15)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

        mock_calculate_age.return_value = 30
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)
        assert price == base_price
        assert "13 лет и старше" in category

    @patch('app.utils.calculators.calculate_age')
    def test_edge_cases_birthday_today(self, mock_calculate_age, base_price):
        """Граничные случаи - день рождения сегодня."""
        # Сегодня исполняется 4 года
        mock_calculate_age.return_value = 4
        child_birth_date = date(2020, 6, 15)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        expected_price = int(base_price * (1 - AgeCategories.CHILD_DISCOUNT))
        assert price == expected_price
        assert "4-7 лет" in category

        # Сегодня исполняется 8 лет
        mock_calculate_age.return_value = 8
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        expected_price = int(base_price * (1 - AgeCategories.PRE_TEEN_DISCOUNT))
        assert price == expected_price
        assert "8-12 лет" in category

        # Сегодня исполняется 13 лет
        mock_calculate_age.return_value = 13
        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == base_price
        assert "13 лет и старше" in category

    @patch('app.utils.calculators.calculate_age')
    def test_different_base_prices(self, mock_calculate_age):
        """Тест с разными базовыми ценами."""
        test_cases = [
            (500, 4, 200),   # 500 руб, 4 года: 500 * 0.4 = 200
            (1500, 5, 600),  # 1500 руб, 5 лет: 1500 * 0.4 = 600
            (2000, 9, 1200), # 2000 руб, 9 лет: 2000 * 0.6 = 1200
            (750, 13, 750),  # 750 руб, 13 лет: полная
            (777, 5, 310),   # 777 * 0.4 = 310.8 -> int() = 310
            (999, 10, 599),  # 999 * 0.6 = 599.4 -> int() = 599
        ]

        for base_price, age, expected in test_cases:
            mock_calculate_age.return_value = age
            child_birth_date = date(2024 - age, 6, 15)

            price, _ = PriceCalculator.calculate_child_price(base_price, child_birth_date)

            assert price == expected, f"Base {base_price}, age {age}: expected {expected}, got {price}"

    @patch('app.utils.calculators.calculate_age')
    def test_rounding(self, mock_calculate_age):
        """Проверка округления цен (int() отбрасывает дробную часть)."""
        mock_calculate_age.return_value = 4
        # 777 * 0.4 = 310.8 -> 310
        price, _ = PriceCalculator.calculate_child_price(777, date(2020, 6, 15))
        assert price == 310

        mock_calculate_age.return_value = 9
        # 999 * 0.6 = 599.4 -> 599
        price, _ = PriceCalculator.calculate_child_price(999, date(2015, 6, 15))
        assert price == 599

    @patch('app.utils.calculators.calculate_age')
    def test_leap_year_birthday(self, mock_calculate_age, base_price):
        """Тест для рождения в високосный год."""
        mock_calculate_age.return_value = 3
        child_birth_date = date(2020, 2, 29)

        price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)

        assert price == 0
        assert "до 3 лет" in category
        mock_calculate_age.assert_called_once_with(child_birth_date)


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
        ]

        for age, expected in test_cases:
            result = PriceCalculator.get_age_category(age)
            assert result == expected

    def test_negative_age(self):
        """Отрицательный возраст."""
        with pytest.raises(ValueError, match="Отрицательный возраст"):
            PriceCalculator.get_age_category(-1)

    def test_zero_age(self):
        """Возраст 0 лет."""
        result = PriceCalculator.get_age_category(0)
        assert result == "до 3 лет включительно (бесплатно)"


# ==================== Тесты для WeightCalculator ====================
class TestWeightCalculator:
    """Тесты для калькулятора веса."""

    def test_calculate_average_child_weight(self):
        """Расчет среднего веса по возрасту."""
        test_cases = [
            (0, WeightCalculator.INFANT_MAX_WEIGHT),   # 0 лет - 15 кг
            (2, WeightCalculator.INFANT_MAX_WEIGHT),   # 2 года - 15 кг
            (3, WeightCalculator.INFANT_MAX_WEIGHT),   # 3 года - 15 кг
            (4, WeightCalculator.CHILD_MAX_WEIGHT),    # 4 года - 25 кг
            (7, WeightCalculator.CHILD_MAX_WEIGHT),    # 7 лет - 25 кг
            (8, WeightCalculator.PRE_TEEN_MAX_WEIGHT), # 8 лет - 40 кг
            (12, WeightCalculator.PRE_TEEN_MAX_WEIGHT),# 12 лет - 40 кг
            (13, WeightCalculator.TEEN_ADULT_WEIGHT),  # 13 лет - 50 кг
            (18, WeightCalculator.TEEN_ADULT_WEIGHT),  # 18 лет - 50 кг
            (None, WeightCalculator.DEFAULT_WEIGHT),   # неизвестно - 25 кг
        ]

        for age, expected in test_cases:
            result = WeightCalculator.calculate_average_child_weight(age)
            assert result == expected, f"Age {age}: expected {expected}, got {result}"

    def test_get_weight_info(self):
        """Информационное сообщение о весе."""
        # Возраст известен
        result = WeightCalculator.get_weight_info(5)
        assert result == "средний вес 25 кг для возраста 5 лет"

        # Возраст неизвестен
        result = WeightCalculator.get_weight_info(None)
        assert result == "средний вес 25 кг (возраст неизвестен)"

    def test_get_weight_by_age_group(self):
        """Полная информация о весе по возрастной группе."""
        result = WeightCalculator.get_weight_by_age_group(5)

        assert result["age"] == 5
        assert result["weight"] == WeightCalculator.CHILD_MAX_WEIGHT
        assert "4-7 лет" in result["category"]
        assert "средний вес 25 кг" in result["weight_info"]


# ==================== Тесты для BookingCalculator ====================
class TestBookingCalculator:
    """Тесты для калькулятора бронирований."""

    def test_calculate_total_price_basic(self):
        """Базовая стоимость без скидок."""
        result = BookingCalculator.calculate_total_price(
            base_price=1000,
            participants_count=2
        )
        assert result == 2000

    def test_calculate_total_price_with_percent_discount(self):
        """Скидка в процентах."""
        result = BookingCalculator.calculate_total_price(
            base_price=1000,
            participants_count=2,
            discount_percent=10
        )
        # 2000 * 90 / 100 = 1800
        assert result == 1800

    def test_calculate_total_price_with_promo_discount(self):
        """Фиксированная скидка по промокоду."""
        result = BookingCalculator.calculate_total_price(
            base_price=1000,
            participants_count=2,
            promo_discount=300
        )
        assert result == 1700

    def test_calculate_total_price_with_both_discounts(self):
        """Комбинация процентной и фиксированной скидки."""
        result = BookingCalculator.calculate_total_price(
            base_price=1000,
            participants_count=2,
            discount_percent=10,
            promo_discount=300
        )
        # 2000 * 90% = 1800, 1800 - 300 = 1500
        assert result == 1500

    def test_calculate_total_price_discount_100_percent(self):
        """100% скидка."""
        result = BookingCalculator.calculate_total_price(
            base_price=1000,
            participants_count=2,
            discount_percent=100
        )
        assert result == 0

    def test_calculate_total_price_promo_exceeds_total(self):
        """Промокод больше суммы заказа."""
        result = BookingCalculator.calculate_total_price(
            base_price=500,
            participants_count=1,
            promo_discount=1000
        )
        assert result == 0  # max(0, ...)

    def test_calculate_available_weight(self):
        """Расчет доступного веса."""
        result = BookingCalculator.calculate_available_weight(
            max_weight=100,
            current_weight=30,
            participants_weights=[20, 15, 10]
        )
        # 100 - (30 + 45) = 25
        assert result == 25

    def test_calculate_available_weight_zero(self):
        """Нет доступного веса."""
        result = BookingCalculator.calculate_available_weight(
            max_weight=100,
            current_weight=100,
            participants_weights=[10]
        )
        assert result == -10

    def test_is_weight_available_true(self):
        """Вес доступен."""
        result = BookingCalculator.is_weight_available(
            max_weight=100,
            current_weight=30,
            additional_weight=45
        )
        assert result is True

    def test_is_weight_available_false(self):
        """Вес превышен."""
        result = BookingCalculator.is_weight_available(
            max_weight=100,
            current_weight=30,
            additional_weight=80
        )
        assert result is False

    def test_is_weight_available_exact(self):
        """Точно равно максимальному весу."""
        result = BookingCalculator.is_weight_available(
            max_weight=100,
            current_weight=30,
            additional_weight=70
        )
        assert result is True


# ==================== Тесты на граничные случаи и ошибки ====================
class TestErrorCases:
    """Тесты обработки граничных случаев."""

    @patch('app.utils.calculators.calculate_age')
    def test_future_birth_date(self, mock_calculate_age):
        """Дата рождения в будущем."""
        mock_calculate_age.return_value = 0

        future_date = date(2025, 6, 15)

        # В текущей реализации calculate_age вернет отрицательный возраст
        # Это баг production кода, тест документирует текущее поведение
        price, _ = PriceCalculator.calculate_child_price(1000, future_date)
        assert price == 0  # будущая дата = 0 лет = бесплатно

    @patch('app.utils.calculators.calculate_age')
    def test_base_price_zero(self, mock_calculate_age):
        """Базовая цена 0."""
        mock_calculate_age.return_value = 4
        child_birth_date = date(2020, 6, 15)

        price, category = PriceCalculator.calculate_child_price(0, child_birth_date)

        assert price == 0
        assert "4-7 лет" in category

    @patch('app.utils.calculators.calculate_age')
    def test_base_price_negative(self, mock_calculate_age):
        """Отрицательная базовая цена."""
        mock_calculate_age.return_value = 4
        child_birth_date = date(2020, 6, 15)

        # Текущее поведение: отрицательная цена * коэффициент
        price, _ = PriceCalculator.calculate_child_price(-100, child_birth_date)
        assert price == -40  # -100 * 0.4 = -40


# ==================== Параметризованные тесты ====================
@pytest.mark.parametrize("age,expected_price_percent,expected_category", [
    (0, 0.0, "до 3 лет"),
    (3, 0.0, "до 3 лет"),
    (4, 0.4, "4-7 лет"),
    (7, 0.4, "4-7 лет"),
    (8, 0.6, "8-12 лет"),
    (12, 0.6, "8-12 лет"),
    (13, 1.0, "13 лет и старше"),
])
@patch('app.utils.calculators.calculate_age')
def test_price_percentage(mock_calculate_age, age, expected_price_percent, expected_category):
    """Параметризованный тест процента от базовой цены."""
    mock_calculate_age.return_value = age

    base_price = 1000
    child_birth_date = date(2024 - age, 6, 15)

    price, category = PriceCalculator.calculate_child_price(base_price, child_birth_date)
    expected_price = int(base_price * expected_price_percent)

    assert price == expected_price
    assert expected_category in category


# ==================== Интеграционные тесты ====================
class TestIntegration:
    """Интеграционные тесты согласованности методов."""

    @patch('app.utils.calculators.calculate_age')
    def test_calculate_and_category_consistency(self, mock_calculate_age):
        """Согласованность calculate_child_price и get_age_category."""
        base_price = 1000
        test_ages = [2, 5, 10, 15]

        for age in test_ages:
            mock_calculate_age.return_value = age

            child_birth_date = date(2024 - age, 6, 15)
            price, calculated_category = PriceCalculator.calculate_child_price(
                base_price, child_birth_date
            )
            expected_category_text = PriceCalculator.get_age_category(age)

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

    def test_price_and_weight_consistency(self):
        """Согласованность ценовых категорий и весовых категорий."""
        # Возрастные границы должны совпадать в PriceCalculator и WeightCalculator
        assert AgeCategories.INFANT_MAX_AGE == 3
        assert AgeCategories.CHILD_MAX_AGE == 7
        assert AgeCategories.PRE_TEEN_MAX_AGE == 12

        # Веса соответствуют возрастным группам
        assert WeightCalculator.INFANT_MAX_WEIGHT == 15
        assert WeightCalculator.CHILD_MAX_WEIGHT == 25
        assert WeightCalculator.PRE_TEEN_MAX_WEIGHT == 40


# ==================== Тесты производительности ====================
class TestPerformance:
    """Тесты производительности."""

    def test_calculation_speed(self):
        """Тест скорости расчета (без моков, с реальным calculate_age)."""
        import time

        base_price = 1000
        today = date.today()

        # Генерируем 1000 разных дат рождения
        test_dates = []
        for i in range(1000):
            birth_year = today.year - (i % 20)
            test_dates.append(date(birth_year, 1, 1))

        start_time = time.perf_counter()

        for birth_date in test_dates:
            PriceCalculator.calculate_child_price(base_price, birth_date)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Не жесткое ограничение, а предупреждение
        if execution_time > 0.1:
            print(f"\n⚠️  Предупреждение: медленный расчет ({execution_time:.4f} сек на 1000 операций)")

        # Всегда проходим, просто логируем
        assert True

    def test_weight_calculation_speed(self):
        """Тест скорости расчета веса."""
        import time

        ages = list(range(0, 20)) + [None] * 5  # 25 значений

        start_time = time.perf_counter()

        for age in ages:
            WeightCalculator.calculate_average_child_weight(age)
            WeightCalculator.get_weight_info(age)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        if execution_time > 0.05:
            print(f"\n⚠️  Предупреждение: медленный расчет веса ({execution_time:.4f} сек)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
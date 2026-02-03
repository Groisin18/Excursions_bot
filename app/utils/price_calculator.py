from datetime import date
from typing import Dict, Tuple

class AgeCategories:
    """Константы возрастных категорий для детских билетов"""

    # Возрастные границы (включительно)
    FREE_MAX_AGE = 3        # до 3 лет включительно - бесплатно
    DISCOUNT_1_MAX_AGE = 7 # 4-7 лет - скидка 60%
    DISCOUNT_2_MAX_AGE = 12 # 8-12 лет - скидка 40%
    # 13+ лет - полная стоимость

    # Проценты скидок (в десятичных долях)
    DISCOUNT_1 = 0.60  # 60% скидка = платим 40%
    DISCOUNT_2 = 0.40  # 40% скидка = платим 60%


class PriceCalculator:
    """Калькулятор цен для детских билетов"""

    @staticmethod
    def calculate_child_price(base_price: int, child_birth_date: date) -> Tuple[int, str]:
        """
        Рассчитать стоимость детского билета по возрасту

        Returns:
            Tuple[цена, возрастная_категория]
        """
        today = date.today()
        age = today.year - child_birth_date.year

        # Корректировка, если день рождения в этом году еще не наступил
        if (today.month, today.day) < (child_birth_date.month, child_birth_date.day):
            age -= 1

        if age <= AgeCategories.FREE_MAX_AGE:
            price = 0
            category = f"до {AgeCategories.FREE_MAX_AGE} лет"
        elif age <= AgeCategories.DISCOUNT_1_MAX_AGE:
            # Скидка 60% = платим 40%
            price = int(base_price * (1 - AgeCategories.DISCOUNT_1))
            category = f"{AgeCategories.FREE_MAX_AGE + 1}-{AgeCategories.DISCOUNT_1_MAX_AGE} лет"
        elif age <= AgeCategories.DISCOUNT_2_MAX_AGE:
            # Скидка 40% = платим 60%
            price = int(base_price * (1 - AgeCategories.DISCOUNT_2))
            category = f"{AgeCategories.DISCOUNT_1_MAX_AGE + 1}-{AgeCategories.DISCOUNT_2_MAX_AGE} лет"
        else:
            price = base_price
            category = "13 лет и старше"

        return price, category

    @staticmethod
    def get_age_category(age: int) -> str:
        """Получить текстовое описание возрастной категории"""
        if age <= AgeCategories.FREE_MAX_AGE:
            return f"до {AgeCategories.FREE_MAX_AGE} лет (бесплатно)"
        elif age <= AgeCategories.DISCOUNT_1_MAX_AGE:
            return f"{AgeCategories.FREE_MAX_AGE + 1}-{AgeCategories.DISCOUNT_1_MAX_AGE} лет (скидка 60%)"
        elif age <= AgeCategories.DISCOUNT_2_MAX_AGE:
            return f"{AgeCategories.DISCOUNT_1_MAX_AGE + 1}-{AgeCategories.DISCOUNT_2_MAX_AGE} лет (скидка 40%)"
        else:
            return "13 лет и старше (полная стоимость)"
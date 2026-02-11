from datetime import date
from typing import Dict, Tuple, List

class AgeCategories:
    """Константы возрастных категорий для детских билетов"""

    # Возрастные границы (включительно)
    INFANT_MAX_AGE = 3        # 0-3 лет включительно - бесплатно
    CHILD_MAX_AGE = 7         # 4-7 лет - скидка 60%
    PRE_TEEN_MAX_AGE = 12     # 8-12 лет - скидка 40%
    # 13+ лет - полная стоимость

    # Проценты скидок (в десятичных долях)
    CHILD_DISCOUNT = 0.60     # 60% скидка = платим 40%
    PRE_TEEN_DISCOUNT = 0.40  # 40% скидка = платим 60%


class PriceCalculator:
    """Калькулятор цен для детских билетов"""

    @staticmethod
    def calculate_child_price(base_price: int, child_birth_date: date) -> Tuple[int, str]:
        """
        Рассчитать стоимость детского билета по возрасту

        Returns:
            Tuple[цена, возрастная_категория]
        """
        from datetime import date as date_class

        today = date_class.today()
        age = today.year - child_birth_date.year

        # Корректировка, если день рождения в этом году еще не наступил
        if (today.month, today.day) < (child_birth_date.month, child_birth_date.day):
            age -= 1

        if age <= AgeCategories.INFANT_MAX_AGE:
            price = 0
            category = f"до {AgeCategories.INFANT_MAX_AGE} лет"
        elif age <= AgeCategories.CHILD_MAX_AGE:
            # Скидка 60% = платим 40%
            price = int(base_price * (1 - AgeCategories.CHILD_DISCOUNT))
            category = f"{AgeCategories.INFANT_MAX_AGE + 1}-{AgeCategories.CHILD_MAX_AGE} лет"
        elif age <= AgeCategories.PRE_TEEN_MAX_AGE:
            # Скидка 40% = платим 60%
            price = int(base_price * (1 - AgeCategories.PRE_TEEN_DISCOUNT))
            category = f"{AgeCategories.CHILD_MAX_AGE + 1}-{AgeCategories.PRE_TEEN_MAX_AGE} лет"
        else:
            price = base_price
            category = "13 лет и старше"

        return price, category

    @staticmethod
    def get_age_category(age: int) -> str:
        """Получить текстовое описание возрастной категории"""
        if age < 0:
            raise ValueError("Отрицательный возраст")
        elif age <= AgeCategories.INFANT_MAX_AGE:
            return f"до {AgeCategories.INFANT_MAX_AGE} лет включительно (бесплатно)"
        elif age <= AgeCategories.CHILD_MAX_AGE:
            return f"{AgeCategories.INFANT_MAX_AGE + 1}-{AgeCategories.CHILD_MAX_AGE} лет (скидка 60%)"
        elif age <= AgeCategories.PRE_TEEN_MAX_AGE:
            return f"{AgeCategories.CHILD_MAX_AGE + 1}-{AgeCategories.PRE_TEEN_MAX_AGE} лет (скидка 40%)"
        else:
            return "13 лет и старше (полная стоимость)"

    @staticmethod
    def get_all_prices(base_price: int) -> Dict[str, int]:
        """
        Получить цены для всех возрастных категорий

        Returns:
            Dict с ценами для каждой категории
        """
        return {
            "infant": 0,  # 0-3 лет
            "child": int(base_price * (1 - AgeCategories.CHILD_DISCOUNT)),  # 4-7 лет
            "pre_teen": int(base_price * (1 - AgeCategories.PRE_TEEN_DISCOUNT)),  # 8-12 лет
            "teen_adult": base_price  # 13+ лет
        }

    @staticmethod
    def get_price_categories(base_price: int) -> List[Dict[str, any]]:
        """
        Получить полную информацию по всем ценовым категориям

        Returns:
            List[Dict] с полной информацией по категориям
        """
        return [
            {
                "age_range": f"до {AgeCategories.INFANT_MAX_AGE} лет",
                "description": "бесплатно",
                "price": 0,
                "discount_percent": 100
            },
            {
                "age_range": f"{AgeCategories.INFANT_MAX_AGE + 1}-{AgeCategories.CHILD_MAX_AGE} лет",
                "description": "скидка 60%",
                "price": int(base_price * (1 - AgeCategories.CHILD_DISCOUNT)),
                "discount_percent": 60
            },
            {
                "age_range": f"{AgeCategories.CHILD_MAX_AGE + 1}-{AgeCategories.PRE_TEEN_MAX_AGE} лет",
                "description": "скидка 40%",
                "price": int(base_price * (1 - AgeCategories.PRE_TEEN_DISCOUNT)),
                "discount_percent": 40
            },
            {
                "age_range": "13 лет и старше",
                "description": "полная стоимость",
                "price": base_price,
                "discount_percent": 0
            }
        ]
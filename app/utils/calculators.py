from datetime import date
from typing import Dict, Tuple, List, Optional
from app.utils.datetime_utils import calculate_age
from app.database.repositories import UserRepository
from app.database.session import async_session

class AgeCategories:
    """Константы возрастных категорий для детских билетов"""

    # Возрастные границы (включительно)
    INFANT_MAX_AGE = 3        # 0-3 лет включительно - бесплатно
    CHILD_MAX_AGE = 7         # 4-7 лет - скидка CHILD_DISCOUNT
    PRE_TEEN_MAX_AGE = 12     # 8-12 лет - скидка PRE_TEEN_DISCOUNT
    # 13+ лет - полная стоимость

    # Проценты скидок (в десятичных долях)
    CHILD_DISCOUNT = 0.60     # 60% скидка = платим 40%
    PRE_TEEN_DISCOUNT = 0.40  # 40% скидка = платим 60%


# ===== КАЛЬКУЛЯТОР ЦЕН =====


class PriceCalculator:
    """Калькулятор цен для детских билетов"""

    @staticmethod
    def calculate_child_price(base_price: int, child_birth_date: date) -> Tuple[int, str]:
        """
        Рассчитать стоимость детского билета по возрасту

        Returns:
            Tuple[цена, возрастная_категория]
        """
        age = calculate_age(child_birth_date)

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



# ===== КАЛЬКУЛЯТОР ВЕСА =====


class WeightCalculator:
    """Калькулятор для расчетов веса участников"""

    # Константы среднего веса по возрастным группам (кг)
    DEFAULT_WEIGHT = 25
    INFANT_MAX_WEIGHT = 15
    CHILD_MAX_WEIGHT = 25
    PRE_TEEN_MAX_WEIGHT = 40
    TEEN_ADULT_WEIGHT = 50

    @staticmethod
    def calculate_average_child_weight(age: Optional[int]) -> int:
        """
        Рассчитать средний вес ребенка по возрасту

        Args:
            age: возраст ребенка в годах (может быть None)

        Returns:
            int: средний вес в кг
        """
        if age is None:
            return WeightCalculator.DEFAULT_WEIGHT
        elif age <= AgeCategories.INFANT_MAX_AGE:
            return WeightCalculator.INFANT_MAX_WEIGHT
        elif age <= AgeCategories.CHILD_MAX_AGE:
            return WeightCalculator.CHILD_MAX_WEIGHT
        elif age <= AgeCategories.PRE_TEEN_MAX_AGE:
            return WeightCalculator.PRE_TEEN_MAX_WEIGHT
        else:
            return WeightCalculator.TEEN_ADULT_WEIGHT

    @staticmethod
    def get_weight_info(age: Optional[int]) -> str:
        """
        Получить информационное сообщение о рассчитанном весе

        Args:
            age: возраст ребенка в годах

        Returns:
            str: описание веса
        """
        weight = WeightCalculator.calculate_average_child_weight(age)
        if age is None:
            return f"средний вес {weight} кг (возраст неизвестен)"
        else:
            return f"средний вес {weight} кг для возраста {age} лет"

    @staticmethod
    def get_weight_by_age_group(age: int) -> Dict[str, any]:
        """
        Получить полную информацию о весе по возрастной группе

        Args:
            age: возраст ребенка

        Returns:
            Dict с информацией о весе
        """
        weight = WeightCalculator.calculate_average_child_weight(age)
        category = PriceCalculator.get_age_category(age)

        return {
            "age": age,
            "weight": weight,
            "category": category,
            "weight_info": WeightCalculator.get_weight_info(age)
        }


# ===== КАЛЬКУЛЯТОР БРОНИРОВАНИЙ =====


class BookingCalculator:
    """Калькулятор для расчетов при бронировании"""

    @staticmethod
    async def calculate_booking_total(
        adult_price: int,
        children_ids: list,
        promo_code_data: dict = None,
        session=None
    ) -> dict:
        """
        Рассчитать итоговую стоимость бронирования с детальной информацией

        Args:
            adult_price: базовая цена экскурсии
            children_ids: список ID детей
            promo_code_data: данные промокода
                        {'type': 'percent'/'fixed', 'value': int, 'code': str}
            session: сессия БД (если есть)

        Returns:
            dict: {
                'final_price': int,  # итоговая цена
                'children_prices': list,  # данные о детях для сохранения в state
                'children_details': list,  # строки для отображения
                'promo_details': str  # строка с информацией о промокоде
            }
        """

        total = adult_price  # взрослый всегда 1
        children_prices = []
        children_details = []

        # Функция для обработки одного ребенка
        async def process_child(child_id, repo):
            child = await repo.get_by_id(child_id)
            if child and child.date_of_birth:
                child_price, category = PriceCalculator.calculate_child_price(
                    adult_price,
                    child.date_of_birth
                )
                return {
                    'id': child_id,
                    'name': child.full_name,
                    'price': child_price,
                    'category': category
                }, f"{child.full_name}: {child_price} руб. ({category})"
            return None, None

        # Если есть дети, добавляем их цены
        if children_ids:
            if session:
                user_repo = UserRepository(session)
                for child_id in children_ids:
                    result = await process_child(child_id, user_repo)
                    if result[0]:
                        child_data, detail = result
                        children_prices.append(child_data)
                        children_details.append(detail)
                        total += child_data['price']
            else:
                async with async_session() as new_session:
                    user_repo = UserRepository(new_session)
                    for child_id in children_ids:
                        result = await process_child(child_id, user_repo)
                        if result[0]:
                            child_data, detail = result
                            children_prices.append(child_data)
                            children_details.append(detail)
                            total += child_data['price']

        # Применяем промокод, если есть
        promo_details = ""
        if promo_code_data and promo_code_data.get('value', 0) > 0:
            promo_type = promo_code_data.get('type')
            promo_value = promo_code_data.get('value')
            promo_code = promo_code_data.get('code', '')

            if promo_type == "percent":
                discount = int(total * promo_value / 100)
                discount_text = f"{promo_value}%"
            else:  # fixed
                discount = min(promo_value, total)
                discount_text = f"{promo_value} руб."

            total -= discount
            promo_details = f"Промокод {promo_code}: скидка {discount_text}"

        return {
            'final_price': total,
            'children_prices': children_prices,
            'children_details': children_details,
            'promo_details': promo_details
        }

    @staticmethod
    def calculate_available_weight(
        max_weight: int,
        current_weight: int,
        participants_weights: List[int]
    ) -> int:
        """
        Рассчитать доступный вес после добавления участников

        Args:
            max_weight: максимальный допустимый вес
            current_weight: текущий занятый вес
            participants_weights: список весов новых участников

        Returns:
            int: оставшийся доступный вес
        """
        total_additional = sum(participants_weights)
        return max_weight - (current_weight + total_additional)

    @staticmethod
    def is_weight_available(
        max_weight: int,
        current_weight: int,
        additional_weight: int
    ) -> bool:
        """
        Проверить, доступен ли указанный вес

        Returns:
            bool: True если вес доступен
        """
        return (current_weight + additional_weight) <= max_weight
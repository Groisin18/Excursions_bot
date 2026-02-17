from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict


class BookingChildData(BaseModel):
    """Данные ребенка в бронировании"""
    child_id: int
    full_name: str
    price: int = Field(ge=0)
    age_category: str
    weight: Optional[int] = Field(None, ge=1, le=299)


class BookingCreationData(BaseModel):
    """Все данные для создания бронирования"""
    # Основные данные
    slot_id: int
    user_id: int
    adult_price: int = Field(ge=0)
    final_price: int = Field(ge=0)

    # Участники
    adult_weight: int = Field(ge=1, le=299)
    children: List[BookingChildData] = Field(default_factory=list)

    # Промокод
    promo_code_id: Optional[int] = None
    promo_code: Optional[str] = None
    promo_discount_type: Optional[str] = None
    promo_discount_value: Optional[int] = Field(None, ge=0, le=100)

    # Вес
    total_weight: int = Field(ge=1)

    @field_validator('final_price')
    @classmethod
    def validate_final_price(cls, v: int) -> int:
        """Проверка, что финальная цена не отрицательная"""
        if v < 0:
            raise ValueError('Цена не может быть отрицательной')
        return v

    @property
    def people_count(self) -> int:
        """Общее количество людей"""
        return 1 + len(self.children)

    @property
    def children_count(self) -> int:
        """Количество детей"""
        return len(self.children)

    @property
    def children_weights(self) -> Dict[int, int]:
        """Словарь весов детей {child_id: weight}"""
        return {child.child_id: child.weight for child in self.children if child.weight}

    @property
    def children_data_for_repo(self) -> List[Dict]:
        """Данные детей в формате для репозитория"""
        return [
            {
                'child_id': child.child_id,
                'price': child.price,
                'age_category': child.age_category
            }
            for child in self.children
        ]
from pydantic import BaseModel, Field, EmailStr


class UserRegistrationData(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Имя")
    surname: str = Field(..., min_length=1, max_length=50, description="Фамилия")
    date_of_birth: str = Field(..., description="Дата рождения")
    age: int = Field(..., ge=0, le=150, description="Возраст")
    weight: int = Field(..., gt=0, le=300, description="Вес в кг")
    address: str = Field(..., min_length=1, max_length=150, description="Адрес проживания")
    phone: str = Field(..., description="Номер телефона")
    email: EmailStr = Field(..., description="Email адрес")

class ChildRegistrationData(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Имя")
    surname: str = Field(..., min_length=1, max_length=50, description="Фамилия")
    date_of_birth: str = Field(..., description="Дата рождения")
    age: int = Field(..., ge=0, le=150, description="Возраст")
    weight: int = Field(..., gt=0, le=300, description="Вес в кг")
    address: str = Field(..., min_length=1, max_length=150, description="Адрес проживания")
    parent_id: int = Field(..., ge=0, description="ID родителя")

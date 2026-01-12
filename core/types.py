from enum import Enum
from typing import Literal


class QuestionType(Enum):
    THEORETICAL = "theory"
    PRACTICAL = "practice"

    @classmethod
    def from_literal(cls, type: Literal["theory", "practice"]) -> "QuestionType":
        return cls[type.upper()]


class OrderType(Enum):
    """Тип фильтрации SQL.

    ASC -- Возрастающий.
    DESC -- Убывающий.
    """

    DESC = "DESC"
    ASC = "ASC"

    @classmethod
    def from_literal(cls, type: Literal["desk", "asc"]) -> "OrderType":
        return cls[type.upper()]

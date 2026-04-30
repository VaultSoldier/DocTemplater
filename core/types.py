from enum import Enum
from typing import Literal


class AppEvent:
    DB_RESET = "DB_RESET"
    UPDATE_THEME = "UPDATE_THEME"
    TABLE_CHANGED = "TABLE_CHANGED"
    API_SUCESS = "API_SUCESS"
    API_NO_URL = "API_NO_URL"
    API_ERROR = "API_ERROR"


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

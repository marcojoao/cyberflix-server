from enum import Enum
from typing import TypeVar

T = TypeVar("T", bound="CatalogFilterType")


class CatalogFilterType(Enum):
    CATEGORIES = "categories"
    YEARS = "years"
    NONE = "none"

    @staticmethod
    def index(value) -> int:
        elements = [e.value for e in CatalogFilterType]
        return elements.index(value.value)

from enum import Enum
from typing import TypeVar

T = TypeVar("T", bound="CatalogType")


class CatalogType(Enum):
    MOVIES = "movie"
    SERIES = "series"
    ANY = "any"

    @staticmethod
    def index(value) -> int:
        elements = [e.value for e in CatalogType]
        return elements.index(value.value)

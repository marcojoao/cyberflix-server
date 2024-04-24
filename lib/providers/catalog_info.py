from lib.model.catalog_type import CatalogType


class ImdbInfo:
    def __init__(self, id: str, type: CatalogType, genres=[], year="") -> None:
        self.id = id
        self.type = type
        self.genres = genres
        self.year = year

    def set_genres(self, genres: list[str]):
        self.genres = genres

    def set_year(self, year: str):
        self.year = year

    def __repr__(self) -> str:
        return f"ImdbInfo(id={self.id}, type={self.type.value.lower()})"

    def __str__(self) -> str:
        return self.__repr__()

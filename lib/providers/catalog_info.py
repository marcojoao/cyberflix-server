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

    def to_dict(self):
        return {"id": self.id, "type": self.type.value.lower(), "genres": self.genres, "year": self.year}

    @staticmethod
    def from_dict(data: dict):
        d_id = data.get("id")
        if not d_id:
            raise ValueError("Id is required")
        return ImdbInfo(
            id=d_id,
            type=CatalogType(data.get("type")),
            genres=data.get("genres"),
            year=data.get("year") or "",
        )

    def to_json(self):
        import json

        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"ImdbInfo(id={self.id}, type={self.type}, genres={self.genres}, year={self.year})"
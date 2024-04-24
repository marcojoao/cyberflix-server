from datetime import datetime, timedelta

from lib.model.catalog_filter_type import CatalogFilterType
from lib.model.catalog_type import CatalogType


class CatalogConfig:
    def __init__(self, name_id: str, provider_id: str, types: list[CatalogType], schema: str, **kwargs):
        self.__name_id: str = name_id
        self.__provider_id: str = provider_id
        self.__display_name: str | None = kwargs.get("display_name") or None
        self.__types: list[CatalogType] = types
        self.__schema: str = schema
        self.__filter_type: CatalogFilterType = kwargs.get("filter_type") or CatalogFilterType.CATEGORIES
        self.__expiration_date: datetime = datetime.now() + timedelta(days=kwargs.get("expiration_days", 1))
        self.__pages: int | None = kwargs.get("pages", None)
        self.__force_update: bool = kwargs.get("force_update", False)

    @property
    def name_id(self) -> str:
        return self.__name_id

    @property
    def provider_id(self) -> str:
        return self.__provider_id

    @property
    def display_name(self) -> str | None:
        return self.__display_name

    @property
    def types(self) -> list[CatalogType]:
        return self.__types

    @property
    def schema(self) -> str:
        return self.__schema

    @property
    def expiration_date(self) -> datetime:
        return self.__expiration_date

    @property
    def pages(self) -> int | None:
        return self.__pages

    @property
    def filter_type(self) -> CatalogFilterType:
        return self.__filter_type

    @property
    def force_update(self) -> bool:
        return self.__force_update

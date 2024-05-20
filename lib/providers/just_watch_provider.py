from lib.apis.just_watch import JustWatch
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class JustWatchProvider(CatalogProvider):
    def __init__(self):
        super().__init__()
        self.__api = JustWatch()

    @property
    def api(self) -> JustWatch:
        return self.__api

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        pages = kwargs.get("pages") or 1
        if c_type == CatalogType.ANY:
            r_type = "MOVIE,SHOW"
        else:
            r_type = "SHOW" if c_type == CatalogType.SERIES else "MOVIE"
        schema = f"objectType={r_type}&{schema}"

        jw_data = self.__api.request_page(schema=schema, pages=pages)
        imdb_infos = []
        for data in jw_data:
            imdb_id: str | None = data.get("imdb_id", None)
            if imdb_id is None or imdb_id.startswith("tt") is False:
                continue
            object_type: str | None = data.get("object_type", None)
            if object_type is None:
                continue
            jw_c_type = CatalogType.SERIES if object_type.upper() == "SHOW" else CatalogType.MOVIES
            imdb_info = ImdbInfo(id=imdb_id, type=jw_c_type)
            imdb_infos.append(imdb_info)
        return imdb_infos

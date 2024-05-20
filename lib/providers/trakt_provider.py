from lib.apis.trakt import Trakt
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class TraktProvider(CatalogProvider):
    def __init__(self):
        super().__init__(on_demand=True)
        self.__provider = Trakt()

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        r_type = "shows" if c_type == CatalogType.SERIES else "movies"
        if c_type == CatalogType.ANY:
            raise ValueError("Trakt does not support 'ANY' type")
        imdb_ids = self.__provider.request_page(s_type=r_type, schema=schema)
        imdb_infos = []
        for imdb_id in imdb_ids:
            if imdb_id is None or imdb_id.startswith("tt") is False:
                continue
            imdb_infos.append(ImdbInfo(id=imdb_id, type=c_type))
        return imdb_infos

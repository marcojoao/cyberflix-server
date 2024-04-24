from lib.apis.imdb import IMDB
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class IMDBProvider(CatalogProvider):
    def __init__(self):
        super().__init__()
        self.__provider = IMDB()

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        pages = kwargs.get("pages") or 1
        imdb_nodes = self.__provider.request_page(schema=schema, pages=pages)
        imdb_infos = []
        for imdb_node in imdb_nodes:
            imdb_id = imdb_node.get("id", None)
            if imdb_id is None or imdb_id == "":
                continue
            imdb_type = imdb_node.get("type", None)
            if imdb_type is None:
                continue
            meta_type = (
                CatalogType.MOVIES
                if imdb_type == "movie"
                else CatalogType.SERIES if c_type == CatalogType.ANY else c_type
            )
            imdb_infos.append(ImdbInfo(id=imdb_id, type=meta_type))

        return imdb_infos

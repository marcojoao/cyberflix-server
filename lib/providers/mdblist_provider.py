from lib.apis.mdblist import MDBList
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class MDBListProvider(CatalogProvider):
    def __init__(self):
        super().__init__()
        self.__provider = MDBList()

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        imdb_nodes = self.__provider.request_page(schema=schema)
        imdb_infos = []
        for imdb_node in imdb_nodes:
            imdb_id = imdb_node.get("imdb_id", None)
            if imdb_id is None or imdb_id == "":
                continue
            imdb_type = imdb_node.get("mediatype", None)
            if imdb_type is None:
                continue
            if imdb_type == "movie" and c_type == CatalogType.SERIES:
                continue
            if imdb_type == "show" and c_type == CatalogType.MOVIES:
                continue
            meta_type = CatalogType.MOVIES if imdb_type == "movie" else CatalogType.SERIES
            imdb_infos.append(ImdbInfo(id=imdb_id, type=meta_type))

        return imdb_infos

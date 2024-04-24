import os

from lib import db_manager, utils
from lib.apis.imdb import IMDB
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class TMDBProvider(CatalogProvider):
    def __init__(self):
        super().__init__()
        self.__imdb = IMDB()
        self.__catalogs_pages = int(os.environ.get("TMDB_CATALOG_PAGES", "180"))

        self.__cached_tmdb_catalogs = []

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        pages = kwargs.get("pages") or self.__catalogs_pages
        catalog_type = "tv" if c_type.value == "series" else "movie"
        schema = schema.replace("$type", catalog_type).replace("$api_key", self.tmdb.api_key)
        url = f"{self.tmdb.url}/{schema}"
        imdb_infos = self.get_catalog_pages(url=url, c_type=c_type, pages=pages)
        db_manager.set_tmdb_ids_cache(db_manager.cached_tmdb_ids)
        return imdb_infos

    def __get_imdb_id(self, tmdb_id: str, type: CatalogType) -> str | None:
        external_ids = self.tmdb.get_external_ids(tmdb_id=tmdb_id, c_type=type)
        imdb_id = None
        if external_ids is not None:
            imdb_id = external_ids.get("imdb_id", None)
        return imdb_id

    def get_catalog_pages(self, url: str, c_type: CatalogType, pages: int) -> list:
        urls = [f"{url}&page={i+1}" for i in range(pages)]

        def __get_metas_thread(**kwargs):
            urls = kwargs.get("item", None)
            idx = kwargs.get("index", None)
            c_type = kwargs.get("c_type", None)
            if urls is None or idx is None or c_type is None:
                return []
            imdb_infos = []
            for page in urls:
                tmdb_nodes = self.tmdb.request_page(page)
                if tmdb_nodes is None or len(tmdb_nodes) == 0:
                    break
                for tmdb_node in tmdb_nodes:
                    tmdb_id = tmdb_node.get("id", None)
                    if tmdb_id is None:
                        continue
                    tmdb_cache = db_manager.cached_tmdb_ids.get(str(tmdb_id)) or None
                    imdb_id = None
                    if tmdb_cache is not None:
                        is_valid = tmdb_cache.get("valid", False)
                        if is_valid is False:
                            continue
                        imdb_id = tmdb_cache.get("imdb_id", None)
                    else:
                        print(f"Getting imdb_id for {tmdb_id}")
                        imdb_id = self.__get_imdb_id(tmdb_id=tmdb_id, type=c_type)

                    if not isinstance(imdb_id, str) or imdb_id.startswith("tt") is False:
                        catalog_type = "tv" if c_type.value == "series" else "movie"
                        title = str(tmdb_node.get("title" if catalog_type == "movie" else "name", ""))
                        search_type = "movie" if catalog_type == "movie" else "tvSeries"
                        results = self.__imdb.request_page(
                            schema=f"searchTerm={title}&sortBy=POPULARITY&sortOrder=ASC&locale=en-US&first=10"
                        )
                        if results is None or len(results) == 0:
                            db_manager.cached_tmdb_ids.update({str(tmdb_id): {"valid": False}})
                            continue
                        for result in results:
                            if result.get("type", "") == search_type and result.get("title", "") == title:
                                imdb_id = result.get("id", None)
                                break
                    if not isinstance(imdb_id, str) or imdb_id.startswith("tt") is False:
                        db_manager.cached_tmdb_ids.update({str(tmdb_id): {"valid": False}})
                        continue

                    db_manager.cached_tmdb_ids.update({str(tmdb_id): {"valid": True, "imdb_id": imdb_id}})
                    tmdb_node.update({"imdb_id": imdb_id})
                    imdb_info = ImdbInfo(id=imdb_id, type=c_type)
                    self.__cached_tmdb_catalogs.append(tmdb_node)
                    imdb_infos.append(imdb_info)
            return imdb_infos

        chunks = utils.divide_chunks(urls, 10)
        results = utils.parallel_for(__get_metas_thread, items=chunks, c_type=c_type)
        results = [item for sublist in results for item in sublist]
        return results

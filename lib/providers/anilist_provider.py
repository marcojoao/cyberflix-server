from lib import db_manager
from lib.apis.anilist import AniList
from lib.apis.tmdb import TMDB
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider
from lib.utils import parallel_for


class AniListProvider(CatalogProvider):
    def __init__(self):
        super().__init__()
        self.__tmdb = TMDB()
        self.__anilist = AniList()

    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        r_type = "TV" if c_type == CatalogType.SERIES else "MOVIE"
        pages = kwargs.get("pages") or 10
        media = self.__anilist.request_page(s_type=r_type, schema=schema, pages=pages)
        imdb_infos = []

        def get_imdb_info(item: dict, idx: int, worker_id: int) -> ImdbInfo | None:
            name = item.get("native", None)
            if name is None:
                return None
            results = self.__tmdb.search(query=name, c_type=c_type)
            if results is None:
                return None

            for result in results:
                original_language = result.get("original_language", None)
                genre_ids = result.get("genre_ids", None)
                valid_original_language = original_language is not None and original_language == "ja"
                valid_genre_ids = genre_ids is not None and 16 in genre_ids
                if valid_original_language and valid_genre_ids:
                    tmdb_id = result.get("id", None)
                    if tmdb_id is None:
                        continue
                    tmdb_cache = db_manager.cached_tmdb_ids.get(str(tmdb_id), None)
                    imdb_id = None
                    if tmdb_cache is not None:
                        is_valid = tmdb_cache.get("valid", False)
                        if is_valid is False:
                            continue
                        imdb_id = tmdb_cache.get("imdb_id", None)
                    else:
                        imdb_id = self.__get_imdb_id(tmdb_id=tmdb_id, type=c_type)

                    if imdb_id is None or imdb_id.startswith("tt") is False:
                        continue

                    if not isinstance(imdb_id, str) or imdb_id.startswith("tt") is False:
                        db_manager.cached_tmdb_ids.update({str(tmdb_id): {"valid": False}})
                        continue

                    db_manager.cached_tmdb_ids.update({str(tmdb_id): {"valid": True, "imdb_id": imdb_id}})
                    return ImdbInfo(id=imdb_id, type=c_type)
            return None

        results = parallel_for(function=get_imdb_info, items=media)

        for result in results:
            if result is not None:
                imdb_infos.append(result)

        db_manager.update_tmdb_ids(db_manager.cached_tmdb_ids)
        return imdb_infos

    def __get_imdb_id(self, tmdb_id: str, type: CatalogType) -> str | None:
        external_ids = self.tmdb.get_external_ids(tmdb_id=tmdb_id, c_type=type)
        imdb_id = None
        if external_ids is not None:
            imdb_id = external_ids.get("imdb_id", None)
        return imdb_id

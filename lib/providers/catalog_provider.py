from abc import abstractmethod

from lib import log, utils
from lib.apis.cinemeta import Cinemeta
from lib.apis.tmdb import TMDB
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo


class CatalogProvider:
    def __init__(self, on_demand: bool = False):
        log.info(f"::=> Initializing {self.__class__.__name__}...")
        self.tmdb = TMDB()
        self.cinemeta = Cinemeta()
        self.on_demand = on_demand

    @abstractmethod
    def get_imdb_info(self, schema: str, c_type: CatalogType, **kwargs) -> list[ImdbInfo]:
        raise NotImplementedError

    def get_catalog_metas(self, catalog_info: list[ImdbInfo]) -> dict:
        results = {}

        series_infos = [info for info in catalog_info if info.type == CatalogType.SERIES]
        movies_infos = [info for info in catalog_info if info.type == CatalogType.MOVIES]
        results.update(self.get_all_metas(infos=series_infos, c_type=CatalogType.SERIES))
        results.update(self.get_all_metas(infos=movies_infos, c_type=CatalogType.MOVIES))

        metas = [results[info.id] for info in catalog_info if info.id in results]
        return {"metas": metas}

    def get_all_metas(self, infos: list[ImdbInfo], c_type: CatalogType) -> dict:
        def __get_metas(**kwargs) -> dict:
            infos = kwargs.get("item", None)
            c_type = kwargs.get("c_type", None)
            ids_to_download = []
            result_metas = {}
            for info in infos:
                ids_to_download.append(info.id)
            if len(ids_to_download) == 0:
                return result_metas
            metas = self.cinemeta.get_meta_bulk(ids_to_download, s_type=c_type.value.lower())
            for meta in metas:
                if meta is None:
                    continue
                imdb_id = meta.get("imdb_id", "")
                if imdb_id == "":
                    log.info("Failed to get imdb_id, skipping...")
                    continue
                poster = meta.get("poster", "")
                if poster == "":
                    log.info(f"Failed to get poster for {imdb_id}, skipping...")
                    continue
                meta = self.update_meta(meta)
                result_metas.update({imdb_id: meta})
            return result_metas

        results = {}
        chunks = utils.divide_chunks(infos, 100)
        list_results = utils.parallel_for(__get_metas, items=chunks, c_type=c_type)
        for result in list_results:
            for key, value in result.items():
                results.update({key: value})
        return results

    def update_meta(self, meta: dict) -> dict:

        genres = set()
        for genre in meta.get("genres", []):
            new_genre = self.cinemeta.get_simplified_genre(genre)
            if new_genre:
                genres.add(new_genre)

        release_info = self.cinemeta.get_simplified_year(meta.get("releaseInfo", ""))
        meta.update({"genres": list(genres)})
        meta.update({"releaseInfo": release_info})
        return meta

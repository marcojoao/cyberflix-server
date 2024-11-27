# from datetime import datetime
from lib.env import SKIP_DB_UPDATE
from rich.progress import track
from datetime import datetime
from catalog_list import CatalogList
from lib import db_manager, log
from lib.apis.cinemeta import Cinemeta
from lib.model.catalog_config import CatalogConfig
from lib.model.catalog_filter_type import CatalogFilterType
from lib.model.catalog_type import CatalogType
from lib.model.manifest import Manifest
from lib.providers.anilist_provider import AniListProvider
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider
from lib.providers.imdb_provider import IMDBProvider
from lib.providers.just_watch_provider import JustWatchProvider
from lib.providers.mdblist_provider import MDBListProvider
from lib.providers.tmdb_provider import TMDBProvider
from lib.providers.trakt_provider import TraktProvider
from lib.utils import parallel_for

class Builder:
    def __init__(self) -> None:
        log.info(f"::=> Initializing {self.__class__.__name__}...")
        self.__catalog_providers: dict[str, CatalogProvider] = {
            "tmdb": TMDBProvider(),
            "imdb": IMDBProvider(),
            "anilist": AniListProvider(),
            "mdblist": MDBListProvider(),
            "justwatch": JustWatchProvider(),
            "trakt": TraktProvider(),
        }
        self.__manifest: Manifest = Manifest()

    def update_imdb_infos(self, infos: list[ImdbInfo], values: dict = {}) -> list[ImdbInfo]:
        metas = values.get("metas") or []
        new_infos = []
        for info in infos:
            for value in metas:
                meta_id = value.get("id", None)
                if meta_id == info.id:
                    genres = value.get("genres") or []
                    if len(genres) == 0:
                        continue
                    new_genres = []
                    for genre in genres:
                        new_genres.append(Cinemeta.get_simplified_genre(genre))
                    info.set_genres(new_genres)
                    year = value.get("releaseInfo") or ""
                    info.set_year(year)
                    new_infos.append(info)
                    break
        return new_infos

    def build_manifiest_item(self, item: CatalogConfig, conf_type: CatalogType, values: list[ImdbInfo]) -> dict:
        unique_filters = set()
        for value in values:
            if item.filter_type == CatalogFilterType.CATEGORIES:
                for genre in value.genres:
                    unique_filters.add(genre)
            elif item.filter_type == CatalogFilterType.YEARS:
                year = value.year
                if year is not None:
                    unique_filters.add(year)
        is_type_years = item.filter_type == CatalogFilterType.YEARS
        unique_filters = sorted(list(unique_filters), reverse=is_type_years)
        if is_type_years and len(unique_filters) > 15:
            unique_filters = unique_filters[:15]
        name_id_parts = item.name_id.split(".")
        name = item.display_name
        item_type = ""

        if len(name_id_parts) > 1:
            item_type = name_id_parts[0].lower().replace("_", " ").title()
            if name is None:
                base_name = item.name_id.replace(f"{name_id_parts[0]}.", "")
                name = f"{base_name}.{conf_type.name.lower()}"
                name = name.replace("_", " ").replace(".any", "").replace(".", " ").title()
            else:
                name = f"{name} {conf_type.name.title()}"
        else:
            item_type = conf_type.value.lower()
            if name is None:
                name = name_id_parts[0].replace("_", " ").title()
        data = {
            "id": self.__get_item_id(item=item, conf_type=conf_type),
            "name": name,
            "type": item_type,
            "extra": [
                {
                    "name": "genre",
                    "options": unique_filters,
                },
                {"name": "skip"},
            ],
            "extraSupported": ["genre", "skip"],
        }
        return data

    def __get_item_id(self, item: CatalogConfig, conf_type: CatalogType) -> str:
        return f"{item.name_id.lower()}.{conf_type.value.lower()}"

    def build_catalog(self, item: CatalogConfig) -> list:
        outputs = []
        types = item.types.copy()
        provider = self.__catalog_providers.get(item.provider_id, None)
        if provider is None:
            return outputs

        current_time = datetime.now()
        for conf_type in types[:]:
            item_id = self.__get_item_id(item, conf_type)
            existing_catalog = db_manager.cached_catalogs.get(item_id)
            if existing_catalog is None:
                continue
            expiration_date = datetime.fromisoformat(existing_catalog.get('expiration_date'))
            if not item.force_update and existing_catalog and expiration_date:
                if current_time < expiration_date:
                    data = existing_catalog.get('data')
                    outputs.append(self.build_manifiest_item(item, conf_type, data))
                    types.remove(conf_type)
                    continue

        if not types:
            return outputs


        def process_type(conf_type, idx, worker_id):
            if provider.on_demand:
                return self.build_manifiest_item(item, conf_type, [])

            imdb_infos = provider.get_imdb_info(schema=item.schema, pages=item.pages, c_type=conf_type)
            if imdb_infos is None or len(imdb_infos) == 0:
                return None

            item_id = self.__get_item_id(item, conf_type)
            item_metas = provider.get_catalog_metas(imdb_infos)
            if item_metas is None or len(item_metas) == 0:
                return None

            metas = item_metas.get("metas") or []
            dict_by_id = {item.get("id"): item for item in metas}
            imdb_infos = self.update_imdb_infos(imdb_infos, item_metas)

            return {
                "item_id": item_id,
                "dict_by_id": dict_by_id,
                "imdb_infos": imdb_infos,
                "manifest_item": self.build_manifiest_item(item, conf_type, imdb_infos)
            }

        results = parallel_for(process_type, types)

        for result in results:
            if result is None:
                continue

            db_manager.cached_metas.update(result["dict_by_id"])
            db_manager.cached_catalogs.update({
                result["item_id"]: {
                    "expiration_date": item.expiration_date,
                    "data": result["imdb_infos"]
                }
            })
            outputs.append(result["manifest_item"])

        return outputs

    def get_catalog(self, provider_id: str, schema: str, c_type: CatalogType, **kwargs) -> list:
        provider = self.__catalog_providers.get(provider_id, None)
        if provider is None:
            return []
        imdb_infos = provider.get_imdb_info(schema=schema, c_type=c_type, **kwargs)
        if imdb_infos is None or len(imdb_infos) == 0:
            return []
        return imdb_infos

    def build(self):
        log.info("Caching catalongs...")
        configs = CatalogList.get_catalog_configs()

        manifest_catalog = []
        current_catalog = ""
        for config in track(configs, f"Building: {current_catalog}"):
            current_catalog = config.name_id
            data = self.build_catalog(config)
            manifest_catalog.extend(data)

        if not SKIP_DB_UPDATE:
            log.info("Uploading tmdb ids ...")
            db_manager.update_tmdb_ids(db_manager.cached_tmdb_ids)

            log.info("Uploading metas ...")
            db_manager.update_metas(metas=db_manager.cached_metas)

            log.info("Uploading catalogs ...")
            db_manager.update_catalogs(catalogs=db_manager.cached_catalogs)

            log.info("Uploading manifest ...")
            manifest = self.__manifest.get_meta(catalogs_config=manifest_catalog)
            db_manager.update_manifest(manifest=manifest)


if __name__ == "__main__":
    Builder().build()

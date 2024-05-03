from datetime import datetime

from rich.progress import track

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
from lib.providers.tmdb_provider import TMDBProvider
from lib.providers.trakt_provider import TraktProvider


class Builder:
    def __init__(self) -> None:
        log.info(f"::=> Initializing {self.__class__.__name__}...")
        self.__catalog_providers: dict[str, CatalogProvider] = {
            "tmdb": TMDBProvider(),
            "imdb": IMDBProvider(),
            "anilist": AniListProvider(),
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

    def build_manifiest_item(self, item: CatalogConfig, conf_type: CatalogType, values: dict = {}) -> dict:
        unique_filters = set()
        metas = values.get("metas") or []
        for value in metas:
            if item.filter_type == CatalogFilterType.CATEGORIES:
                genres = value.get("genres", [])
                for genre in genres:
                    unique_filters.add(genre)
            elif item.filter_type == CatalogFilterType.YEARS:
                year = value.get("releaseInfo")
                if year is not None:
                    unique_filters.add(year)
        is_type_years = item.filter_type == CatalogFilterType.YEARS
        unique_filters = sorted(list(unique_filters), reverse=is_type_years)
        if is_type_years and len(unique_filters) > 10:
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
            "pageSize": 25,
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

    # def get_translation(self, imdb_id: str, title: str, lang: str) -> dict | None:
    #     privider = self.__catalog_providers.get("justwatch")
    #     if isinstance(privider, JustWatchProvider):
    #         result = privider.api.search_title(title, language=lang)
    #         for item in result:
    #             item_imdb_id = item.get("imdb_id", None)
    #             if item_imdb_id == imdb_id:
    #                 t_name = item.get("title", None) or item.get("name", None)
    #                 t_description = item.get("short_description", None) or item.get("description", None)
    #                 t_poster = item.get("big_poster_url", None) or item.get("poster_url", None)
    #                 return {"name": t_name, "description": t_description, "poster": t_poster}
    #     return None

    # def build_translations(self, metas):
    #     langs = db_manager.supported_langs.values()
    #     results = {}
    #     if metas is None:
    #         return results
    #     privider = self.__catalog_providers.get("justwatch")
    #     if not isinstance(privider, JustWatchProvider):
    #         return results

    #     def __get_translations(**kwargs):
    #         item = kwargs.get("item")
    #         privider = kwargs.get("privider")
    #         langs = kwargs.get("langs")
    #         if item is None or privider is None or langs is None:
    #             return {}
    #         imdb_id = item.get("id", None)
    #         title = item.get("name", None)
    #         if imdb_id is None or title is None:
    #             return {}
    #         cached_translation = db_manager.cached_translations.get(imdb_id, None)
    #         translations = {}
    #         for lang in langs:
    #             got_cached = cached_translation is not None and lang in cached_translation
    #             if got_cached:  # check if translation is cached
    #                 translations.update({lang: cached_translation[lang]})
    #                 continue
    #             result = self.get_translation(imdb_id, title, lang)
    #             if result is not None:
    #                 translations.update({lang: result})
    #         return {imdb_id: translations}

    #     metas_list = metas.get("metas")
    #     results = utils.parallel_for(__get_translations, items=metas_list, privider=privider, langs=langs)

    #     output = {}
    #     for result in results:
    #         output.update(result)
    #     return output

    def __get_item_id(self, item: CatalogConfig, conf_type: CatalogType) -> str:
        return f"{item.name_id.lower()}.{conf_type.value.lower()}"

    def build_catalog(self, item: CatalogConfig) -> list:
        outputs = []
        types = item.types.copy()
        provider = self.__catalog_providers.get(item.provider_id, None)
        if provider is None:
            return outputs

        for conf_type in item.types:
            item_id = self.__get_item_id(item, conf_type)
            catalog = db_manager.cached_catalogs.get(item_id) or {}
            cached_data = catalog.get("data") or []
            if item.force_update or len(cached_data) == 0:
                continue
            expiration_data: str = catalog.get("expiration_date", None)
            if expiration_data is not None:
                if datetime.fromisoformat(expiration_data) > datetime.now():
                    item_metas = provider.get_catalog_metas(cached_data)
                    if item_metas is None or len(item_metas) == 0:
                        continue

                    data = self.build_manifiest_item(item, conf_type, item_metas)
                    if data is not None:
                        outputs.append(data)
                        types.remove(conf_type)
                        log.info(
                            f"Using cached {self.__get_item_id(item=item, conf_type=conf_type)}({conf_type.value.lower()})"
                        )

        if len(types) == 0:
            return outputs

        for conf_type in types:

            log.info(f"Building {item.name_id} ({conf_type.value.lower()})")

            if provider.on_demand:
                data = self.build_manifiest_item(item, conf_type)
                outputs.append(data)
                continue

            imdb_infos = provider.get_imdb_info(schema=item.schema, pages=item.pages, c_type=conf_type)
            if imdb_infos is None or len(imdb_infos) == 0:
                continue

            # update catalog lists
            item_id = self.__get_item_id(item, conf_type)

            item_metas = provider.get_catalog_metas(imdb_infos)
            if item_metas is None or len(item_metas) == 0:
                continue
            metas = item_metas.get("metas") or []
            dict_by_id = {item.get("id"): item for item in metas}
            imdb_infos = self.update_imdb_infos(imdb_infos, item_metas)
            db_manager.cached_metas.update(dict_by_id)
            db_manager.cached_catalogs.update(
                {item_id: {"expiration_date": item.expiration_date, "data": imdb_infos}}
            )

            # update catalog metas
            data = self.build_manifiest_item(item, conf_type, item_metas)
            outputs.append(data)

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
        # db_manager.init_tmdb_ids_cache()
        # db_manager.init_translations_cache()

        configs = CatalogList.get_catalog_configs()

        manifest_catalog = []
        current_catalog = ""
        for config in track(configs, f"Building: {current_catalog}"):
            current_catalog = config.name_id
            data = self.build_catalog(config)
            manifest_catalog.extend(data)

        # for lang in db_manager.supported_langs.values():
        #     log.info(f"Uploading {lang} translations to firestore ...")
        #     db_manager.set_catalog_translations(db_manager.cached_translations, lang)

        log.info("Uploading metas ...")
        db_manager.update_metas(db_manager.cached_metas)

        log.info("Uploading manifest ...")
        manifest = self.__manifest.get_meta(catalogs_config=manifest_catalog)
        db_manager.update_manifest(manifest)

        log.info("Uploading catalogs ...")
        db_manager.update_catalogs(db_manager.cached_catalogs)


if __name__ == "__main__":
    Builder().build()

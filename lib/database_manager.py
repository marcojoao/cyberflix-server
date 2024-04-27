from lib import db, env, utils
from lib.model.catalog_type import CatalogType
from lib.providers.catalog_info import ImdbInfo


class DatabaseManager:
    def __init__(self, log, firebase_env_key: str | None = None):
        self.db = db.Db(firebase_env_key=firebase_env_key)
        self.log = log
        self.__cached_tmdb_ids: dict = {}
        self.__cached_manifest: dict = {}
        self.__max_cache_size = 500
        self.update_manifest()

    def init_tmdb_ids_cache(self):
        if self.__cached_tmdb_ids:
            return
        self.__cached_tmdb_ids = self.get_tmdb_ids_cache()

    @property
    def cached_tmdb_ids(self) -> dict:
        return self.__cached_tmdb_ids

    @property
    def cached_manifest(self) -> dict:
        return self.__cached_manifest

    @property
    def supported_langs(self) -> dict[str, str]:
        catalogLanguages = {
            "🇬🇧 English": "en",
            "🇪🇸 Spanish": "es",
            "🇫🇷 French": "fr",
            "🇩🇪 German": "de",
            "🇵🇹 Portuguese": "pt",
            "🇮🇹 Italian": "it",
            "🇷🇴 Romenian": "ro",
        }
        return catalogLanguages

    def get_web_config(self, catalogs) -> dict:
        config = {
            "max_num_of_catalogs": 60,
            "enable_trackt": False,
            "enable_rpdb": True,
            "enable_lang": False,
            "version": self.cached_manifest.get("version") or "0.0.0",
            "default_catalogs": [
                "2047f",
                "358a6",
                "21c60",
                "ab39b",
                "691d0",
                "09e1d",
                "d2466",
            ],
            "catalogs": catalogs,
            "default_language": "en",
            "languages": self.supported_langs,
            "sponsor": env.SPONSOR,
        }
        return {"config": config}

    def update_manifest(self):
        self.__cached_manifest = self.db.get("catalog", "manifest") or {}

    def set_manifest(self, manifest: dict) -> bool:
        self.log.info("Setting manifest...")
        return self.db.set("catalog", "manifest", manifest)

    def get_catalog_schemas_info(self, catalog_id) -> dict:
        return self.db.get("catalog", catalog_id) or {}

    def get_catalog_schemas(self, catalog_id) -> list[ImdbInfo]:
        results = []
        data = self.get_catalog_schemas_info(catalog_id)
        if data is None:
            return results
        num_parts = data.get("num_parts") or 0
        for idx in range(num_parts):
            imdb_infos_data = self.db.get("catalog", f"{catalog_id}.{idx}")
            if imdb_infos_data is None:
                continue
            imdb_infos = imdb_infos_data.get("imdb_info")
            if imdb_infos is None:
                continue
            for imdb_info in imdb_infos:
                imdb_id = imdb_info.get("id")
                imdb_data = imdb_info.get("type")
                imdb_genres = imdb_info.get("genres") or []
                imdb_year = imdb_info.get("year") or ""
                data = ImdbInfo(id=imdb_id, type=CatalogType(imdb_data), genres=imdb_genres, year=imdb_year)
                results.append(data)
        return results

    def set_catalog_schemas(self, catalog_id, imdbInfos: list[ImdbInfo], expiration_date: str) -> bool:
        self.log.info("Setting catalog schemas...")
        idx = 0
        for infos in utils.divide_chunks(imdbInfos, self.__max_cache_size):
            data = []
            for info in infos:
                imdb_info = {
                    "id": info.id,
                    "type": info.type.value.lower(),
                    "genres": info.genres,
                    "year": info.year,
                }
                data.append(imdb_info)
            self.db.set("catalog", f"{catalog_id}.{idx}", {"imdb_info": data})
            idx += 1

        data = {"num_parts": idx, "expiration_date": expiration_date}
        return self.db.set("catalog", f"{catalog_id}", data)

    def set_catalog_metas(self, metas: dict) -> bool:
        self.log.info("Setting catalog metas...")
        if metas is None:
            self.log.info("No metas to set")
            return True
        current_metas = self.get_catalog_metas()
        if current_metas == metas:
            self.log.info("No changes in catalog metas")
            return True
        current_metas.update(metas)
        num_parts = self.__push_all_parts(
            collection="cache", document="metadata", chunk_size=self.__max_cache_size, data=current_metas
        )

        data = {"num_parts": num_parts}
        return self.db.set("cache", "metadata", data)

    def get_catalog_metas_info(self) -> dict:
        return self.db.get("cache", "metadata") or {}

    def get_catalog_metas(self) -> dict:
        results = {}
        data = self.get_catalog_metas_info()
        if data is None:
            return results

        num_parts = data.get("num_parts") or 0
        return self.__fetch_all_parts(collection="cache", document="metadata", num_parts=num_parts) or {}

    def get_catalog_translations_info(self, lang: str) -> dict:
        return self.db.get("cache", f"{lang}_translations") or {}

    def set_catalog_translations(self, metas: dict, lang: str) -> bool:
        self.log.info(f"Setting catalog {lang} translations...")
        if metas is None:
            self.log.info("No translations to set")
            return True
        lang_meta = {}
        for key, value in metas.items():
            lang_meta[key] = value.get(lang)
        current_metas = self.get_catalog_translations(lang=lang)
        if current_metas == lang_meta:
            self.log.info("No changes in catalog translations")
            return True
        current_metas.update(lang_meta)
        num_parts = self.__push_all_parts(
            collection="cache",
            document=f"{lang}_translations",
            chunk_size=self.__max_cache_size,
            data=current_metas,
        )

        data = {"num_parts": num_parts}
        return self.db.set("cache", f"{lang}_translations", data)

    def get_all_catalog_translations(self) -> dict:
        combined = {}

        for lang in self.supported_langs.values():
            for key, value in self.get_catalog_translations(lang=lang).items():
                if key not in combined:
                    combined[key] = {}
                combined[key][lang] = value

        return combined

    def get_catalog_translations(self, lang: str) -> dict:
        results = {}
        data = self.get_catalog_translations_info(lang=lang)
        if data is None:
            return results

        num_parts = data.get("num_parts") or 0
        return (
            self.__fetch_all_parts(collection="cache", document=f"{lang}_translations", num_parts=num_parts)
            or {}
        )

    def get_tmdb_ids_cache_info(self) -> dict:
        return self.db.get("cache", "tmdb_ids") or {}

    def get_tmdb_ids_cache(self) -> dict:
        results = {}
        data = self.get_tmdb_ids_cache_info()
        if data is None:
            return results

        num_parts = data.get("num_parts") or 0
        results = self.__fetch_all_parts(collection="cache", document="tmdb_ids", num_parts=num_parts) or {}
        return results

    def set_tmdb_ids_cache(self, tmdb_cache: dict) -> bool:
        self.log.info("Setting tmdb cache...")
        if tmdb_cache is None:
            self.log.info("No tmdb cache to set")
            return tmdb_cache
        last_cache = self.get_tmdb_ids_cache()
        if last_cache == tmdb_cache:
            self.log.info("No changes in tmdb cache")
            return True
        last_cache.update(tmdb_cache)

        num_parts = self.__push_all_parts(
            collection="cache", document="tmdb_ids", chunk_size=self.__max_cache_size, data=last_cache
        )

        data = {"num_parts": num_parts}
        return self.db.set("cache", "tmdb_ids", data)

    def __fetch_all_parts(self, collection: str, document: str, num_parts: int) -> dict:

        def document_thread(**kwargs):
            idx = kwargs.get("index", None)
            result = self.db.get(collection, f"{document}.{idx}") or {}
            self.log.info(f"Pulled {document}.{idx} from {collection}")
            return result

        results = {}
        list_results = utils.parallel_for(document_thread, items=range(num_parts))
        for result in list_results:
            results.update(result)
        return results

    def __push_all_parts(self, collection: str, document: str, chunk_size: int, data: dict):
        def document_thread(**kwargs):
            new_data = {}
            idx = kwargs.get("index") or 0
            keys = kwargs.get("item") or []
            for key in keys:
                value = data.get(key, None)
                if value is not None:
                    new_data[key] = value

            self.db.set("cache", f"{document}.{idx}", new_data)
            self.log.info(f"Pushed {document}.{idx} to {collection}")

        data_list = list(data.keys())
        total_num_parts = len(data_list) // chunk_size
        self.log.info(f"Pushing {total_num_parts} parts to {collection}")
        chunks = utils.divide_chunks(data_list, chunk_size)
        utils.parallel_for(document_thread, items=chunks, data=data)
        return total_num_parts

from pathlib import Path

import orjson
from BetterJSONStorage import BetterJSONStorage
from tinydb import TinyDB

from lib import env
from lib.providers.catalog_info import ImdbInfo


class DatabaseManager:
    def __init__(self, log):
        self.log = log
        self.__local_dbs: dict[str, Path] = {
            "manifest": Path("db/manifest.db"),
            "catalogs": Path("db/catalogs.db"),
            "tmdb_ids": Path("db/tmdb_ids.db"),
            "metas": Path("db/metas.db"),
        }

        self.__cached_tmdb_ids: dict = {}
        self.__cached_manifest: dict = {}
        self.__cached_catalogs: dict = {}
        self.__cached_metas: dict = {}

        self.update_cache()

    def update_cache(self):
        self.__cached_tmdb_ids = self.get_tmdb_ids()
        self.__cached_manifest = self.get_manifest()
        self.__cached_catalogs = self.get_catalogs()
        self.__cached_metas = self.get_metas()

    @property
    def cached_tmdb_ids(self) -> dict:
        return self.__cached_tmdb_ids

    @property
    def cached_manifest(self) -> dict:
        return self.__cached_manifest

    @property
    def cached_catalogs(self) -> dict:
        return self.__cached_catalogs

    @property
    def cached_metas(self) -> dict:
        return self.__cached_metas

    def get_tmdb_ids(self) -> dict:
        return self.__db_get_all("tmdb_ids")

    def get_manifest(self) -> dict:
        return self.__db_get_all("manifest")

    def get_metas(self) -> dict:
        return self.__db_get_all("metas")

    def get_catalogs(self) -> dict:
        catalogs = self.__db_get_all("catalogs") or {}
        for key, value in catalogs.items():
            if not isinstance(value, dict):
                continue
            data = value.get("data") or []
            conv_data = []
            for item in data:
                if isinstance(item, dict):
                    conv_data.append(ImdbInfo.from_dict(item))
            value.update({"data": conv_data})
            catalogs.update({key: value})
        return catalogs

    def update_tmbd_ids(self, tmdb_ids: dict):
        self.__db_set_all("tmdb_ids", tmdb_ids)
        self.__cached_tmdb_ids = self.get_tmdb_ids()

    def update_metas(self, metas: dict):
        self.__db_set_all("metas", metas)
        self.__cached_metas = self.get_metas()

    def update_manifest(self, manifest: dict):
        self.__db_set_all("manifest", manifest)
        self.__cached_manifest = self.get_manifest()

    def update_catalogs(self, catalogs: dict):
        for key, value in catalogs.items():
            if not isinstance(value, dict):
                continue
            data = value.get("data") or []
            conv_data = []
            for item in data:
                if isinstance(item, ImdbInfo):
                    conv_data.append(item.to_dict())
            value.update({"data": conv_data})
            catalogs.update({key: value})
        self.__db_set_all("catalogs", catalogs)
        self.__cached_catalogs = self.get_catalogs()

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

    def __db_get_all(self, document: str) -> dict:
        try:
            path = self.__local_dbs.get(document)
            if not isinstance(path, Path):
                return {}
            with TinyDB(path, access_mode="r+", option=orjson.OPT_NAIVE_UTC, storage=BetterJSONStorage) as db:
                docs = db.all()
                result = {}
                for doc in docs:
                    key = doc.get("key")
                    value = doc.get("value")
                    if key is not None and value is not None:
                        result[key] = value
                return result
        except Exception as e:
            self.log.error(f"Failed to read from db: {e}")
            return {}

    def __db_set_all(self, document: str, items: dict) -> bool:
        try:
            path = self.__local_dbs.get(document)
            if not isinstance(path, Path):
                return False
            with TinyDB(path, access_mode="r+", option=orjson.OPT_NAIVE_UTC, storage=BetterJSONStorage) as db:
                db.truncate()
                item_list = []
                for key, value in items.items():
                    item_list.append({"key": key, "value": value})
                db.insert_multiple(item_list)
            return True
        except Exception as e:
            self.log.error(f"Failed to write to db: {e}")
            return False

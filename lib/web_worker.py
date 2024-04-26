import hashlib
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta

from builder import Builder
from lib import db_manager, log, utils
from lib.apis.rpdb import RPDB
from lib.apis.trakt import Trakt
from lib.model.catalog_type import CatalogType
from lib.model.catalog_web import CatalogWeb
from lib.providers.catalog_info import ImdbInfo
from lib.providers.catalog_provider import CatalogProvider


class WebWorker:
    def __init__(self) -> None:
        log.info(f"::=> Initializing {self.__class__.__name__}...")
        self.__rpdb_api = RPDB()
        self.__provider = CatalogProvider()
        self.__builder: Builder = Builder()
        self.__is_working: bool = False

        self.__cached_user_configs: dict = {}

        self.__cached_catalogs: dict = {}

        self.__last_update: datetime = datetime.now()

        self.__update_interval = self.get_update_interval()
        self.__background_threading_0 = threading.Thread(
            name="Catalog Service", target=self.__background_catalog_updater
        )
        self.__background_threading_0.start()
        self.__manifest_name = db_manager.cached_manifest.get("name", "Unknown")
        self.__manifest_version = db_manager.cached_manifest.get("version", "Unknown")
        log.info(f"::=>[Manifest Name] {self.__manifest_name}")
        log.info(f"::=>[Manifest Version] {self.__manifest_version}")

    @property
    def manifest_name(self):
        return self.__manifest_name

    @property
    def manifest_version(self):
        return self.__manifest_version

    def get_update_interval(self) -> int:
        current_time = datetime.utcnow()
        tar_time = current_time + timedelta(days=1)
        tar_time = tar_time.replace(hour=3, minute=0, second=0, microsecond=0)

        log.info(f"::=>[Update Schedule] next update will be at {tar_time.date()} {tar_time.time()}")
        diff_time = tar_time - current_time
        return round(diff_time.total_seconds())

    def add_node(self, tree: CatalogWeb, path, node):
        if len(path) == 1:
            tree.add_child(node)
        else:
            for child in tree.children:
                if child.id == path[0]:
                    self.add_node(child, path[1:], node)
                    return
            new_node_name = path[0].replace("_", " ").title()
            new_node = CatalogWeb(path[0], new_node_name)
            tree.add_child(new_node)
            self.add_node(new_node, path[1:], node)

    def build_tree(self, data):
        tree = CatalogWeb("", "Root")
        for item in data:
            item_id: str = item["id"]
            item_path: list[str] = item_id.split(".")
            item_name: str = item_path[-1].replace("_", " ").title()
            node = CatalogWeb(item_id, item_name, False)
            self.add_node(tree, item_path, node)
        return tree

    def get_web_catalogs(self) -> list:
        config_manifest = db_manager.cached_manifest
        tmp_catalogs = config_manifest.get("catalogs", [])
        nested_catalogs = self.build_tree(tmp_catalogs).children
        web_catalogs = [nested_catalog.to_dict() for nested_catalog in nested_catalogs]
        return web_catalogs

    def get_web_config(self) -> dict:
        return db_manager.get_web_config(self.get_web_catalogs())

    def convert_config(self, configs: str) -> dict:
        result = {}
        splited_configs = configs.split("|") if "|" in configs else [configs]
        for config in splited_configs:
            if "=" not in config:
                continue
            try:
                key, value = config.split("=")
                result.update({key: value})
            except ValueError:
                continue
        return result

    def remove_manifest_catalogs(self, manifest: dict) -> dict:
        manifest.update({"catalogs": []})
        return manifest

    def get_configured_manifest(self, base_url: str, configs: str | None) -> dict:
        config_manifest = deepcopy(db_manager.cached_manifest)
        config_manifest.update({"logo": f"{base_url}logo.png"})
        config_manifest.update({"background": f"{base_url}background.png"})
        config_manifest.update({"version": self.manifest_version})
        config_manifest.update({"last_update": str(datetime.now())})

        if configs is None:
            log.info("::=>[Config] No user config found")
            return self.remove_manifest_catalogs(config_manifest)
        converted_configs = self.convert_config(configs)
        user_config = converted_configs.get("catalogs", None)

        if user_config is None:
            log.info("::=>[Config] No user config found")
            return self.remove_manifest_catalogs(config_manifest)

        user_config = self.__cached_user_configs.get(user_config, None)
        if user_config is None:
            log.info("::=>[Config] No user config found")
            return self.remove_manifest_catalogs(config_manifest)

        self.__cached_user_configs.pop(user_config)
        parsed_config = user_config.split(",")
        if len(parsed_config) == 0:
            log.info("::=>[Config] No user config found")
            return self.remove_manifest_catalogs(config_manifest)

        tmp_catalogs = config_manifest.get("catalogs", [])
        new_catalogs = []
        for value in parsed_config:
            for catalog in tmp_catalogs:
                catalog_id = catalog.get("id", None)
                if catalog_id is None:
                    continue
                md5 = hashlib.md5(catalog_id.encode()).hexdigest()[:5]
                if md5 == value:
                    new_catalogs.append(catalog)

            config_manifest.update({"behaviorHints": {"configurable": True, "configurationRequired": False}})
        config_manifest.update({"catalogs": new_catalogs})
        return config_manifest

    def set_user_config(self, config: str) -> str:
        config_id = hashlib.md5(config.encode()).digest().hex()
        self.__cached_user_configs.update({config_id: config})
        return config_id

    def get_trakt_auth_url(self) -> str:
        return Trakt().get_authorization_url()

    def get_trakt_access_token(self, code: str) -> str | None:
        return Trakt().get_access_token(code)

    def __get_trakt_recommendations(self, id: str, access_token: str) -> list:
        trakt_metas = []
        if id == "recommendations.movie":
            trakt_metas = self.__builder.get_catalog(
                provider_id="trakt",
                schema=f"request_type=recommendations&access_token={access_token}",
                c_type=CatalogType.MOVIES,
            )
        elif id == "recommendations.series":
            trakt_metas = self.__builder.get_catalog(
                provider_id="trakt",
                schema=f"request_type=recommendations&access_token={access_token}",
                c_type=CatalogType.SERIES,
            )
        return trakt_metas

    def get_meta(self, id: str, s_type: str, config: str | None) -> dict:
        lang_key = "en"
        if isinstance(config, str) and config != "":
            converted_configs = self.convert_config(config)
            if converted_configs is not None:
                lang_key = converted_configs.get("lang", None)
        imdb_id = id.replace("cyberflix:", "")
        original_meta = self.__provider.cinemeta.get_meta(id=imdb_id, s_type=s_type) or {}
        meta = original_meta.get("meta") or {}
        if lang_key != "en":
            meta = self.__translate_meta(item=meta, lang=lang_key)
        return {"meta": meta}

    def get_configured_catalog(self, id: str, extras: str | None, config: str | None) -> dict:
        catalog_ids = self.catalogs.get(id, [])
        parsed_extras = self.__extras_parser(extras)
        genre = parsed_extras.get("genre", None)
        skip = parsed_extras.get("skip", 0)
        rpdb_key = None
        trakt_key = None
        lang_key = "en"
        if config is not None:
            converted_configs = self.convert_config(config)
            if converted_configs is not None:
                rpdb_key = converted_configs.get("rpgb", None)
                trakt_key = converted_configs.get("trakt", None)
                lang_key = converted_configs.get("lang", None)

        if trakt_key is not None:
            trakt_metas = self.__get_trakt_recommendations(id, trakt_key)
            catalog_ids.extend(trakt_metas)

        catalog_ids = self.__filter_meta(catalog_ids, genre, skip)
        metas = self.__provider.get_catalog_metas(catalog_info=catalog_ids).get("metas", [])
        if lang_key != "en":
            metas = utils.parallel_for(self.__translate_meta, items=metas, lang=lang_key)

        if rpdb_key is not None:
            metas = self.__rpdb_api.replace_posters(metas=metas, api_key=rpdb_key, lang=lang_key or "en")
        if lang_key != "en":
            for meta in metas:
                imdb_id = meta.get("id") or ""
                if imdb_id.startswith("cyberflix:"):
                    continue
                meta.update({"id": f"cyberflix:{imdb_id}"})
        return {"metas": metas}

    def __filter_meta(self, items: list[ImdbInfo], genre: str | None, skip: int) -> list:
        new_items = []
        if genre is not None:
            if genre.isnumeric():
                for item in items:
                    if genre != item.year:
                        continue
                    new_items.append(item)
            else:
                # this is for backward compatibility
                genre = self.__provider.cinemeta.get_simplified_genre(genre) or genre
                for item in items:
                    if genre not in item.genres:
                        continue
                    new_items.append(item)
        else:
            new_items = items

        min_step = min(skip + 25, len(new_items))
        return new_items[:min_step]

    def __translate_meta(self, **kwargs) -> dict:
        meta = kwargs.get("item", None)
        if isinstance(meta, dict):
            lang = kwargs.get("lang", "en")
            imdb_id = meta.get("id", None)
            title = meta.get("name", None)
            translation = self.__builder.get_translation(imdb_id, title, lang)
            if translation is None:
                return meta
            t_name = translation.get("name") or meta.get("name") or ""
            t_description = translation.get("description") or meta.get("description") or ""
            t_poster = translation.get("poster") or meta.get("poster") or ""
            meta.update({"name": t_name, "description": t_description, "poster": t_poster})
            return meta
        return meta

    @property
    def catalogs(self) -> dict:
        return self.__cached_catalogs

    @property
    def manifest(self):
        return db_manager.cached_manifest

    @property
    def last_update(self):
        return self.__last_update

    def load_catalogs(self):
        catalog_dict = {}
        catalogs_names = db_manager.cached_manifest.get("catalogs", [])

        def __get_schema(**kwargs):
            catalog = kwargs.get("item", None)
            if catalog is None:
                return None
            catalog_name = catalog.get("id", None)
            cached_items = db_manager.get_catalog_schemas(catalog_name)
            log.info(f"::=>[Catalog] {catalog_name} has {len(cached_items)} items")
            return {catalog_name: cached_items}

        results = utils.parallel_for(__get_schema, items=catalogs_names)
        for result in results:
            if result is None:
                continue
            catalog_dict.update(result)

        return catalog_dict

    def force_update(self):
        log.info("::=>[Update Triggered]")
        if self.__is_working:
            log.info("::=>[Update Skipped]")
            return
        self.__is_working = True
        self.__builder.build()
        db_manager.update_manifest()
        self.__cached_catalogs: dict = self.load_catalogs()
        self.__last_update = datetime.utcnow()
        self.__is_working = False

        log.info("::=>[Update Finished]")

    def __background_catalog_updater(self):
        log.info("::=>[Update Service Started]")
        self.__cached_catalogs: dict = self.load_catalogs()
        while True:
            time.sleep(self.__update_interval)
            try:
                self.force_update()
            except KeyboardInterrupt:
                log.info("KeyboardInterrupt")
                sys.exit(0)
            except Exception as e:
                log.info(f"Error on update_catalog: {e}")

            self.__update_interval = self.get_update_interval()

    def __extras_parser(self, extras: str | None) -> dict:
        result = {"genre": None, "skip": 0}

        if extras is not None:
            parsed_extras = extras.replace(" & ", "$").split("&")
            for value in parsed_extras:
                if "genre" in value:
                    splited_genre = value.split("=")
                    if len(splited_genre) == 1:
                        continue
                    result.update({"genre": splited_genre[1].replace("$", " & ")})
                elif "skip" in value:
                    splited_skip = value.split("=")
                    if len(splited_skip) == 1:
                        continue
                    result.update({"skip": int(splited_skip[1])})

        return result

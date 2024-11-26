import hashlib
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta

from builder import Builder
from lib import db_manager, env, log
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

        self.__last_update: datetime = datetime.now()

        self.__update_interval = self.get_update_interval()
        self.__background_threading_0 = threading.Thread(
            name="Catalog Service", target=self.__background_catalog_updater
        )

        if len(db_manager.cached_catalogs) == 0:
            log.info("::=>[Catalogs] No catalogs found in local cache, fetching...")
            self.__update_interval = 0
        else:
            self.__manifest_name = db_manager.cached_manifest.get("name", "Unknown")
            self.__manifest_version = db_manager.cached_manifest.get("version", "Unknown")
            log.info(f"::=>[Manifest Name] {self.__manifest_name}")
            log.info(f"::=>[Manifest Version] {self.__manifest_version}")
            for key, value in db_manager.cached_catalogs.items():
                data = value.get("data") or []
                log.info(f"::=>[Catalog] {key} - {len(data)} items")

        self.__background_threading_0.start()

    @property
    def manifest_name(self):
        return self.__manifest_name

    @property
    def manifest_version(self):
        return self.__manifest_version

    def get_update_interval(self) -> int:
        current_time = datetime.now()
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
        config_manifest.update({"name": env.APP_NAME})
        config_manifest.update({"logo": f"{base_url}logo.png"})
        config_manifest.update({"background": f"{base_url}background.png"})
        config_manifest.update({"version": self.manifest_version})
        config_manifest.update({"last_update": str(datetime.now())})

        if configs is None:
            return self.remove_manifest_catalogs(config_manifest)
        converted_configs = self.convert_config(configs)
        config = converted_configs.get("catalogs", None)

        if config is None:
            return self.remove_manifest_catalogs(config_manifest)

        parsed_config = config.split(",")
        if len(parsed_config) == 0:
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
        imdb_id = id.replace("cyberflix:", "")
        original_meta = self.__provider.cinemeta.get_meta(id=imdb_id, s_type=s_type) or {}
        meta = original_meta.get("meta") or {}
        return {"meta": meta}

    async def get_configured_catalog(self, id: str, extras: str | None, config: str | None) -> dict:
        catalog = db_manager.cached_catalogs.get(id) or {}
        catalog_ids = catalog.get("data") or []


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
        catalogs_ids_not_cached = []
        metas = []
        for item in catalog_ids:
            if isinstance(item, ImdbInfo):
                meta = db_manager.cached_metas.get(item.id)
                if meta is None:
                    catalogs_ids_not_cached.append(item)
                    continue
                metas.append(meta)

        if len(catalogs_ids_not_cached) > 0:
            keys = [item.id for item in catalogs_ids_not_cached]
            new_metas = db_manager.get_metas_by_keys(keys)
            metas.extend(new_metas.values())

        new_cached_metas = {}
        for meta in metas:
            meta_id = meta.get("id") or None
            if meta_id is None:
                continue
            for item in catalog_ids:
                if isinstance(item, ImdbInfo) and item.id == meta_id:
                    new_cached_metas.update({item.id: meta})
                    break
        db_manager.cached_metas.update(new_cached_metas)

        sorted_metas = []
        for item in catalog_ids:
            if not isinstance(item, ImdbInfo):
                continue
            for meta in metas:
                if meta.get("id") == item.id:
                    sorted_metas.append(meta)
                    break

        if rpdb_key is not None:
            sorted_metas = self.__rpdb_api.replace_posters(
                metas=sorted_metas, api_key=rpdb_key, lang=lang_key or "en"
            )

        return {
            "metas": sorted_metas,
            "total": len(sorted_metas)
        }

    def __filter_meta(self, items: list[ImdbInfo], genre: str | None, skip: int) -> list:
        new_items = []
        if genre is not None:
            if genre.isnumeric():
                for item in items:
                    if genre != item.year:
                        continue
                    new_items.append(item)
            else:
                genre = self.__provider.cinemeta.get_simplified_genre(genre) or genre
                for item in items:
                    if genre not in item.genres:
                        continue
                    new_items.append(item)
        else:
            new_items = items

        page_size = 25
        min_step = min(skip + page_size, len(new_items))
        return new_items[skip:min_step]

    @property
    def manifest(self):
        return db_manager.cached_manifest

    @property
    def last_update(self):
        return self.__last_update

    def get_recent_changes(self) -> dict:
        recent_changes = db_manager.get_recent_changes()
        report = {
            "summary": {
                "total_changes": len(recent_changes),
                "last_update": recent_changes[0]["timestamp"] if recent_changes else None,
            },
            "changes_by_table": {},
            "details": recent_changes
        }

        for change in recent_changes:
            table = change["table_name"]
            if table not in report["changes_by_table"]:
                report["changes_by_table"][table] = {
                    "deletions": 0,
                    "updates": 0,
                    "insertions": 0
                }

            report["changes_by_table"][table]["deletions"] += len(change["deleted_keys"])
            report["changes_by_table"][table]["updates"] += len(change["updated_keys"])
            report["changes_by_table"][table]["insertions"] += len(change["inserted_keys"])

        return report

    def force_update(self):
        log.info("::=>[Update Triggered]")
        if self.__is_working:
            log.info("::=>[Update Skipped] Already working")
            return
        try:
            self.__is_working = True
            self.__builder.build()
            db_manager.update_cache()

            # Verify the update
            if not self.verify_update():
                raise Exception("Update verification failed - no catalogs found")

            self.__last_update = datetime.now()
            log.info("::=>[Update Finished]")
        except Exception as e:
            log.error(f"::=>[Update Failed] Error: {str(e)}")
            raise
        finally:
            self.__is_working = False

    def __background_catalog_updater(self):
        log.info("::=>[Update Service Started]")
        max_retries = 3
        
        while True:
            time.sleep(self.__update_interval)
            
            for attempt in range(max_retries):
                try:
                    self.force_update()
                    break
                except Exception as e:
                    log.error(f"::=>[Update Failed] Attempt {attempt + 1}/{max_retries}: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(60)  # Wait before retry
                    else:
                        log.error("::=>[Update Failed] Max retries reached")
            
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

    def verify_update(self):
        log.info("::=>[Verify] Checking catalog updates...")

        # Check catalog counts
        catalog_count = len(db_manager.cached_catalogs)
        log.info(f"::=>[Verify] Found {catalog_count} catalogs in cache")

        # Check last modified timestamps
        recent_changes = db_manager.get_recent_changes()
        if recent_changes:
            last_change = recent_changes[0]["timestamp"]
            log.info(f"::=>[Verify] Last change recorded at: {last_change}")

        return catalog_count > 0

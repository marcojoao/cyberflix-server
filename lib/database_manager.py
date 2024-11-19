from supabase import create_client

from lib import env
from lib.providers.catalog_info import ImdbInfo

from datetime import datetime
from collections import OrderedDict


class DatabaseManager:
    def __init__(self, log=None):
        self.log = log
        self.supabase = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

        try:
            _ = self.supabase.rpc('manifest').execute()
            self.log.info("Database connection successful")
        except Exception as e:
            self.log.warning(f"Database health check failed (this is normal on first run): {str(e)}")

        # Load all data into memory at startup
        self.__cached_data = {
            "manifest": self.get_manifest(),
            "catalogs": self.get_catalogs(),
            "tmdb_ids": self.get_tmdb_ids(),
            "metas": {},
        }

        # # Start background loading of metas
        # import threading
        # threading.Thread(target=self.__load_metas_background, daemon=True).start()

    def __load_metas_background(self):
        """Load metas in the background and update the cache."""
        try:
            self.__cached_data["metas"] = self.get_metas()
            self.log.info("Metas loaded successfully in background")
        except Exception as e:
            self.log.error(f"Failed to load metas in background: {e}")

    def __db_update_changes(self, table_name: str, new_items: dict) -> bool:
        try:
            existing_items = self.__cached_data.get(table_name, {})
            keys_to_delete = set(existing_items.keys()) - set(new_items.keys())
            keys_to_update = set()
            keys_to_insert = set()
            # Preserve order by using list of tuples instead of sets
            ordered_changes = []
            for key, value in new_items.items():
                if key not in existing_items:
                    keys_to_insert.add(key)
                    ordered_changes.append(("insert", key))
                elif existing_items[key] != value:
                    keys_to_update.add(key)
                    ordered_changes.append(("update", key))

            if keys_to_delete or keys_to_update or keys_to_insert:
                change_record = {
                    "table_name": table_name,
                    "deleted_keys": list(keys_to_delete),
                    "updated_keys": list(keys_to_update),
                    "inserted_keys": list(keys_to_insert), # Add ordered changes
                    "timestamp": datetime.now().isoformat()
                }
                self.supabase.table("changes").insert(change_record).execute()

            return True

        except Exception as e:
            self.log.error(f"Failed to update {table_name}: {e}")
            raise

    @property
    def cached_tmdb_ids(self) -> dict:
        return self.__cached_data["tmdb_ids"]

    @property
    def cached_manifest(self) -> dict:
        return self.__cached_data["manifest"]

    @property
    def cached_catalogs(self) -> dict:
        return self.__cached_data["catalogs"]

    @property
    def cached_metas(self) -> dict:
        return self.__cached_data["metas"]

    def get_tmdb_ids(self) -> dict:
        try:
            all_tmdb_ids = {}
            page_size = 1000
            start = 0

            while True:
                # Add retry logic for each page
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = self.supabase.table("tmdb_ids") \
                            .select("key, value") \
                            .range(start, start + page_size - 1) \
                            .execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)  # Wait 1 second before retrying

                if not response.data:
                    break

                all_tmdb_ids.update({item['key']: item['value'] for item in response.data})

                if len(response.data) < page_size:
                    break

                start += page_size
            return all_tmdb_ids
        except Exception as e:
            self.log.error(f"Failed to read from tmdb_ids: {e}")
            raise

    def get_manifest(self) -> dict:
        try:
            response = self.supabase.table("manifest").select("key, value").execute()
            if not response.data:
                return {}
            return {item['key']: item['value'] for item in response.data}
        except Exception as e:
            self.log.error(f"Failed to read from manifest: {e}")
            raise

    def get_metas(self) -> dict:
        try:
            all_metas = {}
            page_size = 1000
            start = 0
            while True:
                # Add retry logic for each page
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = self.supabase.table("metas") \
                            .select("key, value") \
                            .range(start, start + page_size - 1) \
                            .execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)  # Wait 1 second before retrying

                if not response.data:
                    break

                all_metas.update({item['key']: item['value'] for item in response.data})

                if len(response.data) < page_size:
                    break

                start += page_size

            return all_metas
        except Exception as e:
            self.log.error(f"Failed to read from metas: {e}")
            raise

    def get_catalogs(self) -> OrderedDict:
        try:
            all_catalogs = OrderedDict()
            page_size = 1000
            start = 0

            while True:
                response = self.supabase.table("catalogs") \
                    .select("key, value") \
                    .range(start, start + page_size - 1) \
                    .execute()

                if not response.data:
                    break

                catalogs_page = {item['key']: item['value'] for item in response.data}

                for key, value in catalogs_page.items():
                    if not isinstance(value, dict):
                        continue
                    data = value.get("data") or []
                    conv_data = []
                    for item in data:
                        if isinstance(item, dict):
                            conv_data.append(ImdbInfo.from_dict(item))
                    value.update({"data": conv_data})
                    all_catalogs[key] = value

                if len(response.data) < page_size:
                    break

                start += page_size

            return all_catalogs
        except Exception as e:
            self.log.error(f"Failed to read from catalogs: {e}")
            raise

    def update_tmdb_ids(self, tmdb_ids: dict):
        try:
            existing_tmdb_ids = self.get_tmdb_ids()
            chunk_size = 1000
            # Find records that need to be updated or inserted
            updates = {}
            for key, value in tmdb_ids.items():
                if key not in existing_tmdb_ids or existing_tmdb_ids[key] != value:
                    updates[key] = value

            if not updates:
                return  # No changes needed
            # Process updates in chunks
            update_items = list(updates.items())
            for i in range(0, len(update_items), chunk_size):
                chunk = dict(update_items[i:i + chunk_size])
                data = [{"key": key, "value": value} for key, value in chunk.items()]
                
                # Add retry logic for each chunk
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.supabase.table("tmdb_ids").upsert(data).execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        self.log.warning(f"Upsert retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)
                
                self.log.info(f"Processed TMDB chunk {i//chunk_size + 1}/{(len(update_items) + chunk_size - 1)//chunk_size}")
            
            # Record the changes and update cache
            self.__db_update_changes("tmdb_ids", tmdb_ids)
            self.__cached_data["tmdb_ids"] = self.get_tmdb_ids()
        except Exception as e:
            self.log.error(f"Failed to update tmdb_ids: {e}")
            raise

    def update_metas(self, metas: dict):
        try:
            # Split data into smaller chunks (e.g., 100 items per chunk)
            chunk_size = 1000
            metas_items = list(metas.items())

            for i in range(0, len(metas_items), chunk_size):
                chunk = dict(metas_items[i:i + chunk_size])
                data = [{"key": key, "value": value} for key, value in chunk.items()]

                # Add retry logic for each chunk
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.supabase.table("metas").upsert(data).execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)  # Wait 1 second before retrying
                
                # Log progress
                self.log.info(f"Processed metas chunk {i//chunk_size + 1}/{(len(metas_items) + chunk_size - 1)//chunk_size}")
            
            self.__db_update_changes("metas", metas)
            self.__cached_data["metas"] = self.get_metas()
        except Exception as e:
            self.log.error(f"Failed to update metas: {e}")
            raise

    def update_manifest(self, manifest: dict):
        try:

            data = [{"key": key, "value": value} for key, value in manifest.items()]
            self.supabase.table("manifest").upsert(data).execute()
            self.__db_update_changes("manifest", manifest)
            self.__cached_data["manifest"] = self.get_manifest()
        except Exception as e:
            self.log.error(f"Failed to update manifest: {e}")
            raise

    def update_catalogs(self, catalogs: dict):
        try:
            import json
            from datetime import datetime

            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    if isinstance(obj, ImdbInfo):
                        return obj.to_dict()
                    return super().default(obj)


            serializable_catalogs = OrderedDict()
            data = []
            for key, value in catalogs.items():
                if not isinstance(value, dict):
                    continue

                try:
                    serializable_value = json.loads(
                        json.dumps(value, cls=DateTimeEncoder),
                        object_pairs_hook=OrderedDict
                    )
                    serializable_catalogs[key] = serializable_value
                    data.append({"key": key, "value": serializable_value})

                except Exception as e:
                    self.log.error(f"Failed to serialize catalog {key}: {e}")
                    continue

            self.supabase.table("catalogs").upsert(data).execute()
            self.__db_update_changes("catalogs", serializable_catalogs)
            self.__cached_data["catalogs"] = self.get_catalogs()
        except Exception as e:
            self.log.error(f"Failed to update catalogs: {e}")
            raise

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

    def get_metas_by_keys(self, keys: list[str]) -> dict:
        try:
            response = self.supabase.table("metas") \
                    .select("key, value") \
                    .in_("key", keys) \
                    .execute()

            if not response.data:
                return {}
            metas = {item['key']: item['value'] for item in response.data}
            self.__cached_data["metas"].update(metas)
            return metas
        except Exception as e:
            self.log.error(f"Failed to read specific metas: {e}")
            raise

    def get_recent_changes(self, limit: int = 50) -> list:
        """Get the most recent changes."""
        try:
            response = self.supabase.table("changes") \
                .select("*") \
                .order("timestamp", desc=True) \
                .limit(limit) \
                .execute()
            return response.data
        except Exception as e:
            self.log.error(f"Failed to get recent changes: {e}")
            return []
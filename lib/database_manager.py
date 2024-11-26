from supabase import create_client

from lib import env
from lib.providers.catalog_info import ImdbInfo
from lib.utils import parallel_for

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
            page_size = 500

            try:
                total_items = self.supabase.table("tmdb_ids").select("count", count='exact').execute().count
            except Exception as e:
                self.log.warning(f"Failed to get exact count for tmdb_ids, using pagination fallback: {e}")
                total_items = page_size

            ranges = [(i, min(i + page_size - 1, total_items - 1)) 
                     for i in range(0, total_items, page_size)]

            def fetch_range(range_tuple, idx, worker_id):
                start, end = range_tuple
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = self.supabase.table("tmdb_ids") \
                            .select("key, value") \
                            .range(start, end) \
                            .execute()
                        result = {item['key']: item['value'] for item in response.data}
                        # If we got no results and we're using the fallback, we've reached the end
                        if not result and total_items == page_size:
                            return None
                        return result
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)

            results = parallel_for(fetch_range, ranges, max_workers=4)
            for result in results:
                if isinstance(result, dict):
                    all_tmdb_ids.update(result)

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
            page_size = 500
            try:
                total_items = self.supabase.table("metas").select("count", count='exact').execute().count
            except Exception as e:
                self.log.warning(f"Failed to get exact count for metas, using pagination fallback: {e}")
                total_items = page_size

            ranges = [(i, min(i + page_size - 1, total_items - 1)) 
                     for i in range(0, total_items, page_size)]

            def fetch_range(range_tuple, idx, worker_id):
                start, end = range_tuple
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = self.supabase.table("metas") \
                            .select("key, value") \
                            .range(start, end) \
                            .execute()
                        result = {item['key']: item['value'] for item in response.data}
                        if not result and total_items == page_size:
                            return None
                        return result
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        import time
                        time.sleep(1)

            results = parallel_for(fetch_range, ranges, max_workers=4)
            for result in results:
                if isinstance(result, dict):
                    all_metas.update(result)

            return all_metas
        except Exception as e:
            self.log.error(f"Failed to read from metas: {e}")
            raise

    def get_catalogs(self) -> OrderedDict:
        try:
            all_catalogs = OrderedDict()
            page_size = 50
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
            chunk_size = 500
            updates = {}
            for key, value in tmdb_ids.items():
                if key not in existing_tmdb_ids or existing_tmdb_ids[key] != value:
                    updates[key] = value

            if not updates:
                return  # No changes needed
            update_items = list(updates.items())
            for i in range(0, len(update_items), chunk_size):
                chunk = dict(update_items[i:i + chunk_size])
                data = [{"key": key, "value": value} for key, value in chunk.items()]

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

            chunk_size = 500
            metas_items = list(metas.items())

            for i in range(0, len(metas_items), chunk_size):
                chunk = dict(metas_items[i:i + chunk_size])
                data = [{"key": key, "value": value} for key, value in chunk.items()]

                # Add exponential backoff retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.supabase.table("metas").upsert(data).execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        self.log.info(f"Waiting {wait_time} seconds before retry...")
                        import time
                        time.sleep(wait_time)

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

            chunk_size = 10
            serializable_catalogs = OrderedDict()
            catalog_items = list(catalogs.items())

            for i in range(0, len(catalog_items), chunk_size):
                chunk = dict(catalog_items[i:i + chunk_size])
                data = []

                for key, value in chunk.items():
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

                # Add retry logic with exponential backoff
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.supabase.table("catalogs").upsert(data).execute()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            raise
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        self.log.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                        self.log.info(f"Waiting {wait_time} seconds before retry...")
                        import time
                        time.sleep(wait_time)

                # Log progress
                self.log.info(f"Processed catalogs chunk {i//chunk_size + 1}/{(len(catalog_items) + chunk_size - 1)//chunk_size}")

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
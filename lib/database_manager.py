from supabase import create_client

from lib import env
from lib.providers.catalog_info import ImdbInfo

from datetime import datetime


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
            # "metas": self.get_metas()
        }

    def __db_update_changes(self, table_name: str, new_items: dict) -> bool:
        try:

            existing_items = self.__cached_data.get(table_name, {})
            keys_to_delete = set(existing_items.keys()) - set(new_items.keys())
            keys_to_update = set()
            keys_to_insert = set()
            for key, value in new_items.items():
                if key not in existing_items:
                    keys_to_insert.add(key)
                elif existing_items[key] != value:
                    keys_to_update.add(key)

            if keys_to_delete or keys_to_update or keys_to_insert:
                change_record = {
                    "table_name": table_name,
                    "deleted_keys": list(keys_to_delete),
                    "updated_keys": list(keys_to_update),
                    "inserted_keys": list(keys_to_insert),
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
                response = self.supabase.table("tmdb_ids") \
                    .select("key, value") \
                    .range(start, start + page_size - 1) \
                    .execute()

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
                response = self.supabase.table("metas") \
                    .select("key, value") \
                    .range(start, start + page_size - 1) \
                    .execute()
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

    def get_catalogs(self) -> dict:
        try:
            all_catalogs = {}
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

    def update_tmbd_ids(self, tmdb_ids: dict):
        self.__db_update_changes("tmdb_ids", tmdb_ids)
        self.__cached_data["tmdb_ids"] = self.get_tmdb_ids()

    def update_metas(self, metas: dict):
        self.__db_update_changes("metas", metas)
        self.__cached_data["metas"] = self.get_metas()

    def update_manifest(self, manifest: dict):
        self.__db_update_changes("manifest", manifest)
        self.__cached_data["manifest"] = self.get_manifest()

    def update_catalogs(self, catalogs: dict):
        import json
        from datetime import datetime

        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, ImdbInfo):
                    return obj.to_dict()
                return super().default(obj)

        # Create a copy to avoid modifying the original data
        serializable_catalogs = {}

        for key, value in catalogs.items():
            if not isinstance(value, dict):
                continue

            try:
                # Convert the value to JSON-serializable format
                serializable_value = json.loads(
                    json.dumps(value, cls=DateTimeEncoder)
                )
                serializable_catalogs[key] = serializable_value

            except Exception as e:
                self.log.error(f"Failed to serialize catalog {key}: {e}")
                continue

        self.__db_update_changes("catalogs", serializable_catalogs)
        self.__cached_data["catalogs"] = self.get_catalogs()

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
            # Import here to avoid circular dependency
            from lib.utils import parallel_for, divide_chunks

            # Split keys into chunks to avoid too many keys in a single query
            CHUNK_SIZE = 5  # Adjust based on your needs
            
            def fetch_meta(key_chunk, _, __, **kwargs):
                response = self.supabase.table("metas") \
                    .select("key, value") \
                    .in_("key", key_chunk) \
                    .execute()
                
                if not response.data:
                    return {}
                return {item['key']: item['value'] for item in response.data}
            
            # Process chunks in parallel
            chunks = list(divide_chunks(keys, CHUNK_SIZE))
            results = parallel_for(fetch_meta, chunks)
            
            # Combine all results
            combined_metas = {}
            for chunk_result in results:
                combined_metas.update(chunk_result)
                
            # Update cache
            self.__cached_data["metas"].update(combined_metas)
            return combined_metas
            
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
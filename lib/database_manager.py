from supabase import create_client, Client

from lib import env
from lib.providers.catalog_info import ImdbInfo


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
            "metas": self.get_metas()
        }

    def __db_set_all(self, table_name: str, items: dict) -> bool:
        try:
            # Delete existing data
            self.supabase.table(table_name).delete().neq('key', '').execute()

            if items:
                # Insert new data in batches of 1000 to avoid request size limits
                batch_size = 1000
                data = [{"key": k, "value": v} for k, v in items.items()]

                for i in range(0, len(data), batch_size):
                    batch = data[i:i + batch_size]
                    try:
                        self.supabase.table(table_name).upsert(batch).execute()
                    except Exception as e:
                        # If insert fails due to RLS, try upsert
                        if "42501" in str(e):
                            self.log.warning(f"Insert failed, trying upsert for {table_name}")
                            # Use individual upserts as fallback
                            for item in batch:
                                self.supabase.table(table_name).upsert(item).execute()
                        else:
                            raise

            # Update cache
            self.__cached_data[table_name] = items
            return True

        except Exception as e:
            self.log.error(f"Failed to write to {table_name}: {e}")
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
            response = self.supabase.table("tmdb_ids").select("key, value").execute()
            if not response.data:
                return {}
            return {item['key']: item['value'] for item in response.data}
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
            response = self.supabase.table("metas").select("key, value").execute()
            if not response.data:
                return {}
            metas = {item['key']: item['value'] for item in response.data}
            return metas
        except Exception as e:
            self.log.error(f"Failed to read from metas: {e}")
            raise

    def get_catalogs(self) -> dict:
        try:
            response = self.supabase.table("catalogs").select("key, value").execute()
            if not response.data:
                return {}
            catalogs = {item['key']: item['value'] for item in response.data}
            # Process catalog data
            for key, value in catalogs.items():
                if not isinstance(value, dict):
                    continue
                data = value.get("data") or []
                conv_data = []
                for item in data:
                    if isinstance(item, dict):
                        conv_data.append(ImdbInfo.from_dict(item))
                value.update({"data": conv_data})
                catalogs[key] = value
            return catalogs
        except Exception as e:
            self.log.error(f"Failed to read from catalogs: {e}")
            raise

    def update_tmbd_ids(self, tmdb_ids: dict):
        self.__db_set_all("tmdb_ids", tmdb_ids)
        self.__cached_data["tmdb_ids"] = self.get_tmdb_ids()

    def update_metas(self, metas: dict):
        self.__db_set_all("metas", metas)
        self.__cached_data["metas"] = self.get_metas()

    def update_manifest(self, manifest: dict):
        self.__db_set_all("manifest", manifest)
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

        self.__db_set_all("catalogs", serializable_catalogs)
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
import json
import os

from lib import log

FILE_PATH = os.path.dirname(os.path.abspath(__file__))


class Manifest:
    def __init__(self):
        log.info(f"::=> Initializing {self.__class__.__name__}...")
        config_file = os.path.join(FILE_PATH, "addon_meta.json")
        self.__config = self.__load_config(config_file=config_file)

    @property
    def config(self) -> dict:
        return self.__config

    def __load_config(self, config_file: str) -> dict:
        try:
            with open(config_file) as file:
                return json.load(file)
        except OSError as e:
            log.info(f"IO Error: {e}")
            return {}
        except json.JSONDecodeError as e:
            log.info(f"JSON Decode Error: {e}")
            return {}

    def get_meta(self, catalogs_config: list) -> dict:
        data = {
            "id": self.__config["id"],
            "version": self.__config["version"],
            "name": self.__config["name"],
            "description": self.__config["description"],
            "logo": "",
            "behaviorHints": {"configurable": True, "configurationRequired": True},
            "idPrefixes": ["cyberflix:"],
            "resources": ["catalog", "meta"],
            "types": ["series", "movie"],
            "catalogs": catalogs_config,
        }
        return data

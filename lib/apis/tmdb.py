import json

import httpx

from lib import env, log
from lib.model.catalog_type import CatalogType


class TMDB:
    def __init__(self, api_key: str | None = None) -> None:
        self.__url = "https://api.themoviedb.org/3"
        api_key = api_key or env.TMDB_API_KEY
        if api_key is None:
            raise ValueError("TMDB API key is missing")
        self.__api_key = api_key
        self.__headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.5",
        }

    @property
    def url(self) -> str:
        return self.__url

    @property
    def api_key(self) -> str:
        return self.__api_key

    def __request(self, url: str) -> dict | None:
        with httpx.Client() as client:
            try:
                response = client.get(url, headers=self.__headers, timeout=1.5)
                if response.status_code == 200:
                    buffer = response.content
                    return json.loads(buffer)
                log.info(f"Failed to fetch {url}, skipping...")
            except Exception as e:
                log.info(e)
        return None

    def request_page(self, url: str) -> list:
        resp = self.__request(url)
        nodes = []
        if resp is not None:
            results = resp.get("results", None)
            if results is None or len(results) == 0:
                return nodes
            for result in results:
                # tmdb_id = result.get("id", None)
                # tmdb_type = result.get("media_type", None)
                # node = {"id": tmdb_id, "type": tmdb_type}
                nodes.append(result)
            return nodes
        return nodes

    def find(self, id: str, c_type: CatalogType, external_source: str = "imdb_id") -> dict | None:
        url = (
            f"{self.__url}/find/{id}?api_key={self.api_key}&language=en-US&external_source={external_source}"
        )
        resp = self.__request(url)
        if resp is not None:
            result = None
            movie_results = resp.get("movie_results", None)
            tv_results = resp.get("tv_results", None)
            if c_type == CatalogType.MOVIES:
                result = movie_results
            elif c_type == CatalogType.SERIES:
                result = tv_results
            else:
                if movie_results is not None:
                    result = movie_results
                elif tv_results is not None:
                    result = tv_results
            if result is not None and len(result) > 0:
                return result[0]
        return None

    def get_external_ids(self, tmdb_id: str, c_type: CatalogType) -> dict | None:
        if c_type == CatalogType.ANY:
            return None
        content_type = "movie" if c_type == CatalogType.MOVIES else "tv"
        url = f"{self.__url}/{content_type}/{tmdb_id}/external_ids?api_key={self.__api_key}"
        return self.__request(url)

    def search(self, query: str, c_type: CatalogType | str) -> list | None:
        if isinstance(c_type, str):
            c_type = CatalogType(c_type)
        search_type = "movie" if c_type == CatalogType.MOVIES else "tv"
        url = f"{self.__url}/search/{search_type}?api_key={self.api_key}&query={query}&language=en-US"
        resp = self.__request(url)
        if resp is not None:
            return resp.get("results", None)
        return None

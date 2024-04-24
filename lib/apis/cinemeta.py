import json
import httpx
from lib import log


class Cinemeta:
    def __init__(self) -> None:
        self.__url = "https://cinemeta-live.strem.io/"
        self.__headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
        }

    @property
    def url(self) -> str:
        return self.__url

    def get_meta_bulk(self, ids: list[str], s_type: str) -> list[dict]:
        meta_url = f"https://v3-cinemeta.strem.io/catalog/{s_type}/last-videos/lastVideosIds="
        results = []
        for idx, id in enumerate(ids):
            if idx == 0:
                meta_url += f"{id}"
            elif idx == len(ids) - 1:
                meta_url += f",{id}.json"
            else:
                meta_url += f",{id}"
        with httpx.Client(follow_redirects=True) as client:
            try:
                response = client.get(meta_url, headers=self.__headers, timeout=50)
                if response.status_code == 200:
                    buffer = response.content
                    if buffer is None:
                        return results
                    data = json.loads(buffer)
                    if isinstance(data, dict):
                        metas_detailed = data.get("metasDetailed", [])
                        for meta in metas_detailed:
                            if meta is not None:
                                results.append(meta)
            except Exception as e:
                log.info(e)
        return results

    def get_meta(self, id: str, s_type: str) -> dict | None:
        meta_url = f"{self.__url}meta/{s_type}/{id}.json"
        with httpx.Client(follow_redirects=True) as client:
            try:
                response = client.get(meta_url, headers=self.__headers, timeout=10)
                if response.status_code == 200:
                    buffer = response.content
                    if buffer is None:
                        return None
                    return json.loads(buffer)
            except Exception as e:
                log.info(e)
        return None

    def get_simplified_year(self, year: str) -> str:
        if "–" in year:
            year = year.split("–")[0].strip()
        elif "-" in year:
            year = year.split("-")[0].strip()
        return year

    @staticmethod
    def get_simplified_genre(name: str) -> str | None:
        simplified_genre = {
            "Kids": "Kids",
            "Musical": "Music",
            "TV": "Short",
            "Sci-Fi & Fantasy": "Sci-Fi",
            "Adult": "Adult",
            "Family": "Family",
            "Documentary": "Documentary",
            "Biography": "Documentary",
            "War": "Documentary",
            "Reality-TV": "TV",
            "Sci-Fi": "Sci-Fi",
            "Fantasy": "Fantasy",
            "TV Movie": "TV",
            "Crime": "Crime",
            "Romance": "Romance",
            "History": "History",
            "Action & Adventure": "Action",
            "Action": "Action",
            "Talk-Show": "TV",
            "War & Politics": "Documentary",
            "Horror": "Horror",
            "Sport": "Sport",
            "Western": "Western",
            "Comedy": "Comedy",
            "Music": "Music",
            "Adventure": "Adventure",
            "Soap": "TV",
            "Reality": "TV",
            "Animation": "Animation",
            "Game-Show": "TV",
            "Thriller": "Thriller",
            "News": "TV",
            "Talk": "TV",
            "Science Fiction": "Sci-Fi",
            "Drama": "Drama",
            "Film-Noir": "Drama",
            "Mystery": "Mystery",
        }
        return simplified_genre.get(name, None)

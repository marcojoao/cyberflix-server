import httpx

from lib import env, log


class MDBList:
    def __init__(self, api_key: str | None = None) -> None:
        self.__url = "https://mdblist.com/api/"
        api_key = api_key or env.MDBLIST_API_KEY
        if api_key is None:
            raise ValueError("MDBList API key is missing")
        self.__api_key = api_key
        self.__headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
        }

    @property
    def url(self) -> str:
        return self.__url

    def request_page(
        self,
        schema: str,
        timeout: int = 20,
    ) -> list:
        url = self.__url + schema + f"?apikey={self.__api_key}"
        with httpx.Client() as client:
            resp = client.get(
                url,
                headers=self.__headers,
                timeout=timeout,
            )
            if resp.status_code != 200:
                log.error(f"Failed to fetch {url}, error: {resp.text}")
                return []
            nodes = resp.json()
        return nodes

import json

import httpx

from lib import env, log


class Trakt:
    def __init__(self, client_id: str | None = None) -> None:
        self.__url = "https://api.trakt.tv/"
        self.client_id = client_id or env.TRAKT_CLIENT_ID
        self.client_secret = env.TRAKT_CLIENT_SECRET
        self.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    @property
    def url(self) -> str:
        return self.__url

    def get_authorization_url(self) -> str:
        return f"https://trakt.tv/oauth/authorize?response_type=code&client_id={self.client_id}&redirect_uri={self.redirect_uri}"

    def get_access_token(self, authorization_code: str) -> str | None:
        token_url = "https://trakt.tv/oauth/token"
        payload = {
            "code": authorization_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "authorization_code",
        }
        with httpx.Client() as client:
            try:
                response = client.post(token_url, json=payload, timeout=3)
                if response.status_code == 200:
                    buffer = response.content
                    if buffer is None:
                        return None
                    access_token = json.loads(buffer).get("access_token", None)
                    return access_token
            except Exception as e:
                log.info(e)
        return None

    def __request(self, url: str, access_token: str, timeout: int) -> dict | None:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
            "X-Pagination-Page": "1",
            "X-Pagination-Limit": "100",
        }
        params = {
            "ignore_collected": "false",
            "ignore_watchlisted": "false",
            "page": 1,
            "limit": 100,  # Set pagination limit to 100
        }
        with httpx.Client() as client:
            try:
                response = client.get(url, headers=headers, params=params, timeout=3)
                if response.status_code == 200:
                    buffer = response.content
                    return json.loads(buffer)
                log.info(f"Failed to fetch {url}, skipping...")
            except Exception as e:
                log.info(e)
        return None

    def request_page(self, schema: str, s_type: str, timeout: int = 20) -> list:
        nodes = []
        schema_parts = schema.split("&")
        schema_dict = {}
        for part in schema_parts:
            key, value = part.split("=")
            if value.isdigit():
                value = int(value)
            if isinstance(value, str):
                list_value = value.split(",")
                if len(list_value) > 1:
                    value = list_value
            schema_dict.update({key: value})

        access_token = schema_dict.get("access_token", None)
        if access_token is None:
            return nodes

        request_type = schema_dict.get("request_type", None)
        if request_type is None:
            return nodes

        link = f"{self.__url}{request_type}/{s_type}?access_token={access_token}?ignore_collected=true?ignore_watchlisted=true"

        try:
            access_token = schema.split("access_token=")[1]
            results = self.__request(link, access_token, timeout)
            if results is not None:
                for result in results:
                    imdb_id = result.get("ids", {}).get("imdb", None)
                    if imdb_id is None:
                        continue
                    nodes.append(imdb_id)
                return nodes
            return nodes
        except Exception as e:
            log.info(e)
            return nodes

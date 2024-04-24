import time

import httpx


class AniList:
    def __init__(self) -> None:
        self.__url = "https://graphql.anilist.co"
        self.__headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
        }

    @property
    def url(self) -> str:
        return self.__url

    def get_query(self):
        query = """
            query ($page: Int, $perPage: Int, $format: MediaFormat, $sort: [MediaSort], $season: MediaSeason, $status: MediaStatus) {
                Page(page: $page, perPage: $perPage) {
                    pageInfo { hasNextPage }
                    media(type: ANIME, format: $format, sort: $sort, season: $season, status: $status) {
                        title { english, native }
                    }
                }
            }
        """
        return query

    def request_page(
        self,
        schema: str,
        s_type: str = "TV",
        pages: int = 10,
        timeout: int = 5,
    ) -> list:
        nodes = []
        schema_parts = schema.split("&")
        schema_dict = {}
        try:
            for part in schema_parts:
                key, value = part.split("=")
                if value.isdigit():
                    value = int(value)
                if isinstance(value, str):
                    list_value = value.split(",")
                    if len(list_value) > 1:
                        value = list_value
                schema_dict.update({key: value})
        except ValueError:
            print("Invalid schema, skipping...")
            return nodes

        sort = schema_dict.get("sort") or []
        if isinstance(sort, str):
            sort = sort.split(",") if "," in sort else [sort]

        season = schema_dict.get("season") or None
        status = schema_dict.get("status") or None

        items = []
        query = self.get_query()
        with httpx.Client() as client:
            for page in range(1, pages + 1):
                time.sleep(timeout)

                variables = {"format": s_type, "sort": sort, "page": page, "perPage": 20}
                if season:
                    variables.update({"season": season})
                if status:
                    variables.update({"status": status})
                try:
                    resp = client.post(
                        self.__url,
                        headers=self.__headers,
                        json={"query": query, "variables": variables},
                        timeout=timeout,
                    )
                    if resp.status_code != 200:
                        print(f"Failed to fetch {self.__url}, skipping...")
                        continue
                    data = dict(resp.json())
                    page_data = data.get("data", {}).get("Page", {})
                    media = page_data.get("media", [])
                    has_next_page = (
                        data.get("data", False)
                        .get("Page", False)
                        .get("pageInfo", False)
                        .get("hasNextPage", False)
                        or False
                    )
                    for item in media:
                        data = item.get("title", {})
                        if data is not None:
                            items.append(data)
                    if not has_next_page:
                        break
                except httpx.TimeoutException:
                    print(f"Request timed out, retrying in {timeout} seconds...")
                    continue
                except httpx.HTTPError as e:
                    print(e)
                    continue
        return items

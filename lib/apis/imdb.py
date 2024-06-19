import httpx


class IMDB:
    def __init__(self) -> None:
        self.__url = "https://caching.graphql.imdb.com/"
        self.__headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
        }

    @property
    def url(self) -> str:
        return self.__url

    def advanced_title_search(
        self,
        query: str,
        sort_by: str = "POPULARITY",
        sort_order: str = "ASC",
        locale: str = "en-US",
        count: int = 1,
        types: list[str] = ["tvSeries", "movie"],
        genres: list[str] = [],
    ) -> dict:
        data = {
            "operationName": "AdvancedTitleSearch",
            "variables": {
                "certificateConstraint": {},
                "colorationConstraint": {},
                "creditedCompanyConstraint": {},
                "first": count,
                "genreConstraint": {"allGenreIds": genres},
                "listConstraint": {
                    "inAllLists": [],
                    "inAllPredefinedLists": [],
                    "notInAnyList": [],
                    "notInAnyPredefinedList": [],
                },
                "locale": locale,
                "releaseDateConstraint": {"releaseDateRange": {}},
                "runtimeConstraint": {"runtimeRangeMinutes": {}},
                "sortBy": sort_by,
                "sortOrder": sort_order,
                "titleTextConstraint": {"searchTerm": query},
                "userRatingsConstraint": {"aggregateRatingRange": {}, "ratingsCountRange": {}},
                "titleTypeConstraint": {"anyTitleTypeIds": types},
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "42714660b115c035a3c14572bfd2765c622e2659f7b346e2ee7a1f24296f08e7",
                }
            },
        }
        return data

    def get_award_event(
        self,
        event_id="ev0000003",
        sort_by="POPULARITY",
        sort_order="ASC",
        locale="en-US",
        count=50,
        after_cursor="",
        persisted_query="",
    ) -> dict:
        data = {
            "operationName": "AdvancedTitleSearch",
            "variables": {
                "locale": locale,
                "first": count,
                "sortBy": sort_by,
                "sortOrder": sort_order,
                "awardConstraint": {
                    "allEventNominations": [{"eventId": event_id, "winnerFilter": "WINNER_ONLY"}],
                    "excludeEventNominations": [],
                },
                "after": after_cursor,
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "42714660b115c035a3c14572bfd2765c622e2659f7b346e2ee7a1f24296f08e7",
                }
            },
        }
        return data

    def request_page(
        self,
        schema: str,
        pages: int = 1,
        timeout: int = 20,
    ) -> list:
        nodes = []
        schema = schema.replace(" ", "%20")
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
        search_term = schema_dict.get("searchTerm") or None
        event_id = schema_dict.get("eventId") or None
        sort_by = schema_dict.get("sortBy") or "POPULARITY"
        sort_order = schema_dict.get("sortOrder") or "ASC"
        locale = schema_dict.get("locale") or "en-US"
        count = schema_dict.get("first") or 1
        title_type = schema_dict.get("titleType") or None
        types = schema_dict.get("types") or []
        if isinstance(types, str):
            types = types.split(",") if "," in types else [types]
        genres = schema_dict.get("genres") or []
        if isinstance(genres, str):
            genres = genres.split(",") if "," in genres else [genres]
        last_cursor = ""
        query = {}
        with httpx.Client() as client:
            for _ in range(1, pages + 1):
                if search_term is not None:
                    query = self.advanced_title_search(
                        query=search_term,
                        sort_by=sort_by,
                        sort_order=sort_order,
                        locale=locale,
                        count=count,
                        types=types,
                        genres=genres,
                    )
                elif event_id is not None:
                    query = self.get_award_event(
                        event_id=event_id,
                        sort_by=sort_by,
                        sort_order=sort_order,
                        locale=locale,
                        count=count,
                        after_cursor=last_cursor,
                    )
                else:
                    return nodes
                try:
                    resp = client.post(
                        self.__url,
                        headers=self.__headers,
                        json=query,
                        timeout=timeout,
                    )
                    if resp.status_code != 200:
                        print(f"Failed to fetch {self.__url}, skipping...")
                        continue

                    data = dict(resp.json())
                    advanced_title_search = data.get("data", {}).get("advancedTitleSearch", {})
                    if advanced_title_search is None:
                        continue
                    has_next_page = advanced_title_search.get("pageInfo", {}).get("hasNextPage", False)
                    edges = advanced_title_search.get("edges", [])
                    last_cursor = advanced_title_search.get("pageInfo", {}).get("endCursor", "")
                    for edge in edges:
                        info = edge.get("node", {}).get("title", {})
                        imdb_id = info.get("id", None)
                        title_text = info.get("titleText", None)
                        if title_text is None:
                            continue
                        imdb_title = title_text.get("text", None)
                        if imdb_title is None:
                            continue
                        title_type = info.get("titleType", None)
                        if title_type is None:
                            continue
                        imdb_type = title_type.get("id", None)
                        if imdb_type is None:
                            continue
                        node = {"id": imdb_id, "title": imdb_title, "type": imdb_type}
                        nodes.append(node)
                    if has_next_page is False:
                        break
                except httpx.TimeoutException:
                    print(f"Request timed out, retrying in {timeout} seconds...")
                    continue
                except httpx.HTTPError as e:
                    print(e)
                    continue
        return nodes

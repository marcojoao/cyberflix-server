import time

import httpx


class JustWatch:
    def __init__(self) -> None:
        self.__url = "https://apis.justwatch.com/graphql"
        self.__headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/117.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "content-type": "application/json",
            "App-Version": "3.7.1-web-web",
            "DEVICE-ID": "XFpiKlykEe6wTkKWjpYncw",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    @property
    def url(self) -> str:
        return self.__url

    def __get_search_title_query(self, **kwargs) -> dict:
        search_query = kwargs.get("search_query", "")
        language = kwargs.get("language", "en")
        count = kwargs.get("count", 4)
        data = {
            "operationName": "GetSuggestedTitles",
            "variables": {
                "country": "US",
                "language": language,
                "first": count,
                "filter": {"searchQuery": search_query},
            },
            "query": """
            query GetSuggestedTitles($country: Country!, $language: Language!, $first: Int!, $filter: TitleFilter) {
              popularTitles(country: $country, first: $first, filter: $filter) {
                edges {
                  node {
                    ...SuggestedTitle
                  }
                }
              }
            }
            fragment SuggestedTitle on MovieOrShow {
              objectType
              content(country: $country, language: $language) {
                title
                shortDescription
                posterUrl
                externalIds {
                    imdbId
                }
              }
            }
        """,
        }
        return data

    def __get_popular_titles_query(
        self,
        **kwargs,
    ) -> dict:
        object_types = kwargs.get("objectType", "MOVIE")
        sort_by = kwargs.get("sort", "TRENDING")
        providers = kwargs.get("providers", "nfx")
        country = kwargs.get("country", "GB")
        count = kwargs.get("count", 100)
        language = kwargs.get("language", "en")
        after_cursor = kwargs.get("after_cursor", "")
        if not isinstance(object_types, list):
            object_types = [object_types]
        if not isinstance(providers, list):
            providers = [providers]
        data = {
            "operationName": "GetPopularTitles",
            "variables": {
                "popularTitlesSortBy": sort_by,
                "first": count,
                "platform": "WEB",
                "sortRandomSeed": 0,
                "afterCursor": after_cursor,
                "offset": None,
                "popularTitlesFilter": {
                    "ageCertifications": [],
                    "excludeGenres": [],
                    "excludeProductionCountries": [],
                    "genres": [],
                    "objectTypes": object_types,
                    "productionCountries": [],
                    "packages": providers,
                    "excludeIrrelevantTitles": False,
                    "presentationTypes": [],
                    "monetizationTypes": ["FREE", "FLATRATE", "ADS"],
                },
                "language": language,
                "country": country,
            },
            "query": """
                query GetPopularTitles(
                    $country: Country!,
                    $popularTitlesFilter: TitleFilter,
                    $afterCursor: String,
                    $popularTitlesSortBy: PopularTitlesSorting! = POPULAR,
                    $first: Int!,
                    $language: Language!,
                    $offset: Int = 0,
                    $sortRandomSeed: Int! = 0,
                ) {
                    popularTitles(
                        country: $country,
                        filter: $popularTitlesFilter,
                        offset: $offset,
                        after: $afterCursor,
                        sortBy: $popularTitlesSortBy,
                        first: $first,
                        sortRandomSeed: $sortRandomSeed
                    ) {
                        totalCount
                        pageInfo {
                            startCursor
                            endCursor
                            hasPreviousPage
                            hasNextPage
                        }
                        edges {
                            ...PopularTitleGraphql
                        }
                    }
                }

                fragment PopularTitleGraphql on PopularTitlesEdge {
                    cursor
                    node {
                        objectType
                        content(country: $country, language: $language) {
                            externalIds {
                                imdbId
                            }
                        }
                    }
                }
                """,
        }
        return data

    def search_title(
        self, search_query: str, count: int = 4, language: str = "en", timeout: int = 10
    ) -> list:
        with httpx.Client() as client:
            try:
                query = self.__get_search_title_query(
                    search_query=search_query, language=language, count=count
                )
                if not query:
                    raise ValueError("operationName is not valid")
                resp = client.post(
                    self.__url,
                    headers=self.__headers,
                    json=query,
                    timeout=timeout,
                )
                if resp.status_code != 200:
                    print(f"Failed to fetch {self.__url}, skipping...")
                    return []
                data = dict(resp.json())
                if data is None:
                    print(f"No results found for {search_query}, skipping...")
                    return []
                results = []
                data = data.get("data", {})
                if data is None:
                    print(f"No results found for {search_query}, skipping...")
                    return []
                popular_titles = data.get("popularTitles", {})
                if popular_titles is None:
                    print(f"No results found for {search_query}, skipping...")
                    return []
                edges = popular_titles.get("edges") or []
                for edge in edges:
                    node = edge.get("node", {})
                    content = node.get("content", {})
                    imdb_id = content.get("externalIds", {}).get("imdbId", None)
                    title = content.get("title", None)
                    short_description = content.get("shortDescription", None)
                    poster_url = content.get("posterUrl", None)
                    big_poster_url = None
                    if poster_url is not None:
                        poster_url = poster_url.replace("{profile}", "s166").replace("{format}", "jpeg")
                        poster_url = f"https://images.justwatch.com{poster_url}"
                        big_poster_url = poster_url.replace("s166", "s592")
                    content_type = node.get("objectType", None)
                    translated = title is not None and short_description is not None
                    result = {
                        "imdb_id": imdb_id,
                        "title": title,
                        "short_description": short_description,
                        "poster_url": poster_url,
                        "big_poster_url": big_poster_url,
                        "content_type": content_type,
                        "translated": translated,
                    }

                    results.append(result)
                return results
            except httpx.TimeoutException:
                print(f"Request timed out, retrying in {timeout} seconds...")
                return []
            except httpx.HTTPError as e:
                print(e)
                return []

    def request_page(
        self,
        schema: str,
        pages: int = 1,
        timeout: int = 10,
    ) -> list:
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

        with httpx.Client() as client:
            catalog_ids = []
            for _ in range(1, pages + 1):
                time.sleep(1)
                try:
                    query = self.__get_popular_titles_query(**schema_dict)
                    if not query:
                        raise ValueError("operationName is not valid")
                    resp = client.post(
                        self.__url,
                        headers=self.__headers,
                        json=query,
                        timeout=timeout,
                    )
                    if resp.status_code != 200:
                        print(f"Failed to fetch {self.__url}, skipping...")
                        continue

                    json = dict(resp.json())
                    data = json.get("data", {})
                    if data is None:
                        print(f"No results found for {schema}, skipping...")
                        continue
                    popular_titles = data.get("popularTitles", {})
                    if popular_titles is None:
                        print(f"No results found for {schema}, skipping...")
                        continue

                    edges = popular_titles.get("edges", []) or []

                    has_next_page = popular_titles.get("pageInfo", {}).get("hasNextPage", False)
                    for edge in edges:
                        schema_dict.update({"after_cursor": edge.get("cursor", "")})
                        object_type = edge.get("node", {}).get("objectType", None)
                        imdb_id = (
                            edge.get("node", {}).get("content", {}).get("externalIds", {}).get("imdbId", None)
                        )
                        if object_type is None:
                            continue
                        if imdb_id == "" or imdb_id is None or imdb_id.startswith("tt") is False:
                            continue
                        catalog_ids.append({"imdb_id": imdb_id, "object_type": object_type})
                    if not has_next_page:
                        break
                except httpx.TimeoutException:
                    print(f"Request timed out, retrying in {timeout} seconds...")
                    continue
                except httpx.HTTPError as e:
                    print(e)
                    continue

        return catalog_ids

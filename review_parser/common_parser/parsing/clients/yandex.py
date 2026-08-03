import json
import re
from html import unescape
from typing import Any
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlunsplit,
    urlsplit,
    unquote
)

import requests
from bs4 import BeautifulSoup

from common_parser.parsing.exceptions import (
    ParserError,
    InvalidSourceUrlError,
    ProviderRequestError
)
from common_parser.parsing.limits import get_review_limit


# YandexClient
# - открыть страницу отзывов Яндекс Карт
# - вытащить business_id из URL
# - вытащить state-view JSON из HTML
# - достать reviewResults
# - пройти HTML-пагинацию /reviews/?page=N
# - вернуть сырые reviewResults / raw reviews
class YandexClient:
    provider = "yandex"
    max_reviews = get_review_limit(provider)
    page_size = 50

    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) "
            "Gecko/20100101 Firefox/153.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def _find_first(self, pattern: str, text: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def _resolve_source(self, source_url: str) -> tuple[str, str]:
        """
        Open source URL and return final URL with extracted Yandex business id.

        This is needed for short links and share links because the original URL
        may not contain the organization id directly.
        """
        response = self.session.get(
            source_url,
            headers=self.default_headers,
            timeout=30,
            allow_redirects=True,
        )

        if response.status_code != 200:
            raise ProviderRequestError(
                provider=self.provider,
                status_code=response.status_code,
                response_text=response.text[:500],
            )

        business_id = self.extract_business_id(response.url, response.text)

        return response.url, business_id

    def _walk_values(self, data: Any, key_name: str) -> list[Any]:
        """
        Recursively collect values by key from a nested dict/list structure.

        Yandex state-view JSON is large and deeply nested, so this helper
        avoids relying on one fragile absolute path.
        """
        values = []
    
        if isinstance(data, dict):
            for key, value in data.items():
                if key == key_name:
                    values.append(value)
    
                values.extend(self._walk_values(value, key_name))
    
        elif isinstance(data, list):
            for item in data:
                values.extend(self._walk_values(item, key_name))
    
        return values

    def _find_review_results_container(self, data: Any) -> dict[str, Any] | None:
        """
        Find an organization dict that contains reviewResults.

        The average business rating is stored near reviewResults in the parent
        organization object, not inside reviewResults itself.
        """
        if isinstance(data, dict):
            review_results = data.get("reviewResults")

            if (
                isinstance(review_results, dict)
                and isinstance(review_results.get("reviews"), list)
                and isinstance(review_results.get("params"), dict)
            ):
                return data

            for value in data.values():
                found = self._find_review_results_container(value)
                if found:
                    return found

        elif isinstance(data, list):
            for item in data:
                found = self._find_review_results_container(item)
                if found:
                    return found

        return None

    def extract_business_id(self, source_url: str, html: str | None = None) -> str:
        """
        Extract Yandex organization/business id from URL or HTML.

        Supported inputs:
        - /maps/org/name/{business_id}/
        - query param poi[uri]=ymapsbm1://org?oid={business_id}
        - fallback search in HTML for businessId/oid fields
        """
        # 1. /maps/org/name/123456789/
        match = re.search(r"/org/[^/]+/(\d+)", source_url)
        if match:
            return match.group(1)

        # 2. query: ?poi[uri]=ymapsbm1://org?oid=123456789
        parts = urlsplit(source_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))

        poi_uri = query.get("poi[uri]")
        if poi_uri:
            decoded_poi_uri = unquote(poi_uri)
            oid_match = re.search(r"oid=(\d+)", decoded_poi_uri)
            if oid_match:
                return oid_match.group(1)

        # 3. HTML fallback
        if html:
            patterns = [
                r'"businessId"\s*:\s*"?(\d+)"?',
                r'businessId["\']?\s*[:=]\s*["\']?(\d+)',
                r'"oid"\s*:\s*"?(\d+)"?',
                r'"id"\s*:\s*"(\d+)".{0,300}"reviewResults"',
            ]

            for pattern in patterns:
                value = self._find_first(pattern, html)
                if value:
                    return value

        raise InvalidSourceUrlError(
            f"Cannot extract Yandex business id from URL: {source_url}"
        )

    def build_reviews_page_url(self, source_url: str, business_id: str, page: int) -> str:
        """
        Build a clean Yandex reviews page URL for a business id and page.

        The incoming source URL can contain map-only parameters such as
        mode=poi, poi[uri], ll, z. They are intentionally dropped because they
        can make Yandex return a map page without reviewResults.
        """
        parts = urlsplit(source_url)
        query = {
            "tab": "reviews",
            "page": str(page),
            "reviews[sort]": "by_time",
        }
        path = f"/maps/org/{business_id}/reviews"

        return urlunsplit(
            (
                parts.scheme or 'https',
                parts.netloc or 'yandex.ru',
                f'{path}/',
                urlencode(query, doseq=True),
                parts.fragment,
            )
        )

    def get_reviews_page_html(self, source_url: str, business_id: str, page: int) -> str:
        """
        Download HTML for one Yandex reviews page.

        Raises ProviderRequestError when Yandex returns a non-200 response.
        """
        url = self.build_reviews_page_url(source_url, business_id, page)

        response = self.session.get(
            url,
            headers=self.default_headers,
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderRequestError(
                provider=self.provider,
                status_code=response.status_code,
                response_text=response.text[:500],
            )

        return response.text

    def extract_state_views(self, html: str) -> list[dict[str, Any]]:
        """
        Extract JSON objects from <script class="state-view"> tags.

        Yandex embeds page data, including reviews, inside these JSON scripts.
        """
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.select('script.state-view[type="application/json"]')

        states: list[dict[str, Any]] = []

        for script in scripts:
            if not script.string:
                continue

            raw_json = unescape(script.string)

            try:
                states.append(json.loads(raw_json))
            except json.JSONDecodeError:
                continue

        return states

    def extract_review_results(self, html: str) -> dict[str, Any]:
        """
        Extract reviewResults block from a Yandex reviews page HTML.

        The returned dict contains raw reviews and pagination metadata:
        reviews, params, tags, aspects. If possible, business_rating is added
        from the parent organization ratingData block.
        """
        states = self.extract_state_views(html)

        for state in states:
            container = self._find_review_results_container(state)
            if not container:
                continue

            review_results = dict(container["reviewResults"])
            rating_data = container.get("ratingData") or {}

            if isinstance(rating_data, dict):
                review_results["business_rating"] = rating_data.get("ratingValue")

            return review_results

        raise ParserError("Cannot find Yandex reviewResults in HTML.")

    def get_reviews_page(self, source_url: str, business_id: str, page: int) -> dict[str, Any]:
        """
        Return raw reviewResults for one reviews page.

        This combines HTTP loading and state-view extraction for a single page.
        """
        html = self.get_reviews_page_html(source_url, business_id, page)
        return self.extract_review_results(html)

    def get_all_review_results(
        self,
        source_url: str,
        max_pages: int = 12,
    ) -> list[dict[str, Any]]:
        """
        Return raw reviewResults blocks for all available pages up to max_pages.

        Yandex exposes up to 12 pages by public HTML pagination in observed
        tests, which is 600 reviews with the current page size of 50.
        """
        resolved_url, business_id = self._resolve_source(source_url)
        first_page = self.get_reviews_page(resolved_url, business_id, page=1)

        params = first_page.get("params", {})
        total_pages = params.get("totalPages") or 1

        max_allowed_pages = min(
            max_pages,
            (self.max_reviews + self.page_size - 1) // self.page_size,
        )
        pages_to_fetch = min(int(total_pages), max_allowed_pages)

        results = [first_page]

        for page in range(2, pages_to_fetch + 1):
            try:
                results.append(
                    self.get_reviews_page(resolved_url, business_id, page=page)
                )
            except (ProviderRequestError, ParserError):
                break

        return results

    def get_all_reviews(
        self,
        source_url: str,
        max_pages: int = 12,
    ) -> list[dict[str, Any]]:
        """
        Return a flat list of raw Yandex reviews with duplicate reviewId removed.

        Use get_all_review_results when pagination metadata like external count
        or totalPages is also needed.
        """
        review_results_pages = self.get_all_review_results(
            source_url=source_url,
            max_pages=max_pages,
        )

        reviews: list[dict[str, Any]] = []
        seen_review_ids: set[str] = set()

        for page_result in review_results_pages:
            for review in page_result.get("reviews", []):
                review_id = review.get("reviewId")

                if review_id and review_id in seen_review_ids:
                    continue

                if review_id:
                    seen_review_ids.add(review_id)

                reviews.append(review)

                if len(reviews) >= self.max_reviews:
                    return reviews

        return reviews

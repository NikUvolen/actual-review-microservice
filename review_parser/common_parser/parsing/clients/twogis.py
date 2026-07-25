import re
import os

from common_parser.services.http_client import get as http_get


class TwoGisClient:
    base_url = 'https://public-api.reviews.2gis.com/2.0'

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv(
            'TWOGIS_API_KEY',
            "37c04fe6-a560-4549-b459-02309cf643ad"
        )

    def extract_firm_id(self, source_url: str) -> str:
        """
        Extracts the firm ID from the given source URL.

        Args:
            source_url (str): The source URL to extract the firm ID from.
        """
        match = re.search(r'/firm/(\d+)', source_url)
        if not match:
            raise ValueError('Invalid source URL format. Could not extract firm ID.')
        return match.group(1)

    def get_reviews_page(self, firm_id: str, limit: int = 50, offset: int = 0) -> dict:
        """
        Fetches reviews for the given firm ID.

        Args:
            firm_id (str): The firm ID to fetch reviews for.
            limit (int): The maximum number of reviews to fetch. Default is 50.
            offset (int): The offset for pagination. Default is 0.
        """
        url = f'{self.base_url}/branches/{firm_id}/reviews'
        params = {
            'limit': limit,
            'offset': offset,
            'is_advertiser': 'true',
            'fields': 'meta.branch_rating,meta.branch_reviews_count,meta.total_count',
            'without_my_first_review': 'false',
            'rated': 'true',
            'sort_by': 'date_edited',
            'key': self.api_key,
            'locale': 'ru_RU'
        }

        response = http_get(url, params=params)
        if response.status_code != 200:
            raise Exception(f'Failed to fetch reviews: {response.status_code} - {response.text}')
        return response.json()

    def get_all_reviews(self, firm_id: str, *, page_size: int = 50) -> dict:
        """
        Fetches all reviews for the given firm ID, handling pagination.

        Args:
            firm_id (str): The firm ID to fetch reviews for.
            page_size (int): The maximum number of reviews to fetch per page. Default is 50.
        """
        first_page = self.get_reviews_page(firm_id, limit=page_size, offset=0)

        meta = first_page.get('meta', {})
        reviews = list(first_page.get('reviews', []))
        total_count = meta.get('total_count') or len(reviews)

        offset = len(reviews)

        while offset < total_count:
            page = self.get_reviews_page(
                firm_id,
                limit=page_size,
                offset=offset
            )
            page_reviews = page.get('reviews', [])

            if not page_reviews:
                break

            reviews.extend(page_reviews)
            offset += len(page_reviews)

        return {
            'meta': meta,
            'reviews': reviews
        }

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from common_parser.parsing.clients.yandex import YandexClient
from common_parser.parsing.dto import ParseResult, ParsedReview
from common_parser.parsing.limits import get_review_limit
from common_parser.parsing.providers.base import BaseReviewParser


class YandexParser(BaseReviewParser):
    provider = 'yandex'
    max_reviews = get_review_limit(provider)

    def __init__(self, client: YandexClient | None = None):
        self.client = client or YandexClient()

    def _parse_external_count(
        self, 
        review_result_pages: list[dict[str, Any]]
    ) -> int | None:
        if not review_result_pages:
            return None

        params = review_result_pages[0].get('params', {})
        count = params.get('count')

        if count is None:
            return None

        return int(count)

    def _parse_avg_rating(
        self,
        review_result_pages: list[dict[str, Any]]
    ) -> float | None:
        if not review_result_pages:
            return None

        rating = review_result_pages[0].get('business_rating')

        if rating is None:
            return None

        try:
            return round(float(rating), 2)
        except (TypeError, ValueError):
            return None

    def _parse_avatar_url(self, author: dict[str, Any]) -> str | None:
        avatar_url = author.get('avatarUrl')

        if not avatar_url:
            return None

        return avatar_url.replace('{size}', 'islands-68')

    def _parse_rating(self, raw_review: dict[str, Any]) -> float | None:
        rating = raw_review.get('rating')

        if rating is None:
            return None

        try:
            return float(rating)
        except (TypeError, ValueError):
            return None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

    def _parse_media_urls(self, raw_review: dict[str, Any]) -> list[str]:
        media_urls: list[str] = []

        for photo in raw_review.get('photos') or []:
            url_template = photo.get('urlTemplate')
            if url_template:
                media_urls.append(url_template.replace('{size}', 'XXXL'))

        for video in raw_review.get('videos') or []:
            url = video.get('url') or video.get('playerUrl')
            if url:
                media_urls.append(url)

        return media_urls

    def _parse_review_url(self, raw_review: dict[str, Any]) -> str | None:
        business_id = raw_review.get('businessId')
        author = raw_review.get('author') or {}
        public_id = author.get('publicId')

        if not business_id or not public_id:
            return None

        query = urlencode({
            'reviews[publicId]': public_id,
            'utm_source': 'review',
        })

        return f'https://yandex.ru/maps/org/{business_id}/reviews?{query}'
    
    def _parse_review(self, raw_review: dict[str, Any]) -> ParsedReview:
        author = raw_review.get('author') or {}

        return ParsedReview(
            external_id=raw_review.get('reviewId'),
            author_name=author.get('name') or 'Аноним',
            author_avatar_url=self._parse_avatar_url(author),
            rating=self._parse_rating(raw_review),
            text=raw_review.get('text') or '',
            pub_date=self._parse_datetime(raw_review.get('updatedTime')),
            review_url=self._parse_review_url(raw_review),
            media_urls=self._parse_media_urls(raw_review)
        )

    def _parse_reviews(
        self,
        review_result_pages: list[dict[str, Any]]
    ) -> list[ParsedReview]:
        parsed_reviews: list[ParsedReview] = []
        seen_review_ids: set[str] = set()

        for page in review_result_pages:
            for raw_review in page.get('reviews', []):
                review_id = raw_review.get('reviewId')

                if review_id and review_id in seen_review_ids:
                    continue

                if review_id:
                    seen_review_ids.add(review_id)

                parsed_reviews.append(
                    self._parse_review(raw_review)
                )

        return sorted(
            parsed_reviews,
            key=lambda review: (
                review.pub_date.timestamp() if review.pub_date else float('-inf')
            ),
            reverse=True,
        )[:self.max_reviews]

    def parse(self, source_url: str) -> ParseResult:
        review_results_pages = self.client.get_all_review_results(source_url)

        external_count = self._parse_external_count(review_results_pages)
        avg_rating = self._parse_avg_rating(review_results_pages)
        reviews = self._parse_reviews(review_results_pages)

        return ParseResult(
            provider=self.provider,
            source_url=source_url,
            external_count=external_count,
            avg_rating=avg_rating,
            reviews=reviews
        )

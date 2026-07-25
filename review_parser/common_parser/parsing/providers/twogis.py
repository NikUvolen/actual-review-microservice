from datetime import datetime

from common_parser.parsing.clients.twogis import TwoGisClient
from common_parser.parsing.dto import ParseResult, ParsedReview
from common_parser.parsing.providers.base import BaseReviewParser



class TwoGisParser(BaseReviewParser):
    provider = "2gis"

    def __init__(self, client: TwoGisClient | None = None):
        self.client = client or TwoGisClient()

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _parse_review(self, item: dict, source_url: str) -> ParsedReview:
        pub_date = self._parse_datetime(item.get('date_created'))

        user = item.get('user', {})
        avatar_url = user.get('photo_preview_urls', {}).get('url')

        media_urls = []
        for photo in item.get('photos', []):
            preview_urls = photo.get('preview_urls', {})
            photo_url = preview_urls.get('url')
            if photo_url:
                media_urls.append(photo_url)

        external_id = item.get('id')
        review_url = None

        if external_id:
            review_url = f'{source_url}/tab/reviews/review/{external_id}'

        return ParsedReview(
            external_id=external_id,
            author_name=user.get('name') or 'Аноним',
            author_avatar_url=avatar_url,
            rating=item.get('rating'),
            text=item.get('text') or '',
            pub_date=pub_date,
            review_url=review_url,
            media_urls=media_urls
        )

    def parse(self, source_url: str) -> ParseResult:
        firm_id = self.client.extract_firm_id(source_url)
        raw_data = self.client.get_all_reviews(firm_id)

        meta = raw_data.get('meta', {})
        reviews = [
            self._parse_review(item, source_url)
            for item in raw_data.get('reviews', [])
        ]

        return ParseResult(
            provider=self.provider,
            source_url=source_url,
            external_count=meta.get('branch_reviews_count'),
            avg_rating=meta.get('branch_rating'),
            reviews=reviews
        )
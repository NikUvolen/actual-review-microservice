from common_parser.parsing.providers.twogis import TwoGisParser


class FakeTwoGisClient:
    def extract_firm_id(self, source_url: str) -> str:
        return "123"

    def get_all_reviews(self, firm_id: str) -> dict:
        return {
            "meta": {
                "branch_reviews_count": 10,
                "branch_rating": 4.7,
            },
            "reviews": [
                {
                    "id": "review-1",
                    "date_created": "2025-01-01T10:00:00",
                    "user": {
                        "name": "Ivan",
                        "photo_preview_urls": {
                            "url": "https://example.com/avatar.jpg",
                        },
                    },
                    "rating": 5,
                    "text": "Good place",
                    "photos": [
                        {
                            "preview_urls": {
                                "url": "https://example.com/photo.jpg",
                            },
                        },
                    ],
                },
            ],
        }


def test_twogis_parser_returns_normalized_result():
    parser = TwoGisParser(client=FakeTwoGisClient())

    result = parser.parse("https://2gis.ru/irkutsk/firm/123")

    assert result.provider == "2gis"
    assert result.source_url == "https://2gis.ru/irkutsk/firm/123"
    assert result.external_count == 10
    assert result.avg_rating == 4.7
    assert len(result.reviews) == 1

    review = result.reviews[0]
    assert review.external_id == "review-1"
    assert review.author_name == "Ivan"
    assert review.author_avatar_url == "https://example.com/avatar.jpg"
    assert review.rating == 5
    assert review.text == "Good place"
    assert review.review_url == "https://2gis.ru/irkutsk/firm/123/tab/reviews/review/review-1"
    assert review.media_urls == ["https://example.com/photo.jpg"]


def test_twogis_parser_uses_defaults_for_missing_optional_fields():
    class ClientWithSparseReview(FakeTwoGisClient):
        def get_all_reviews(self, firm_id: str) -> dict:
            return {
                "meta": {},
                "reviews": [
                    {
                        "id": "review-2",
                        "user": {},
                    },
                ],
            }

    parser = TwoGisParser(client=ClientWithSparseReview())

    result = parser.parse("https://2gis.ru/irkutsk/firm/123")

    assert result.external_count is None
    assert result.avg_rating is None
    assert len(result.reviews) == 1

    review = result.reviews[0]
    assert review.external_id == "review-2"
    assert review.author_name == "Аноним"
    assert review.author_avatar_url is None
    assert review.rating is None
    assert review.text == ""
    assert review.pub_date is None
    assert review.media_urls == []

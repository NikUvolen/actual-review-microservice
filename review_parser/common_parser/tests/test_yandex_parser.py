from datetime import datetime, timezone

from common_parser.parsing.providers.yandex import YandexParser


class FakeYandexClient:
    def get_all_review_results(self, source_url: str) -> list[dict]:
        return [
            {
                "business_rating": 4.400000095367432,
                "params": {
                    "count": 255,
                    "totalPages": 6,
                },
                "reviews": [
                    {
                        "reviewId": "review-1",
                        "businessId": "1009077078",
                        "author": {
                            "name": "Ivan",
                            "avatarUrl": (
                                "https://avatars.mds.yandex.net/get-yapic/1/{size}"
                            ),
                            "publicId": "author-public-1",
                        },
                        "rating": 5,
                        "text": "Good university",
                        "updatedTime": "2026-06-20T02:47:08.214Z",
                        "photos": [
                            {
                                "urlTemplate": (
                                    "https://avatars.mds.yandex.net/get-altay/1/{size}"
                                ),
                            },
                        ],
                        "videos": [
                            {
                                "url": "https://example.com/video.mp4",
                            },
                        ],
                    },
                    {
                        "reviewId": "review-2",
                        "businessId": "1009077078",
                        "author": {
                            "name": "Petr",
                            "publicId": "author-public-2",
                        },
                        "rating": "4",
                        "text": "Fine",
                        "updatedTime": "2026-06-21T03:10:00.000Z",
                        "photos": [],
                        "videos": [
                            {
                                "playerUrl": "https://example.com/player",
                            },
                        ],
                    },
                ],
            },
            {
                "params": {
                    "count": 255,
                    "totalPages": 6,
                },
                "reviews": [
                    {
                        "reviewId": "review-1",
                        "businessId": "1009077078",
                        "author": {
                            "name": "Ivan",
                            "publicId": "author-public-1",
                        },
                    },
                    {
                        "reviewId": "review-3",
                        "businessId": "1009077078",
                        "author": {},
                    },
                ],
            },
        ]


def test_yandex_parser_returns_normalized_result():
    parser = YandexParser(client=FakeYandexClient())

    result = parser.parse("https://yandex.ru/maps/org/1009077078/reviews/")

    assert result.provider == "yandex"
    assert result.source_url == "https://yandex.ru/maps/org/1009077078/reviews/"
    assert result.external_count == 255
    assert result.avg_rating == 4.4
    assert len(result.reviews) == 3

    review = next(
        review for review in result.reviews
        if review.external_id == "review-1"
    )
    assert review.external_id == "review-1"
    assert review.author_name == "Ivan"
    assert review.author_avatar_url == (
        "https://avatars.mds.yandex.net/get-yapic/1/islands-68"
    )
    assert review.rating == 5.0
    assert review.text == "Good university"
    assert review.pub_date == datetime(
        2026, 6, 20, 2, 47, 8, 214000, tzinfo=timezone.utc
    )
    assert review.review_url == (
        "https://yandex.ru/maps/org/1009077078/reviews?"
        "reviews%5BpublicId%5D=author-public-1&utm_source=review"
    )
    assert review.media_urls == [
        "https://avatars.mds.yandex.net/get-altay/1/XXXL",
        "https://example.com/video.mp4",
    ]


def test_yandex_parser_skips_duplicate_review_ids():
    parser = YandexParser(client=FakeYandexClient())

    result = parser.parse("https://yandex.ru/maps/org/1009077078/reviews/")

    assert {review.external_id for review in result.reviews} == {
        "review-1",
        "review-2",
        "review-3",
    }


def test_yandex_parser_uses_defaults_for_missing_optional_fields():
    parser = YandexParser(client=FakeYandexClient())

    result = parser.parse("https://yandex.ru/maps/org/1009077078/reviews/")

    review = next(
        review for review in result.reviews
        if review.external_id == "review-3"
    )
    assert review.external_id == "review-3"
    assert review.author_name == "Аноним"
    assert review.author_avatar_url is None
    assert review.rating is None
    assert review.text == ""
    assert review.pub_date is None
    assert review.review_url is None
    assert review.media_urls == []


def test_yandex_parser_returns_none_when_average_rating_is_missing():
    parser = YandexParser(client=FakeYandexClient())

    assert parser._parse_avg_rating([{"params": {}, "reviews": []}]) is None


def test_yandex_parser_returns_at_most_100_reviews():
    class LargeResultClient(FakeYandexClient):
        def get_all_review_results(self, source_url: str) -> list[dict]:
            return [
                {
                    "params": {"count": 150, "totalPages": 3},
                    "reviews": [
                        {
                            "reviewId": f"review-{index}",
                            "author": {},
                            "updatedTime": f"2026-06-{(index % 28) + 1:02d}T00:00:00.000Z",
                        }
                        for index in range(150)
                    ],
                }
            ]

    result = YandexParser(client=LargeResultClient()).parse(
        "https://yandex.ru/maps/org/123/reviews/"
    )

    assert result.external_count == 150
    assert len(result.reviews) == 100


def test_yandex_parser_sorts_reviews_by_date_descending():
    result = YandexParser(client=FakeYandexClient()).parse(
        "https://yandex.ru/maps/org/1009077078/reviews/"
    )

    assert [review.external_id for review in result.reviews] == [
        "review-2",
        "review-1",
        "review-3",
    ]

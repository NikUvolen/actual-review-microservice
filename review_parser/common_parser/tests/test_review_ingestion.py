from datetime import datetime, timedelta

import pytest

from common_parser.models import (
    Branch,
    BranchProvider,
    Organization,
    ProviderStat,
    Review,
    ReviewMedia,
)
from common_parser.parsing.dto import ParsedReview, ParseResult
from common_parser.parsing.ingestion import ReviewIngestionService


@pytest.fixture
def branch_provider() -> BranchProvider:
    organization = Organization.objects.create(
        name="Test Org",
        inn="1234567890",
    )
    branch = Branch.objects.create(
        organization=organization,
        city="Irkutsk",
        address="Test address",
    )
    return BranchProvider.objects.create(
        branch=branch,
        provider="2gis",
        source_url="https://2gis.ru/irkutsk/firm/123",
    )


def make_review(**overrides) -> ParsedReview:
    values = {
        "external_id": "review-1",
        "author_name": "Ivan",
        "author_avatar_url": "https://example.com/avatar.jpg",
        "rating": 5.0,
        "text": "Excellent",
        "pub_date": datetime(2025, 1, 1, 10, 0, 0),
        "review_url": "https://2gis.ru/irkutsk/firm/123/tab/reviews/review/review-1",
        "media_urls": [],
    }
    values.update(overrides)
    return ParsedReview(**values)


def make_result(**overrides) -> ParseResult:
    values = {
        "provider": "2gis",
        "source_url": "https://2gis.ru/irkutsk/firm/123",
        "external_count": 1,
        "avg_rating": 4.8,
        "reviews": [make_review()],
    }
    values.update(overrides)
    return ParseResult(**values)


@pytest.mark.django_db
def test_review_ingestion_creates_provider_stat_review_and_media(
    branch_provider: BranchProvider,
):
    result = make_result(
        reviews=[
            make_review(
                media_urls=[
                    "https://example.com/photo-1.jpg",
                    "https://example.com/photo-2.jpg",
                ]
            )
        ]
    )

    ingestion_result = ReviewIngestionService().save(branch_provider, result)

    assert ingestion_result.parsed_count == 1
    assert ingestion_result.created_count == 1
    assert ingestion_result.skipped_count == 0

    stat = ProviderStat.objects.get(provider=branch_provider)
    assert stat.external_rating_avg == 4.8
    assert stat.last_parse_date is not None

    review = Review.objects.get(provider=branch_provider)
    assert review.external_review_id == "review-1"
    assert review.author_name == "Ivan"
    assert review.author_avatar_url == "https://example.com/avatar.jpg"
    assert review.rating == 5.0
    assert review.text == "Excellent"
    assert review.review_url == "https://2gis.ru/irkutsk/firm/123/tab/reviews/review/review-1"
    assert len(review.content_hash) == 64

    media_urls = list(
        ReviewMedia.objects.filter(review=review)
        .order_by("url")
        .values_list("url", flat=True)
    )
    assert media_urls == [
        "https://example.com/photo-1.jpg",
        "https://example.com/photo-2.jpg",
    ]


@pytest.mark.django_db
def test_review_ingestion_skips_duplicate_by_external_id(
    branch_provider: BranchProvider,
):
    service = ReviewIngestionService()
    result = make_result()

    first = service.save(branch_provider, result)
    second = service.save(branch_provider, result)

    assert first.created_count == 1
    assert first.skipped_count == 0
    assert second.created_count == 0
    assert second.skipped_count == 1
    assert Review.objects.filter(provider=branch_provider).count() == 1


@pytest.mark.django_db
def test_review_ingestion_skips_duplicate_by_content_hash_without_external_id(
    branch_provider: BranchProvider,
):
    service = ReviewIngestionService()
    result = make_result(
        reviews=[
            make_review(
                external_id=None,
                review_url=None,
                author_name="Petr",
                text="Good service",
            )
        ]
    )

    first = service.save(branch_provider, result)
    second = service.save(branch_provider, result)

    assert first.created_count == 1
    assert second.created_count == 0
    assert second.skipped_count == 1
    assert Review.objects.filter(provider=branch_provider).count() == 1


@pytest.mark.django_db
def test_review_ingestion_keeps_latest_100_reviews_per_provider(
    branch_provider: BranchProvider,
):
    base_date = datetime(2025, 1, 1, 10, 0, 0)
    reviews = [
        make_review(
            external_id=f"review-{index}",
            pub_date=base_date + timedelta(days=index),
            review_url=f"https://example.com/reviews/{index}",
        )
        for index in range(105)
    ]

    ingestion_result = ReviewIngestionService().save(
        branch_provider,
        make_result(reviews=reviews, external_count=105),
    )

    stored_external_ids = set(
        Review.objects
        .filter(provider=branch_provider)
        .values_list("external_review_id", flat=True)
    )

    assert ingestion_result.parsed_count == 105
    assert ingestion_result.created_count == 100
    assert ingestion_result.skipped_count == 5
    assert len(stored_external_ids) == 100
    assert stored_external_ids == {
        f"review-{index}" for index in range(5, 105)
    }


@pytest.mark.django_db
def test_review_ingestion_prunes_only_current_provider_and_cascades_media(
    branch_provider: BranchProvider,
):
    base_date = datetime(2025, 1, 1, 10, 0, 0)
    service = ReviewIngestionService()
    initial_reviews = [
        make_review(
            external_id=f"review-{index}",
            pub_date=base_date + timedelta(days=index),
            review_url=f"https://example.com/reviews/{index}",
        )
        for index in range(100)
    ]
    service.save(branch_provider, make_result(reviews=initial_reviews))

    oldest_review = Review.objects.get(
        provider=branch_provider,
        external_review_id="review-0",
    )
    oldest_media = ReviewMedia.objects.create(
        review=oldest_review,
        media_type="photo",
        url="https://example.com/old-photo.jpg",
    )
    other_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="yandex",
        source_url="https://yandex.ru/maps/org/123/reviews/",
    )
    other_review = Review.objects.create(
        provider=other_provider,
        author_name="Other provider author",
        text="Other provider review",
        published_date=base_date,
        external_review_id="other-review",
        content_hash="a" * 64,
    )

    service.save(
        branch_provider,
        make_result(
            reviews=[
                make_review(
                    external_id="review-100",
                    pub_date=base_date + timedelta(days=100),
                    review_url="https://example.com/reviews/100",
                )
            ]
        ),
    )

    assert Review.objects.filter(provider=branch_provider).count() == 100
    assert not Review.objects.filter(pk=oldest_review.pk).exists()
    assert not ReviewMedia.objects.filter(pk=oldest_media.pk).exists()
    assert Review.objects.filter(pk=other_review.pk).exists()

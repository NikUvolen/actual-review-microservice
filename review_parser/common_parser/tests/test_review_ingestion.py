from datetime import datetime

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

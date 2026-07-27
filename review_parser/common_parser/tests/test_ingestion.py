from datetime import datetime

import pytest

from common_parser.models import Branch, Organization, Review
from common_parser.parsing.dto import ParsedReview, ParseResult
from common_parser.parsing.ingestion import ReviewIngestionService


@pytest.fixture
def branch() -> Branch:
    organization = Organization.objects.create(
        name="Test Org",
        inn="1234567890",
    )
    return Branch.objects.create(
        organization=organization,
        address="Test address",
    )


@pytest.mark.django_db
def test_review_ingestion_creates_reviews_and_skips_duplicates(branch: Branch):
    result = ParseResult(
        provider="2gis",
        source_url="https://2gis.ru/test/firm/123",
        external_count=1,
        avg_rating=5.0,
        reviews=[
            ParsedReview(
                external_id="review-1",
                author_name="Ivan",
                author_avatar_url=None,
                rating=5,
                text="Excellent",
                pub_date=datetime(2025, 1, 1, 10, 0, 0),
                review_url="https://2gis.ru/test/firm/123/tab/reviews/review/review-1",
                media_urls=[],
            ),
        ],
    )

    service = ReviewIngestionService()

    first = service.save(branch, result)
    second = service.save(branch, result)

    assert first.parsed_count == 1
    assert first.created_count == 1
    assert first.skipped_count == 0

    assert second.parsed_count == 1
    assert second.created_count == 0
    assert second.skipped_count == 1

    reviews = Review.objects.filter(branch=branch, provider="2gis")
    assert reviews.count() == 1

    review = reviews.get()
    assert review.author == "Ivan"
    assert review.content == "Excellent"
    assert review.rating == 5
    assert review.review_url == "https://2gis.ru/test/firm/123/tab/reviews/review/review-1"


@pytest.mark.django_db
def test_review_ingestion_updates_2gis_branch_stats(branch: Branch):
    result = ParseResult(
        provider="2gis",
        source_url="https://2gis.ru/test/firm/123",
        external_count=15,
        avg_rating=4.8,
        reviews=[],
    )

    ingestion_result = ReviewIngestionService().save(branch, result)

    branch.refresh_from_db()

    assert ingestion_result.parsed_count == 0
    assert branch.twogis_review_count == 15
    assert branch.twogis_review_avg == 4.8


@pytest.mark.django_db
def test_review_ingestion_falls_back_to_author_and_content_deduplication(branch: Branch):
    result = ParseResult(
        provider="vlru",
        source_url="https://www.vl.ru/test-company",
        external_count=1,
        avg_rating=4.5,
        reviews=[
            ParsedReview(
                external_id="101",
                author_name="Petr",
                author_avatar_url=None,
                rating=4,
                text="Good service",
                pub_date=datetime(2025, 1, 1, 10, 0, 0),
                review_url=None,
                media_urls=[],
            ),
        ],
    )

    service = ReviewIngestionService()

    first = service.save(branch, result)
    second = service.save(branch, result)

    assert first.created_count == 1
    assert second.created_count == 0
    assert second.skipped_count == 1
    assert Review.objects.filter(branch=branch, provider="vlru").count() == 1

import pytest

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.parsing.ingestion import IngestionResult
from common_parser import tasks


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


@pytest.mark.django_db
def test_parse_branch_reviews_async_uses_branch_provider(monkeypatch, branch_provider):
    class FakeReviewParsingService:
        called_with: BranchProvider | None = None

        def parse_and_save_provider_reviews(
            self,
            branch_provider: BranchProvider,
        ) -> IngestionResult:
            self.__class__.called_with = branch_provider
            return IngestionResult(
                parsed_count=3,
                created_count=2,
                skipped_count=1,
            )

    monkeypatch.setattr(tasks, "ReviewParsingService", FakeReviewParsingService)

    result = tasks.parse_branch_reviews_async(branch_provider.id)

    assert FakeReviewParsingService.called_with == branch_provider
    assert result["branch_provider_id"] == branch_provider.id
    assert result["branch_id"] == branch_provider.branch_id
    assert result["provider"] == "2gis"
    assert result["parsed"] == 3
    assert result["created"] == 2
    assert result["skipped"] == 1
    assert isinstance(result["duration_ms"], int)

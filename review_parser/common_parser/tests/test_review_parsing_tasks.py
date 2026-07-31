import pytest

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.parsing.exceptions import InvalidSourceUrlError, ProviderRequestError
from common_parser.parsing.ingestion import IngestionResult
from common_parser.services.review_parsing import MissingReviewSourceUrlError
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


@pytest.mark.django_db
def test_parse_branch_reviews_async_retries_temporary_provider_error(
    monkeypatch,
    branch_provider,
):
    class RetryCalled(Exception):
        def __init__(self, exc: Exception):
            self.exc = exc

    class FakeReviewParsingService:
        def parse_and_save_provider_reviews(
            self,
            branch_provider: BranchProvider,
        ) -> IngestionResult:
            raise ProviderRequestError(
                provider="2gis",
                status_code=503,
                response_text="Service unavailable",
            )

    def fake_retry(*, exc: Exception):
        raise RetryCalled(exc)

    monkeypatch.setattr(tasks, "ReviewParsingService", FakeReviewParsingService)
    monkeypatch.setattr(tasks.parse_branch_reviews_async, "retry", fake_retry)

    with pytest.raises(RetryCalled) as exc_info:
        tasks.parse_branch_reviews_async(branch_provider.id)

    assert isinstance(exc_info.value.exc, ProviderRequestError)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error",
    [
        InvalidSourceUrlError("Invalid source URL"),
        MissingReviewSourceUrlError("Missing source URL"),
    ],
)
def test_parse_branch_reviews_async_does_not_retry_permanent_errors(
    monkeypatch,
    branch_provider,
    error,
):
    class RetryCalled(Exception):
        pass

    class FakeReviewParsingService:
        def parse_and_save_provider_reviews(
            self,
            branch_provider: BranchProvider,
        ) -> IngestionResult:
            raise error

    def fake_retry(*, exc: Exception):
        raise RetryCalled

    monkeypatch.setattr(tasks, "ReviewParsingService", FakeReviewParsingService)
    monkeypatch.setattr(tasks.parse_branch_reviews_async, "retry", fake_retry)

    with pytest.raises(type(error)):
        tasks.parse_branch_reviews_async(branch_provider.id)

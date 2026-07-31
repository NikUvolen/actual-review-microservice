import pytest

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.parsing.ingestion import IngestionResult
from common_parser.services import parsing_orchestrator
from common_parser.services.parsing_orchestrator import ParsingOrchestrator


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
def test_parsing_orchestrator_gets_branch_provider(branch_provider):
    orchestrator = ParsingOrchestrator()

    result = orchestrator.get_branch_provider(branch_provider.pk)

    assert result == branch_provider


@pytest.mark.django_db
def test_parsing_orchestrator_runs_sync_parsing(branch_provider):
    class FakeParsingService:
        called_with: BranchProvider | None = None

        def parse_and_save_provider_reviews(
            self,
            branch_provider: BranchProvider,
        ) -> IngestionResult:
            self.__class__.called_with = branch_provider
            return IngestionResult(
                parsed_count=5,
                created_count=3,
                skipped_count=2,
            )

    service = FakeParsingService()
    orchestrator = ParsingOrchestrator(parsing_service=service)

    result = orchestrator.parse_branch_provider_sync(branch_provider.pk)

    assert FakeParsingService.called_with == branch_provider
    assert result.parsed_count == 5
    assert result.created_count == 3
    assert result.skipped_count == 2


@pytest.mark.django_db
def test_parsing_orchestrator_enqueues_async_task(monkeypatch, branch_provider):
    class FakeTaskResult:
        id = "task-123"

    class FakeCeleryApp:
        called_name: str | None = None
        called_args: list[int] | None = None

        def send_task(self, name: str, args: list[int]):
            self.__class__.called_name = name
            self.__class__.called_args = args
            return FakeTaskResult()

    monkeypatch.setattr(parsing_orchestrator, "app", FakeCeleryApp())

    orchestrator = ParsingOrchestrator()

    task_id = orchestrator.parse_branch_provider_async(branch_provider.pk)

    assert task_id == "task-123"
    assert FakeCeleryApp.called_name == "parse_branch_reviews_async"
    assert FakeCeleryApp.called_args == [branch_provider.pk]


def test_parsing_orchestrator_returns_async_result(monkeypatch):
    class FakeAsyncResult:
        def __init__(self, task_id: str):
            self.task_id = task_id

    monkeypatch.setattr(parsing_orchestrator, "AsyncResult", FakeAsyncResult)

    result = ParsingOrchestrator().get_task_result("task-123")

    assert isinstance(result, FakeAsyncResult)
    assert result.task_id == "task-123"

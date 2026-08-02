import pytest
from django.utils import timezone

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

    monkeypatch.setattr(parsing_orchestrator, "celery_app", FakeCeleryApp())

    orchestrator = ParsingOrchestrator()

    task_id = orchestrator.parse_branch_provider_async(branch_provider.pk)

    assert task_id == "task-123"
    assert FakeCeleryApp.called_name == "parse_branch_reviews_async"
    assert FakeCeleryApp.called_args == [branch_provider.pk]


@pytest.mark.django_db
def test_parsing_orchestrator_enqueues_all_branch_provider_tasks(
    monkeypatch,
    branch_provider,
):
    second_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="yandex",
        source_url="https://yandex.ru/maps/org/1009077078/reviews/",
    )
    inactive_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="vlru",
        source_url="https://www.vl.ru/test-company",
        is_active=False,
    )

    class FakeTaskResult:
        def __init__(self, task_id: str):
            self.id = task_id

    class FakeCeleryApp:
        calls: list[tuple[str, list[int]]] = []

        def send_task(self, name: str, args: list[int]):
            self.__class__.calls.append((name, args))
            return FakeTaskResult(f"task-{args[0]}")

    monkeypatch.setattr(parsing_orchestrator, "celery_app", FakeCeleryApp())

    task_ids = ParsingOrchestrator().parse_branch_providers_async(
        branch_provider.branch_id
    )

    assert task_ids == [
        f"task-{branch_provider.pk}",
        f"task-{second_provider.pk}",
    ]
    assert FakeCeleryApp.calls == [
        ("parse_branch_reviews_async", [branch_provider.pk]),
        ("parse_branch_reviews_async", [second_provider.pk]),
    ]
    assert inactive_provider.pk is not None


@pytest.mark.django_db
def test_parsing_orchestrator_enqueues_only_due_branch_providers(
    monkeypatch,
    branch_provider,
):
    now = timezone.now()
    branch_provider.next_parse_date = now - timezone.timedelta(minutes=1)
    branch_provider.save(update_fields=["next_parse_date"])

    inactive_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="yandex",
        source_url="https://yandex.ru/maps/org/1009077078/reviews/",
        is_active=False,
        next_parse_date=now - timezone.timedelta(minutes=1),
    )
    future_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="vlru",
        source_url="https://www.vl.ru/test-company",
        next_parse_date=now + timezone.timedelta(hours=1),
    )
    no_schedule_provider = BranchProvider.objects.create(
        branch=branch_provider.branch,
        provider="google",
        source_url="https://example.com/google",
        next_parse_date=None,
    )

    class FakeTaskResult:
        def __init__(self, task_id: str):
            self.id = task_id

    class FakeCeleryApp:
        calls: list[tuple[str, list[int]]] = []

        def send_task(self, name: str, args: list[int]):
            self.__class__.calls.append((name, args))
            return FakeTaskResult(f"task-{args[0]}")

    monkeypatch.setattr(parsing_orchestrator, "celery_app", FakeCeleryApp())

    task_ids = ParsingOrchestrator().parse_due_branch_providers_async()

    assert task_ids == [
        f"task-{branch_provider.pk}",
        f"task-{no_schedule_provider.pk}",
    ]
    assert FakeCeleryApp.calls == [
        ("parse_branch_reviews_async", [branch_provider.pk]),
        ("parse_branch_reviews_async", [no_schedule_provider.pk]),
    ]
    assert inactive_provider.pk is not None
    assert future_provider.pk is not None
    assert no_schedule_provider.pk is not None


def test_parsing_orchestrator_returns_async_result(monkeypatch):
    class FakeAsyncResult:
        def __init__(self, task_id: str):
            self.task_id = task_id

    monkeypatch.setattr(parsing_orchestrator, "AsyncResult", FakeAsyncResult)

    result = ParsingOrchestrator().get_task_result("task-123")

    assert isinstance(result, FakeAsyncResult)
    assert result.task_id == "task-123"

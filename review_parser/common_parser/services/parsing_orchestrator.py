from celery.result import AsyncResult
from django.shortcuts import get_object_or_404

from review_parser.celery import app
from common_parser.models import BranchProvider
from common_parser.parsing.ingestion import IngestionResult
from common_parser.services.review_parsing import ReviewParsingService


class ParsingOrchestrator:
    def __init__(
        self,
        parsing_service: ReviewParsingService | None = None,
    ):
        self.parsing_service = parsing_service or ReviewParsingService()

    def get_branch_provider(self, branch_provider_id: int) -> BranchProvider:
        return get_object_or_404(
            BranchProvider,
            pk=branch_provider_id
        )

    def parse_branch_provider_sync(
        self,
        branch_provider_id: int,
    ) -> IngestionResult:
        branch_provider = self.get_branch_provider(branch_provider_id)

        return self.parsing_service.parse_and_save_provider_reviews(
            branch_provider=branch_provider
        )

    def parse_branch_provider_async(
        self,
        branch_provider_id: int,
    ) -> str:
        branch_provider = self.get_branch_provider(branch_provider_id)

        task = app.send_task(
            'parse_branch_reviews_async',
            args=[branch_provider.pk],
        )

        return task.id

    def get_task_result(self, task_id: str) -> AsyncResult:
        return AsyncResult(task_id)

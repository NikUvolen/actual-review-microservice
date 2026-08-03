import requests
from celery import shared_task

from common_parser.services.parsing_orchestrator import ParsingOrchestrator
from common_parser.models import BranchProvider
from django.shortcuts import get_object_or_404
from loguru import logger
from time import perf_counter

from common_parser.parsing.exceptions import (
    InvalidSourceUrlError,
    ParserError,
    ProviderRequestError,
)
from common_parser.services.review_parsing import (
    MissingReviewSourceUrlError,
    UnknownProviderError,
    ReviewParsingService,
)


@shared_task(
    bind=True,
    name='parse_branch_reviews_async',
    max_retries=3,
    default_retry_delay=60,
)
def parse_branch_reviews_async(self, branch_provider_id: int):
    t0 = perf_counter()

    try:
        branch_provider = get_object_or_404(
            BranchProvider,
            id=branch_provider_id,
            is_active=True,
            branch__is_active=True,
        )
        result = ReviewParsingService().parse_and_save_provider_reviews(
            branch_provider=branch_provider
        )

        branch_provider.mark_as_parsed()

    except (
        ProviderRequestError,
        requests.Timeout,
        requests.ConnectionError,
    ) as exc:
        logger.warning(
            f'parse_branch_reviews_async retry: '
            f'branch_provider_id={branch_provider_id} '
            f'error={exc}'
        )

        raise self.retry(exc=exc)
    
    except (
        InvalidSourceUrlError,
        MissingReviewSourceUrlError,
        UnknownProviderError,
        ParserError,
    ) as exc:
        logger.exception(
            f'parse_branch_reviews_async failed without retry: '
            f'branch_provider_id={branch_provider_id} '
            f'error={exc}'
        )
        raise


    duration_ms = int((perf_counter() - t0) * 1000)

    logger.info(
        f'parse_branch_reviews_async finished: '
        f'branch_provider_id={branch_provider_id} '
        f'branch_id={branch_provider.branch.pk} '
        f'provider={branch_provider.provider} '
        f'parsed={result.parsed_count} created={result.created_count} ' 
        f'skipped={result.skipped_count} '
        f'duration_ms={duration_ms}'
    )

    return {
        'branch_provider_id': branch_provider_id,
        'branch_id': branch_provider.branch.pk,
        'provider': branch_provider.provider,
        'parsed': result.parsed_count,
        'created': result.created_count,
        'skipped': result.skipped_count,
        'duration_ms': duration_ms,
    }

@shared_task(
    name='enqueue_scheduled_branch_provider_parsing',
    ignore_result=True,
)
def enqueue_scheduled_branch_provider_parsing():
    task_ids = ParsingOrchestrator().parse_active_branch_providers_async()

    return {
        'enqueued_count': len(task_ids),
        'task_ids': task_ids,
    }

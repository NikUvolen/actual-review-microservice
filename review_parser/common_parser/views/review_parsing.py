from collections import Counter

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Count
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from common_parser.models import Branch, Review, BranchProvider
from common_parser.serializers import (
    ReviewFilterSerializer,
    ReviewSerializer,
    ParsingTaskStartSerializer, 
    ParsingTaskStatusSerializer,
    BranchProviderSummarySerializer
)
from common_parser.services.parsing_orchestrator import ParsingOrchestrator
from common_parser.services.reviews_query import ReviewsQueryService
from common_parser.api_settings import (
    DEFAULT_REVIEW_PAGE_SIZE,
    MAX_REVIEW_PAGE_SIZE,
)


PROVIDER_PARAMETER = openapi.Parameter(
    'provider',
    openapi.IN_QUERY,
    description='Review provider code: 2gis, vlru, yandex or google.',
    type=openapi.TYPE_STRING,
)
DATE_FROM_PARAMETER = openapi.Parameter(
    'date_from',
    openapi.IN_QUERY,
    description='Start of publication date range (YYYY-MM-DD), inclusive.',
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_DATE,
)
DATE_TO_PARAMETER = openapi.Parameter(
    'date_to',
    openapi.IN_QUERY,
    description='End of publication date range (YYYY-MM-DD), inclusive.',
    type=openapi.TYPE_STRING,
    format=openapi.FORMAT_DATE,
)
PAGE_PARAMETER = openapi.Parameter(
    'page',
    openapi.IN_QUERY,
    description='Page number.',
    type=openapi.TYPE_INTEGER,
)
PAGE_SIZE_PARAMETER = openapi.Parameter(
    'page_size',
    openapi.IN_QUERY,
    description='Reviews per page (maximum 100).',
    type=openapi.TYPE_INTEGER,
)
MODE_PARAMETER = openapi.Parameter(
    'mode',
    openapi.IN_QUERY,
    description='Result mode: standard or interleave.',
    type=openapi.TYPE_STRING,
    enum=['standard', 'interleave'],
)
ORDERING_PARAMETER = openapi.Parameter(
    'ordering',
    openapi.IN_QUERY,
    description=(
        'Review ordering: -published_date, published_date, -rating or rating.'
    ),
    type=openapi.TYPE_STRING,
    enum=['-published_date', 'published_date', '-rating', 'rating'],
)
INTERLEAVE_SIZE_PARAMETER = openapi.Parameter(
    'interleave_size',
    openapi.IN_QUERY,
    description='Consecutive reviews per provider in interleave mode (1-100).',
    type=openapi.TYPE_INTEGER,
    minimum=1,
    maximum=100,
)
PROVIDER_ORDER_PARAMETER = openapi.Parameter(
    'provider_order',
    openapi.IN_QUERY,
    description='Preferred provider order separated by commas.',
    type=openapi.TYPE_STRING,
)


class ReviewPagination(PageNumberPagination):
    page_size = DEFAULT_REVIEW_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = MAX_REVIEW_PAGE_SIZE


class ReviewListMixin:
    pagination_class = ReviewPagination
    query_service = ReviewsQueryService()

    def get_filters(self, request, *, allow_interleave: bool) -> dict:
        filter_serializer = ReviewFilterSerializer(
            data=request.query_params,
            context={'allow_interleave': allow_interleave},
        )
        filter_serializer.is_valid(raise_exception=True)
        return filter_serializer.validated_data

    def get_paginated_response(self, request, queryset):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ReviewSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data), page


# Получить BranchProvider по id
# запустить Celery task
# вернуть task_id + status = Pending
class BranchProviderParseAPIView(APIView):
    def post(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(
            BranchProvider, 
            pk=branch_provider_id,
            branch__organization__user=request.user,
            branch__is_active=True,
            is_active=True,
        )

        task_id = ParsingOrchestrator().parse_branch_provider_async(branch_provider.pk)

        serializer = ParsingTaskStartSerializer(
            {
                "task_id": task_id,
                "branch_provider_id": branch_provider_id,
                "status": "PENDING",
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED
        )


class ParsingTaskStatusAPIView(APIView):
    def get(self, request, task_id: str):
        task = ParsingOrchestrator().get_task_result(task_id)

        serializer = ParsingTaskStatusSerializer(
            {
                "task_id": task_id,
                "status": task.status,
                "result": task.result if task.successful() else None,
            }
        )

        return Response(serializer.data)


class BranchProviderReviewsAPIView(ReviewListMixin, APIView):
    @swagger_auto_schema(
        manual_parameters=[
            DATE_FROM_PARAMETER,
            DATE_TO_PARAMETER,
            ORDERING_PARAMETER,
            PAGE_PARAMETER,
            PAGE_SIZE_PARAMETER,
        ]
    )
    def get(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(
            BranchProvider.objects.annotate(
                stored_review_count=Count('reviews')
            ),
            pk=branch_provider_id,
            branch__organization__user=request.user,
            branch__is_active=True,
            is_active=True,
        )

        reviews = (
            Review.objects
            .filter(provider=branch_provider)
            .select_related('provider')
            .prefetch_related("media")
        )

        filters = self.get_filters(request, allow_interleave=False)
        reviews, _ = self.query_service.build(
            reviews,
            filters,
            [branch_provider.provider],
        )
        response, page = self.get_paginated_response(request, reviews)
        returned_counts = Counter(review.provider_id for review in page)
        provider_data = BranchProviderSummarySerializer(
            branch_provider,
            context={'returned_counts': returned_counts},
        ).data

        response.data['provider'] = provider_data
        response.data['mode'] = filters['mode']
        response.data['ordering'] = filters['ordering']

        return response


class BranchReviewsAPIView(ReviewListMixin, APIView):
    @swagger_auto_schema(
        manual_parameters=[
            PROVIDER_PARAMETER,
            DATE_FROM_PARAMETER,
            DATE_TO_PARAMETER,
            PAGE_PARAMETER,
            PAGE_SIZE_PARAMETER,
            MODE_PARAMETER,
            ORDERING_PARAMETER,
            INTERLEAVE_SIZE_PARAMETER,
            PROVIDER_ORDER_PARAMETER,
        ]
    )
    def get(self, request, branch_id: int):
        branch = get_object_or_404(
            Branch,
            pk=branch_id,
            organization__user=request.user,
            is_active=True,
        )

        filters = self.get_filters(request, allow_interleave=True)

        branch_providers_queryset = (
            BranchProvider.objects
            .filter(branch=branch, is_active=True)
            .select_related('stats')
            .annotate(stored_review_count=Count('reviews'))
        )
        if provider := filters.get('provider'):
            branch_providers_queryset = branch_providers_queryset.filter(
                provider=provider
            )
        branch_providers = list(branch_providers_queryset)
        available_providers = [
            branch_provider.provider
            for branch_provider in branch_providers
        ]

        reviews = (
            Review.objects
            .filter(provider__branch=branch, provider__is_active=True)
            .select_related('provider')
            .prefetch_related('media')
        )

        reviews, provider_order = self.query_service.build(
            reviews,
            filters,
            available_providers,
        )
        response, page = self.get_paginated_response(request, reviews)

        provider_positions = {
            provider: position
            for position, provider in enumerate(provider_order)
        }
        branch_providers.sort(
            key=lambda item: (
                provider_positions.get(item.provider, len(provider_positions)),
                item.pk,
            )
        )
        returned_counts = Counter(review.provider_id for review in page)
        providers_data = BranchProviderSummarySerializer(
            branch_providers,
            many=True,
            context={'returned_counts': returned_counts},
        ).data

        response.data['providers'] = providers_data
        response.data['mode'] = filters['mode']
        response.data['ordering'] = filters['ordering']
        if filters['mode'] == 'interleave':
            response.data['interleave_size'] = filters['interleave_size']
            response.data['provider_order'] = provider_order

        return response

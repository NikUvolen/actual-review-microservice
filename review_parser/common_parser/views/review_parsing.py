from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
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


class ReviewPagination(PageNumberPagination):
    page_size = DEFAULT_REVIEW_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = MAX_REVIEW_PAGE_SIZE


class ReviewListMixin:
    pagination_class = ReviewPagination

    def get_filtered_reviews(self, request, queryset):
        filter_serializer = ReviewFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data

        if provider := filters.get('provider'):
            queryset = queryset.filter(provider__provider=provider)
        if date_from := filters.get('date_from'):
            queryset = queryset.filter(published_date__date__gte=date_from)
        if date_to := filters.get('date_to'):
            queryset = queryset.filter(published_date__date__lte=date_to)

        return queryset

    def get_paginated_response(self, request, queryset):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ReviewSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


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
            PAGE_PARAMETER,
            PAGE_SIZE_PARAMETER,
        ]
    )
    def get(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(
            BranchProvider, 
            pk=branch_provider_id,
            branch__organization__user=request.user,
            branch__is_active=True,
            is_active=True,
        )

        provider_data = BranchProviderSummarySerializer(
            branch_provider, many=False
        ).data

        reviews = (
            Review.objects
            .filter(provider=branch_provider)
            .select_related('provider')
            .prefetch_related("media")
            .order_by("-published_date")
        )

        reviews = self.get_filtered_reviews(request, reviews)
        response = self.get_paginated_response(request, reviews)
        response.data['provider'] = provider_data

        return response


class BranchReviewsAPIView(ReviewListMixin, APIView):
    @swagger_auto_schema(
        manual_parameters=[
            PROVIDER_PARAMETER,
            DATE_FROM_PARAMETER,
            DATE_TO_PARAMETER,
            PAGE_PARAMETER,
            PAGE_SIZE_PARAMETER,
        ]
    )
    def get(self, request, branch_id: int):
        branch = get_object_or_404(
            Branch,
            pk=branch_id,
            organization__user=request.user,
            is_active=True,
        )

        branch_providers = (
            BranchProvider.objects
            .filter(branch=branch, is_active=True)
            .select_related('stats')
            .order_by('provider', 'pk')
        )
        providers_data = BranchProviderSummarySerializer(
            branch_providers, many=True
        ).data

        reviews = (
            Review.objects
            .filter(provider__branch=branch)
            .select_related('provider')
            .prefetch_related('media')
            .order_by('-published_date', '-pk')
        )

        reviews = self.get_filtered_reviews(request, reviews)
        response = self.get_paginated_response(request, reviews)
        response.data['providers'] = providers_data

        return response

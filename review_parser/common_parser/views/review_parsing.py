from celery.result import AsyncResult
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from review_parser.celery import app
from common_parser.models import Review, BranchProvider
from common_parser.tasks import parse_branch_reviews_async
from common_parser.serializers import (
    ReviewSerializer,
    ParsingTaskStartSerializer, 
    ParsingTaskStatusSerializer
)


# Получить BranchProvider по id
# запустить Celery task
# вернуть task_id + status = Pending
class BranchProviderParseAPIView(APIView):
    def post(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(BranchProvider, pk=branch_provider_id)

        task = app.send_task(
            'parse_branch_reviews_async',
            args=[branch_provider.pk],
        )
        serializer = ParsingTaskStartSerializer(
            {
                "task_id": task.id,
                "branch_provider_id": branch_provider.pk,
                "status": "PENDING",
            }
        )

        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED
        )


class ParsingTaskStatusAPIView(APIView):
    def get(self, request, task_id: str):
        task = AsyncResult(task_id)

        serializer = ParsingTaskStatusSerializer(
            {
                "task_id": task_id,
                "status": task.status,
                "result": task.result if task.successful() else None,
            }
        )

        return Response(serializer.data)


class BranchProviderReviewsAPIView(APIView):
    def get(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(BranchProvider, pk=branch_provider_id)

        reviews = (
            Review.objects
            .filter(provider=branch_provider)
            .prefetch_related("media")
            .order_by("-published_date")
        )

        serializer = ReviewSerializer(reviews, many=True)
        count: int = reviews.count()

        return Response({
            'count': reviews.count(),
            'results': serializer.data
        })

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from common_parser.models import Review, BranchProvider
from common_parser.serializers import (
    ReviewSerializer,
    ParsingTaskStartSerializer, 
    ParsingTaskStatusSerializer
)
from common_parser.services.parsing_orchestrator import ParsingOrchestrator


# Получить BranchProvider по id
# запустить Celery task
# вернуть task_id + status = Pending
class BranchProviderParseAPIView(APIView):
    def post(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(
            BranchProvider, 
            pk=branch_provider_id,
            branch__organization=request.user.organization
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


class BranchProviderReviewsAPIView(APIView):
    def get(self, request, branch_provider_id: int):
        branch_provider = get_object_or_404(
            BranchProvider, 
            pk=branch_provider_id,
            branch__organization=request.user.organization
        )

        reviews = (
            Review.objects
            .filter(provider=branch_provider)
            .prefetch_related("media")
            .order_by("-published_date")
        )

        serializer = ReviewSerializer(reviews, many=True)
        count: int = reviews.count()

        return Response({
            'count': count,
            'results': serializer.data
        })

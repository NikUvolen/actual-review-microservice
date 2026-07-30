from django.urls import path

from common_parser.views.review_parsing import (
    BranchProviderParseAPIView,
    ParsingTaskStatusAPIView,
    BranchProviderReviewsAPIView,
)    


urlpatterns = [
    path(
        'branch_providers/<int:branch_provider_id>/parse/',
        BranchProviderParseAPIView.as_view(),
        name='branch-provider-parse'
    ),
    path(
            'branch_providers/<int:branch_provider_id>/reviews/',
            BranchProviderReviewsAPIView.as_view(),
            name='branch-provider-reviews'
    ),
    path(
        'parsing-tasks/<str:task_id>/',
        ParsingTaskStatusAPIView.as_view(),
        name='parsing-task-status'
    ),
]

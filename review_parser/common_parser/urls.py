from django.urls import path

from common_parser.views.review_parsing import (
    BranchProviderParseAPIView,
    ParsingTaskStatusAPIView,
    BranchReviewsAPIView,
    BranchProviderReviewsAPIView,
)    
from common_parser.views.crud import (
    BranchDetailAPIView,
    BranchListCreateAPIView,
    BranchProviderDetailAPIView,
    BranchProviderListCreateAPIView,
    OrganizationAPIView,
)


urlpatterns = [
    path(
        'organization/',
        OrganizationAPIView.as_view(),
        name='organization-detail',
    ),
    path(
        'branches/',
        BranchListCreateAPIView.as_view(),
        name='branch-list',
    ),
    path(
        'branches/<int:pk>/',
        BranchDetailAPIView.as_view(),
        name='branch-detail',
    ),
    path(
        'branches/<int:branch_id>/providers/',
        BranchProviderListCreateAPIView.as_view(),
        name='branch-provider-list',
    ),
    path(
        'branch-providers/<int:pk>/',
        BranchProviderDetailAPIView.as_view(),
        name='branch-provider-detail',
    ),
    path(
        'branch_providers/<int:branch_provider_id>/parse/',
        BranchProviderParseAPIView.as_view(),
        name='branch-provider-parse'
    ),
    path(
        'branches/<int:branch_id>/reviews/',
        BranchReviewsAPIView.as_view(),
        name='branch-reviews',
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

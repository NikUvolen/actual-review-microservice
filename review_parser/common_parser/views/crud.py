import logging
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.serializers import (
    BranchProviderSerializer,
    BranchSerializer,
    BranchCreateSerializer,
    OrganizationSerializer,
)
from common_parser.services.parsing_orchestrator import ParsingOrchestrator


logger = logging.getLogger(__name__)


class OrganizationAccessMixin:
    request: Request
    _organization: Organization | None = None

    def get_organization(self) -> Organization:
        if self._organization is None:
            self._organization = get_object_or_404(
                Organization,
                user=self.request.user,
            )
        return self._organization


class OrganizationAPIView(
    OrganizationAccessMixin,
    generics.RetrieveUpdateAPIView,
):
    serializer_class = OrganizationSerializer

    def get_object(self) -> Organization:
        return self.get_organization()


class BranchListCreateAPIView(
    OrganizationAccessMixin,
    generics.ListCreateAPIView,
):
    serializer_class = BranchSerializer

    @swagger_auto_schema(
        request_body=BranchCreateSerializer,
        responses={201: BranchSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Branch.objects.none()

        return (
            Branch.objects
            .filter(
                organization=self.get_organization(),
                is_active=True,
            )
            .select_related('organization')
            .prefetch_related(
                Prefetch(
                    'branch_providers',
                    queryset=BranchProvider.objects.filter(is_active=True),
                )
            )
            .order_by('pk')
        )

    def get_serializer_context(self):
        context = dict(super().get_serializer_context())
        if not getattr(self, 'swagger_fake_view', False):
            context['organization'] = self.get_organization()
        return context

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())


class BranchDetailAPIView(
    OrganizationAccessMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = BranchSerializer

    @swagger_auto_schema(
        request_body=BranchCreateSerializer,
        responses={200: BranchSerializer},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=BranchCreateSerializer,
        responses={200: None},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Branch.objects.none()

        return (
            Branch.objects
            .filter(
                organization=self.get_organization(),
                is_active=True,
            )
            .select_related('organization')
            .prefetch_related(
                Prefetch(
                    'branch_providers',
                    queryset=BranchProvider.objects.filter(is_active=True),
                )
            )
        )

    def get_serializer_context(self):
        context = dict(super().get_serializer_context())
        if not getattr(self, 'swagger_fake_view', False):
            context['organization'] = self.get_organization()
        return context

    def perform_destroy(self, instance: Branch):
        with transaction.atomic():
            BranchProvider.objects.filter(
                branch=instance,
                is_active=True
            ).update(is_active=False)
            instance.is_active = False
            instance.save(update_fields=['is_active'])


class BranchProviderListCreateAPIView(
    OrganizationAccessMixin,
    generics.ListCreateAPIView,
):
    serializer_class = BranchProviderSerializer
    _branch: Branch | None = None

    def get_branch(self) -> Branch:
        if self._branch is None:
            self._branch = get_object_or_404(
                Branch,
                pk=self.kwargs['branch_id'],
                organization=self.get_organization(),
                is_active=True,
            )
        return self._branch

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return BranchProvider.objects.none()

        return (
            BranchProvider.objects
            .filter(branch=self.get_branch(), is_active=True)
            .select_related('branch', 'stats')
            .order_by('pk')
        )

    def get_serializer_context(self):
        context = dict(super().get_serializer_context())
        if not getattr(self, 'swagger_fake_view', False):
            context['branch'] = self.get_branch()
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        branch_provider = serializer.save(branch=self.get_branch())

        try:
            task_id = ParsingOrchestrator().parse_branch_provider_async(
                branch_provider.pk
            )
        except Exception as e:
            logger.exception(
                'Failed to start initial parsing task for branch_provider_id=%s\n%s',
                branch_provider.pk,
                e,
            )
            task_id = None

        response_serializer = self.get_serializer(branch_provider)

        return Response(
            {
                'provider': response_serializer.data,
                'task_id': task_id,
                'status': 'NOT_STARTED' if task_id is None else 'PENDING',
            },
            status=status.HTTP_201_CREATED,
        )


class BranchProviderDetailAPIView(
    OrganizationAccessMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = BranchProviderSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return BranchProvider.objects.none()

        return (
            BranchProvider.objects
            .filter(
                branch__organization=self.get_organization(),
                branch__is_active=True,
                is_active=True,
            )
            .select_related('branch', 'stats')
        )

    def perform_destroy(self, instance: BranchProvider) -> None:
        instance.is_active = False
        instance.save(update_fields=['is_active'])

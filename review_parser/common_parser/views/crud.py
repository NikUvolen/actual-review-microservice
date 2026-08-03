from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.serializers import (
    BranchProviderSerializer,
    BranchSerializer,
    OrganizationSerializer,
)


class OrganizationAccessMixin:
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
        context = super().get_serializer_context()
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
        context = super().get_serializer_context()
        if not getattr(self, 'swagger_fake_view', False):
            context['organization'] = self.get_organization()
        return context

    def perform_destroy(self, instance: Branch):
        with transaction.atomic():
            instance.branch_providers.filter(is_active=True).update(is_active=False)
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
        context = super().get_serializer_context()
        if not getattr(self, 'swagger_fake_view', False):
            context['branch'] = self.get_branch()
        return context

    def perform_create(self, serializer):
        serializer.save(branch=self.get_branch())


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

    def perform_destroy(self, instance: BranchProvider):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

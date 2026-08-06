from collections.abc import Iterable

from django.db.models import (
    Case,
    ExpressionWrapper,
    F,
    IntegerField,
    QuerySet,
    Value,
    When,
    Window,
)
from django.db.models.functions import RowNumber

from common_parser.api_settings import DEFAULT_PROVIDER_ORDER
from common_parser.models import Review


class ReviewsQueryService:
    def apply_filters(
        self,
        queryset: QuerySet[Review],
        filters: dict,
    ) -> QuerySet[Review]:
        if provider := filters.get('provider'):
            queryset = queryset.filter(provider__provider=provider)
        if date_from := filters.get('date_from'):
            queryset = queryset.filter(
                published_date__date__gte=date_from
            )
        if date_to := filters.get('date_to'):
            queryset = queryset.filter(
                published_date__date__lte=date_to
            )
        return queryset

    def resolve_provider_order(
        self,
        available_providers: Iterable[str],
        requested_order: list[str] | None = None,
    ) -> list[str]:
        available = set(available_providers)
        resolved: list[str] = []

        for provider in requested_order or []:
            if provider in available and provider not in resolved:
                resolved.append(provider)

        for provider in DEFAULT_PROVIDER_ORDER:
            if provider in available and provider not in resolved:
                resolved.append(provider)

        for provider in sorted(available):
            if provider not in resolved:
                resolved.append(provider)

        return resolved

    def _ordering_expressions(self, ordering: str) -> list:
        if ordering == 'published_date':
            return [
                F('published_date').asc(nulls_last=True),
                F('pk').asc(),
            ]
        if ordering == '-rating':
            return [
                F('rating').desc(nulls_last=True),
                F('published_date').desc(nulls_last=True),
                F('pk').desc(),
            ]
        if ordering == 'rating':
            return [
                F('rating').asc(nulls_last=True),
                F('published_date').desc(nulls_last=True),
                F('pk').desc(),
            ]
        return [
            F('published_date').desc(nulls_last=True),
            F('pk').desc(),
        ]

    def order_standard(
        self,
        queryset: QuerySet[Review],
        ordering: str,
    ) -> QuerySet[Review]:
        return queryset.order_by(*self._ordering_expressions(ordering))

    def order_interleaved(
        self,
        queryset: QuerySet[Review],
        *,
        ordering: str,
        interleave_size: int,
        provider_order: list[str],
    ) -> QuerySet[Review]:
        if provider_order:
            provider_priority = Case(
                *[
                    When(provider__provider=provider, then=Value(position))
                    for position, provider in enumerate(provider_order)
                ],
                default=Value(len(provider_order)),
                output_field=IntegerField(),
            )
        else:
            provider_priority = Value(0, output_field=IntegerField())
        provider_row_number = Window(
            expression=RowNumber(),
            partition_by=[F('provider__provider')],
            order_by=self._ordering_expressions(ordering),
        )

        return (
            queryset
            .annotate(
                _provider_priority=provider_priority,
                _provider_row_number=provider_row_number,
            )
            .annotate(
                _interleave_group=ExpressionWrapper(
                    (F('_provider_row_number') - Value(1))
                    / Value(interleave_size),
                    output_field=IntegerField(),
                )
            )
            .order_by(
                '_interleave_group',
                '_provider_priority',
                '_provider_row_number',
                'pk',
            )
        )

    def build(
        self,
        queryset: QuerySet[Review],
        filters: dict,
        available_providers: Iterable[str],
    ) -> tuple[QuerySet[Review], list[str]]:
        queryset = self.apply_filters(queryset, filters)
        provider_order = self.resolve_provider_order(
            available_providers,
            filters.get('provider_order'),
        )
        ordering = filters['ordering']

        if filters['mode'] == 'interleave':
            queryset = self.order_interleaved(
                queryset,
                ordering=ordering,
                interleave_size=filters['interleave_size'],
                provider_order=provider_order,
            )
        else:
            queryset = self.order_standard(queryset, ordering)

        return queryset, provider_order

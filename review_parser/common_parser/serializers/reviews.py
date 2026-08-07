from rest_framework import serializers

from common_parser.models import BranchProvider, Review, ReviewMedia
from common_parser.api_settings import (
    DEFAULT_REVIEW_MODE,
    DEFAULT_REVIEW_ORDERING,
    MAX_INTERLEAVE_SIZE,
    MAX_REVIEW_PAGE_SIZE,
)


REVIEW_MODES = ('standard', 'interleave')
REVIEW_ORDERINGS = (
    '-published_date',
    'published_date',
    '-rating',
    'rating',
)
DATE_REVIEW_ORDERINGS = (
    '-published_date',
    'published_date',
)


class BaseReviewFilterSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_REVIEW_PAGE_SIZE,
    )

    def validate(self, attrs):
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {'date_to': 'Must be greater than or equal to date_from.'}
            )

        return attrs


class BranchProviderReviewsFilterSerializer(BaseReviewFilterSerializer):
    mode = serializers.HiddenField(default=DEFAULT_REVIEW_MODE)
    ordering = serializers.ChoiceField(
        choices=DATE_REVIEW_ORDERINGS,
        default=DEFAULT_REVIEW_ORDERING,
    )

    def validate(self, attrs):
        unsupported_parameters = (
            'provider',
            'mode',
            'interleave_size',
            'provider_order',
        )
        errors = {
            parameter: 'Unavailable for one provider.'
            for parameter in unsupported_parameters
            if parameter in self.initial_data
        }
        if errors:
            raise serializers.ValidationError(errors)

        return super().validate(attrs)


class BranchReviewsFilterSerializer(BaseReviewFilterSerializer):
    provider = serializers.ChoiceField(
        choices=BranchProvider.PROVIDER_CHOICES,
        required=False,
    )
    mode = serializers.ChoiceField(
        choices=REVIEW_MODES,
        default=DEFAULT_REVIEW_MODE,
    )
    ordering = serializers.ChoiceField(
        choices=REVIEW_ORDERINGS,
        default=DEFAULT_REVIEW_ORDERING,
    )
    interleave_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_INTERLEAVE_SIZE,
    )
    provider_order = serializers.CharField(required=False)

    def validate_provider_order(self, value: str) -> list[str]:
        provider_order = [
            provider.strip().lower()
            for provider in value.split(',')
            if provider.strip()
        ]
        if not provider_order:
            raise serializers.ValidationError('Provider order cannot be empty.')

        if len(provider_order) != len(set(provider_order)):
            raise serializers.ValidationError(
                'Provider order cannot contain duplicates.'
            )

        known_providers = {
            provider for provider, _ in BranchProvider.PROVIDER_CHOICES
        }
        unknown_providers = [
            provider
            for provider in provider_order
            if provider not in known_providers
        ]
        if unknown_providers:
            raise serializers.ValidationError(
                f'Unknown providers: {", ".join(unknown_providers)}.'
            )

        return provider_order

    def validate(self, attrs):
        attrs = super().validate(attrs)

        mode = attrs['mode']
        interleave_parameters = ('interleave_size', 'provider_order')

        if mode != 'interleave':
            invalid_parameters = [
                parameter
                for parameter in interleave_parameters
                if parameter in attrs
            ]
            if invalid_parameters:
                raise serializers.ValidationError({
                    parameter: 'Available only when mode=interleave.'
                    for parameter in invalid_parameters
                })

        if mode == 'interleave':
            attrs.setdefault('interleave_size', 1)

        return attrs


class ReviewMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewMedia
        fields = (
            'id',
            'media_type',
            'url',
        )


class ReviewSerializer(serializers.ModelSerializer):
    media = ReviewMediaSerializer(many=True, read_only=True)
    provider_name = serializers.CharField(
        source='provider.provider',
        read_only=True,
    )

    class Meta:
        model = Review
        fields = (
            'id',
            'provider',
            'provider_name',
            'author_name',
            'author_avatar_url',
            'rating',
            'text',
            'review_url',
            'published_date',
            'external_review_id',
            'media'
        )

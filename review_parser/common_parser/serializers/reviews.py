from rest_framework import serializers

from common_parser.models import BranchProvider, Review, ReviewMedia
from common_parser.api_settings import MAX_REVIEW_PAGE_SIZE


class ReviewFilterSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=BranchProvider.PROVIDER_CHOICES,
        required=False,
    )
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

from rest_framework import serializers

from common_parser.models import Review, ReviewMedia


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

    class Meta:
        model = Review
        fields = (
            'id',
            'provider',
            'author_name',
            'author_avatar_url',
            'rating',
            'text',
            'review_url',
            'published_date',
            'external_review_id',
            'media'
        )

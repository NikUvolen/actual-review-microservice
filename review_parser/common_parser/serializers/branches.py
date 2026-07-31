from rest_framework import serializers

from common_parser.models import Branch, BranchProvider, ProviderStat
from common_parser.serializers.organizations import OrganizationSerializer


class ProviderStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderStat
        fields = (
            'id',
            'external_rating_avg',
            'last_parse_date'
        )


class BranchProviderSerializer(serializers.ModelSerializer):
    stats = ProviderStatSerializer(read_only=True)

    class Meta:
        model = BranchProvider
        fields = (
            'id',
            'branch',
            'provider',
            'source_url',
            'external_place_id',
            'stats'
        )


class BranchSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    branch_providers = BranchProviderSerializer(many=True, read_only=True)

    class Meta:
        model = Branch
        fields = (
            'id',
            'organization',
            'city',
            'address',
            'branch_providers'
        )

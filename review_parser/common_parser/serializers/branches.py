from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from urllib.parse import urlsplit

from common_parser.models import Branch, BranchProvider, ProviderStat
from common_parser.serializers.organizations import OrganizationSerializer
from common_parser.validators import validate_twogis_source_url


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

    PROVIDER_DOMAINS = {
        '2gis': ('2gis.ru', '2gis.com'),
        'vlru': ('vl.ru',),
        'yandex': ('yandex.ru', 'yandex.com'),
        'google': ('google.com', 'goo.gl'),
    }

    class Meta:
        model = BranchProvider
        fields = (
            'id',
            'branch',
            'provider',
            'source_url',
            'external_place_id',
            'is_active',
            'stats'
        )
        read_only_fields = ('branch', 'is_active')

    def validate(self, attrs):
        provider = attrs.get('provider', getattr(self.instance, 'provider', None))
        source_url = attrs.get('source_url', getattr(self.instance, 'source_url', None))

        if provider and source_url:
            hostname = (urlsplit(source_url).hostname or '').lower()
            allowed_domains = self.PROVIDER_DOMAINS.get(provider, ())
            if not any(
                hostname == domain or hostname.endswith(f'.{domain}')
                for domain in allowed_domains
            ):
                raise serializers.ValidationError({
                    'source_url': f'URL does not match provider {provider}.'
                })

            if provider == '2gis':
                try:
                    validate_twogis_source_url(source_url)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError({
                        'source_url': exc.messages[0]
                    }) from exc

        branch = self.instance.branch if self.instance else self.context.get('branch')
        if branch and provider and source_url:
            duplicates = BranchProvider.objects.filter(
                branch=branch,
                provider=provider,
                source_url=source_url,
            )
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({
                    'source_url': 'This provider URL is already attached to the branch.'
                })

        return attrs


class BranchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = (
            'city',
            'address'
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
            'is_active',
            'branch_providers'
        )
        read_only_fields = ('organization', 'is_active')

    def validate(self, attrs):
        organization = (
            self.instance.organization
            if self.instance
            else self.context.get('organization')
        )
        address = attrs.get('address', getattr(self.instance, 'address', None))

        if organization and address:
            duplicates = Branch.objects.filter(
                organization=organization,
                address=address,
            )
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({
                    'address': 'A branch with this address already exists.'
                })

        return attrs


class BranchProviderSummarySerializer(serializers.ModelSerializer):
    external_rating_avg = serializers.FloatField(
        source='stats.external_rating_avg',
        read_only=True,
    )
    # external_review_count = serializers.IntegerField(
    #     source='stats.external_review_count',
    #     read_only=True,
    # )
    last_parse_date = serializers.DateTimeField(
        source='stats.last_parse_date',
        read_only=True,
    )
    stored_review_count = serializers.IntegerField(read_only=True)
    returned_count = serializers.SerializerMethodField()

    def get_returned_count(self, instance: BranchProvider) -> int:
        returned_counts = self.context.get('returned_counts', {})
        return returned_counts.get(instance.pk, 0)

    class Meta:
        model = BranchProvider
        fields = (
            'id',
            'provider',
            'source_url',
            'external_rating_avg',
            'last_parse_date',
            'stored_review_count',
            'returned_count',
        )

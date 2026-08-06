import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from common_parser.models import Branch, BranchProvider, Organization
from common_parser.parsing.ingestion import IngestionResult
from common_parser import admin as common_parser_admin


@pytest.fixture
def admin_context(db):
    user_model = get_user_model()
    admin_user = user_model.objects.create_superuser(
        username='admin-parsing-user',
        password='test-password',
        email='admin@example.com',
    )
    organization = Organization.objects.create(
        name='Admin organization',
        inn='1234567890',
        user=user_model.objects.create_user(username='organization-owner'),
    )
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Admin address',
    )
    branch_provider = BranchProvider.objects.create(
        branch=branch,
        provider='2gis',
        source_url='https://2gis.ru/irkutsk/firm/123',
    )
    return admin_user, branch_provider


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_shows_and_runs_sync_parsing(
    client,
    admin_context,
    monkeypatch,
):
    admin_user, branch_provider = admin_context
    client.force_login(admin_user)

    class FakeParsingOrchestrator:
        called_with: int | None = None

        def parse_branch_provider_sync(self, branch_provider_id: int):
            self.__class__.called_with = branch_provider_id
            return IngestionResult(
                parsed_count=3,
                created_count=2,
                skipped_count=1,
            )

    monkeypatch.setattr(
        common_parser_admin,
        'ParsingOrchestrator',
        FakeParsingOrchestrator,
    )

    change_url = reverse(
        'admin:common_parser_branchprovider_change',
        args=[branch_provider.pk],
    )
    response = client.get(change_url)

    assert response.status_code == 200
    assert 'Запустить без Celery' in response.content.decode()

    parse_url = reverse(
        'admin:common_parser_branchprovider_parse_sync',
        args=[branch_provider.pk],
    )
    response = client.post(parse_url)

    assert response.status_code == 302
    assert response.url == change_url
    assert FakeParsingOrchestrator.called_with == branch_provider.pk


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_admin_sync_parsing_is_blocked_outside_debug(client, admin_context):
    admin_user, branch_provider = admin_context
    client.force_login(admin_user)

    parse_url = reverse(
        'admin:common_parser_branchprovider_parse_sync',
        args=[branch_provider.pk],
    )

    response = client.post(parse_url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_rejects_twogis_url_without_numeric_firm_id(
    client,
    admin_context,
):
    admin_user, branch_provider = admin_context
    client.force_login(admin_user)

    change_url = reverse(
        'admin:common_parser_branchprovider_change',
        args=[branch_provider.pk],
    )
    response = client.post(
        change_url,
        {
            'branch': branch_provider.branch_id,
            'provider': '2gis',
            'source_url': 'https://2gis.ru/irkutsk/search/company',
            'external_place_id': '',
            'is_active': 'on',
        },
    )

    assert response.status_code == 200
    assert '2GIS URL must contain a numeric firm ID' in response.content.decode()

    branch_provider.refresh_from_db()
    assert branch_provider.source_url == 'https://2gis.ru/irkutsk/firm/123'

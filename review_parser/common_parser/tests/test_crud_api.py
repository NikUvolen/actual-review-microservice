import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from common_parser.models import Branch, BranchProvider, Organization, Review
from common_parser.services.parsing_orchestrator import ParsingOrchestrator


@pytest.fixture
def organization_context():
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username='owner',
        password='test-password',
    )
    other_user = user_model.objects.create_user(
        username='other-owner',
        password='test-password',
    )
    organization = Organization.objects.create(
        user=owner,
        name='Owner organization',
        inn='1234567890',
    )
    other_organization = Organization.objects.create(
        user=other_user,
        name='Other organization',
        inn='0987654321',
    )
    return owner, organization, other_organization


@pytest.fixture
def authenticated_client(organization_context):
    owner, _, _ = organization_context
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.mark.django_db
def test_crud_requires_authentication():
    response = APIClient().get(reverse('branch-list'))

    assert response.status_code == 401


@pytest.mark.django_db
def test_user_can_retrieve_and_update_own_organization(
    authenticated_client,
    organization_context,
):
    _, organization, _ = organization_context

    get_response = authenticated_client.get(reverse('organization-detail'))
    patch_response = authenticated_client.patch(
        reverse('organization-detail'),
        {'name': 'Updated organization'},
        format='json',
    )
    delete_response = authenticated_client.delete(reverse('organization-detail'))

    organization.refresh_from_db()
    assert get_response.status_code == 200
    assert get_response.data['id'] == organization.pk
    assert patch_response.status_code == 200
    assert organization.name == 'Updated organization'
    assert delete_response.status_code == 405


@pytest.mark.django_db
def test_user_without_organization_gets_not_found():
    user = get_user_model().objects.create_user(username='without-organization')
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(reverse('organization-detail'))

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_can_create_and_list_only_own_active_branches(
    authenticated_client,
    organization_context,
):
    _, organization, other_organization = organization_context
    Branch.objects.create(
        organization=other_organization,
        city='Irkutsk',
        address='Foreign address',
    )
    Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Inactive address',
        is_active=False,
    )

    create_response = authenticated_client.post(
        reverse('branch-list'),
        {'city': 'Irkutsk', 'address': 'Own address'},
        format='json',
    )
    list_response = authenticated_client.get(reverse('branch-list'))

    created_branch = Branch.objects.get(address='Own address')
    assert create_response.status_code == 201
    assert created_branch.organization == organization
    assert created_branch.is_active is True
    assert list_response.status_code == 200
    assert [branch['id'] for branch in list_response.data] == [created_branch.pk]


@pytest.mark.django_db
def test_user_cannot_access_foreign_branch(
    authenticated_client,
    organization_context,
):
    _, _, other_organization = organization_context
    foreign_branch = Branch.objects.create(
        organization=other_organization,
        city='Irkutsk',
        address='Foreign address',
    )

    response = authenticated_client.get(
        reverse('branch-detail', kwargs={'pk': foreign_branch.pk})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_branch_delete_deactivates_branch_and_its_providers(
    authenticated_client,
    organization_context,
):
    _, organization, _ = organization_context
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Own address',
    )
    provider = BranchProvider.objects.create(
        branch=branch,
        provider='2gis',
        source_url='https://2gis.ru/irkutsk/firm/123',
    )

    response = authenticated_client.delete(
        reverse('branch-detail', kwargs={'pk': branch.pk})
    )

    branch.refresh_from_db()
    provider.refresh_from_db()
    assert response.status_code == 204
    assert branch.is_active is False
    assert provider.is_active is False


@pytest.mark.django_db
def test_orchestrator_skips_providers_of_inactive_branches(
    monkeypatch,
    organization_context,
):
    _, organization, _ = organization_context
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Inactive branch',
        is_active=False,
    )
    BranchProvider.objects.create(
        branch=branch,
        provider='2gis',
        source_url='https://2gis.ru/irkutsk/firm/123',
        is_active=True,
    )
    enqueued: list[int] = []

    monkeypatch.setattr(
        ParsingOrchestrator,
        '_enqueue_branch_provider',
        lambda self, provider: enqueued.append(provider.pk) or 'task-id',
    )

    task_ids = ParsingOrchestrator().parse_active_branch_providers_async()

    assert task_ids == []
    assert enqueued == []


@pytest.mark.django_db
def test_user_can_create_provider_for_own_branch(
    authenticated_client,
    organization_context,
):
    _, organization, _ = organization_context
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Own address',
    )

    response = authenticated_client.post(
        reverse('branch-provider-list', kwargs={'branch_id': branch.pk}),
        {
            'provider': '2gis',
            'source_url': 'https://2gis.ru/irkutsk/firm/123',
            'external_place_id': '123',
        },
        format='json',
    )

    provider = BranchProvider.objects.get(branch=branch)
    assert response.status_code == 201
    assert provider.provider == '2gis'
    assert provider.is_active is True


@pytest.mark.django_db
def test_provider_rejects_url_from_another_domain(
    authenticated_client,
    organization_context,
):
    _, organization, _ = organization_context
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Own address',
    )

    response = authenticated_client.post(
        reverse('branch-provider-list', kwargs={'branch_id': branch.pk}),
        {
            'provider': '2gis',
            'source_url': 'https://yandex.ru/maps/org/123/reviews/',
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'source_url' in response.data


@pytest.mark.django_db
def test_user_cannot_create_provider_for_foreign_branch(
    authenticated_client,
    organization_context,
):
    _, _, other_organization = organization_context
    foreign_branch = Branch.objects.create(
        organization=other_organization,
        city='Irkutsk',
        address='Foreign address',
    )

    response = authenticated_client.post(
        reverse('branch-provider-list', kwargs={'branch_id': foreign_branch.pk}),
        {
            'provider': '2gis',
            'source_url': 'https://2gis.ru/irkutsk/firm/123',
        },
        format='json',
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_access_foreign_provider(
    authenticated_client,
    organization_context,
):
    _, _, other_organization = organization_context
    foreign_branch = Branch.objects.create(
        organization=other_organization,
        city='Irkutsk',
        address='Foreign address',
    )
    foreign_provider = BranchProvider.objects.create(
        branch=foreign_branch,
        provider='2gis',
        source_url='https://2gis.ru/irkutsk/firm/123',
    )

    response = authenticated_client.get(
        reverse(
            'branch-provider-detail',
            kwargs={'pk': foreign_provider.pk},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_provider_delete_marks_provider_inactive(
    authenticated_client,
    organization_context,
):
    _, organization, _ = organization_context
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Own address',
    )
    provider = BranchProvider.objects.create(
        branch=branch,
        provider='vlru',
        source_url='https://www.vl.ru/test-company',
    )

    response = authenticated_client.delete(
        reverse('branch-provider-detail', kwargs={'pk': provider.pk})
    )

    provider.refresh_from_db()
    assert response.status_code == 204
    assert provider.is_active is False


@pytest.mark.django_db
def test_user_cannot_read_foreign_provider_reviews(
    authenticated_client,
    organization_context,
):
    _, _, other_organization = organization_context
    foreign_branch = Branch.objects.create(
        organization=other_organization,
        city='Irkutsk',
        address='Foreign address',
    )
    foreign_provider = BranchProvider.objects.create(
        branch=foreign_branch,
        provider='2gis',
        source_url='https://2gis.ru/irkutsk/firm/123',
    )
    Review.objects.create(
        provider=foreign_provider,
        author_name='Author',
        text='Foreign review',
        external_review_id='foreign-review',
        content_hash='f' * 64,
    )

    response = authenticated_client.get(
        reverse(
            'branch-provider-reviews',
            kwargs={'branch_provider_id': foreign_provider.pk},
        )
    )

    assert response.status_code == 404

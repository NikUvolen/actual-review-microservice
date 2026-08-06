from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from common_parser.models import Branch, BranchProvider, Organization, Review


@pytest.fixture
def interleaving_context(db):
    user = get_user_model().objects.create_user(
        username='interleaving-owner',
        password='test-password',
    )
    organization = Organization.objects.create(
        user=user,
        name='Interleaving organization',
        inn='123456789012',
    )
    branch = Branch.objects.create(
        organization=organization,
        city='Irkutsk',
        address='Interleaving address',
    )
    providers = {
        '2gis': BranchProvider.objects.create(
            branch=branch,
            provider='2gis',
            source_url='https://2gis.ru/irkutsk/firm/123',
        ),
        'yandex': BranchProvider.objects.create(
            branch=branch,
            provider='yandex',
            source_url='https://yandex.ru/maps/org/123/reviews/',
        ),
        'vlru': BranchProvider.objects.create(
            branch=branch,
            provider='vlru',
            source_url='https://www.vl.ru/test-company',
        ),
    }
    base_date = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    reviews: list[Review] = []
    review_number = 1
    for provider_name, provider in providers.items():
        for index in range(4):
            reviews.append(
                Review(
                    provider=provider,
                    author_name=f'{provider_name} author {index}',
                    text=f'{provider_name}-{index}',
                    rating=5 - index,
                    published_date=base_date - timedelta(days=index),
                    external_review_id=f'{provider_name}-{index}',
                    content_hash=f'{review_number:064x}',
                )
            )
            review_number += 1
    Review.objects.bulk_create(reviews)

    client = APIClient()
    client.force_authenticate(user=user)
    return client, branch, providers


@pytest.mark.django_db
def test_branch_reviews_interleave_by_custom_provider_order_and_size(
    interleaving_context,
):
    client, branch, _ = interleaving_context

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        {
            'mode': 'interleave',
            'interleave_size': 2,
            'provider_order': 'vlru,2gis',
            'page_size': 100,
        },
    )

    assert response.status_code == 200
    assert response.data['provider_order'] == ['vlru', '2gis', 'yandex']
    assert [item['text'] for item in response.data['results']] == [
        'vlru-0',
        'vlru-1',
        '2gis-0',
        '2gis-1',
        'yandex-0',
        'yandex-1',
        'vlru-2',
        'vlru-3',
        '2gis-2',
        '2gis-3',
        'yandex-2',
        'yandex-3',
    ]
    assert [item['provider'] for item in response.data['providers']] == [
        'vlru',
        '2gis',
        'yandex',
    ]
    assert all(
        item['stored_review_count'] == 4
        for item in response.data['providers']
    )
    assert all(
        item['returned_count'] == 4
        for item in response.data['providers']
    )


@pytest.mark.django_db
def test_interleave_ignores_known_provider_not_attached_to_branch(
    interleaving_context,
):
    client, branch, _ = interleaving_context

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        {
            'mode': 'interleave',
            'provider_order': 'google,vlru',
            'page_size': 3,
        },
    )

    assert response.status_code == 200
    assert response.data['provider_order'] == ['vlru', '2gis', 'yandex']
    assert [item['provider_name'] for item in response.data['results']] == [
        'vlru',
        '2gis',
        'yandex',
    ]


@pytest.mark.django_db
def test_interleave_returns_empty_page_for_branch_without_providers(
    interleaving_context,
):
    client, branch, _ = interleaving_context
    BranchProvider.objects.filter(branch=branch).delete()

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        {'mode': 'interleave'},
    )

    assert response.status_code == 200
    assert response.data['count'] == 0
    assert response.data['provider_order'] == []
    assert response.data['providers'] == []
    assert response.data['results'] == []


@pytest.mark.django_db
def test_interleave_pagination_continues_the_same_sequence(
    interleaving_context,
):
    client, branch, _ = interleaving_context
    url = reverse('branch-reviews', kwargs={'branch_id': branch.pk})
    params = {
        'mode': 'interleave',
        'interleave_size': 1,
        'page_size': 4,
    }

    first_page = client.get(url, params)
    second_page = client.get(url, {**params, 'page': 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert [item['text'] for item in first_page.data['results']] == [
        '2gis-0',
        'yandex-0',
        'vlru-0',
        '2gis-1',
    ]
    assert [item['text'] for item in second_page.data['results']] == [
        'yandex-1',
        'vlru-1',
        '2gis-2',
        'yandex-2',
    ]


@pytest.mark.django_db
def test_interleave_continues_after_one_provider_runs_out(
    interleaving_context,
):
    client, branch, providers = interleaving_context
    Review.objects.filter(
        provider=providers['vlru'],
        external_review_id__in=('vlru-2', 'vlru-3'),
    ).delete()

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        {
            'mode': 'interleave',
            'interleave_size': 2,
            'page_size': 100,
        },
    )

    assert response.status_code == 200
    assert [item['text'] for item in response.data['results']] == [
        '2gis-0',
        '2gis-1',
        'yandex-0',
        'yandex-1',
        'vlru-0',
        'vlru-1',
        '2gis-2',
        '2gis-3',
        'yandex-2',
        'yandex-3',
    ]


@pytest.mark.django_db
def test_branch_reviews_support_rating_ordering(interleaving_context):
    client, branch, providers = interleaving_context
    Review.objects.create(
        provider=providers['2gis'],
        author_name='No rating',
        text='no-rating',
        rating=None,
        published_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        external_review_id='no-rating',
        content_hash='f' * 64,
    )

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        {'ordering': 'rating', 'page_size': 100},
    )

    assert response.status_code == 200
    ratings = [
        item['rating']
        for item in response.data['results']
        if item['rating'] is not None
    ]
    assert ratings == sorted(ratings)
    assert response.data['results'][-1]['text'] == 'no-rating'


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('params', 'error_field'),
    (
        (
            {'mode': 'interleave', 'provider_order': '2gis,telegram'},
            'provider_order',
        ),
        (
            {'mode': 'interleave', 'provider_order': '2gis,2gis'},
            'provider_order',
        ),
        (
            {'mode': 'interleave', 'interleave_size': 0},
            'interleave_size',
        ),
        (
            {'mode': 'interleave', 'interleave_size': 101},
            'interleave_size',
        ),
        (
            {'mode': 'standard', 'interleave_size': 2},
            'interleave_size',
        ),
    ),
)
def test_branch_reviews_reject_invalid_interleave_parameters(
    interleaving_context,
    params,
    error_field,
):
    client, branch, _ = interleaving_context

    response = client.get(
        reverse('branch-reviews', kwargs={'branch_id': branch.pk}),
        params,
    )

    assert response.status_code == 400
    assert error_field in response.data


@pytest.mark.django_db
def test_branch_provider_reviews_reject_interleave_mode(interleaving_context):
    client, _, providers = interleaving_context

    response = client.get(
        reverse(
            'branch-provider-reviews',
            kwargs={'branch_provider_id': providers['2gis'].pk},
        ),
        {'mode': 'interleave'},
    )

    assert response.status_code == 400
    assert 'mode' in response.data

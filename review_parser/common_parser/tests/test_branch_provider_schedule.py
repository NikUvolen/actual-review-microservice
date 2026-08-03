import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from common_parser.models import Branch, BranchProvider, Organization
from review_parser.celery import app as celery_app


@pytest.fixture
def branch_provider() -> BranchProvider:
    user = get_user_model().objects.create_user(username='schedule-user')
    organization = Organization.objects.create(
        name="Test Org",
        inn="1234567890",
        user=user,
    )
    branch = Branch.objects.create(
        organization=organization,
        city="Irkutsk",
        address="Test address",
    )
    return BranchProvider.objects.create(
        branch=branch,
        provider="2gis",
        source_url="https://2gis.ru/irkutsk/firm/123",
    )


@pytest.mark.django_db
def test_branch_provider_mark_as_parsed_updates_schedule_dates(branch_provider):
    branch_provider.mark_as_parsed()
    branch_provider.refresh_from_db()

    assert branch_provider.last_parse_date is not None


def test_celery_beat_runs_parsing_on_tuesday_and_saturday_at_six():
    beat_entry = celery_app.conf.beat_schedule[
        "enqueue-scheduled-branch-provider-parsing"
    ]
    schedule = beat_entry["schedule"]

    assert beat_entry["task"] == "enqueue_scheduled_branch_provider_parsing"
    assert schedule.minute == {0}
    assert schedule.hour == {6}
    assert schedule.day_of_week == {2, 6}

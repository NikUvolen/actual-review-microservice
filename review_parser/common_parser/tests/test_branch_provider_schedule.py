from datetime import datetime, timedelta, timezone

import pytest

from common_parser.models import Branch, BranchProvider, Organization


@pytest.fixture
def branch_provider() -> BranchProvider:
    organization = Organization.objects.create(
        name="Test Org",
        inn="1234567890",
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
@pytest.mark.parametrize(
    ("parse_frequency", "expected_delta"),
    [
        ("hourly", timedelta(hours=1)),
        ("daily", timedelta(days=1)),
        ("weekly", timedelta(days=7)),
        ("monthly", timedelta(days=30)),
    ],
)
def test_branch_provider_calculates_next_parse_date(
    branch_provider,
    parse_frequency,
    expected_delta,
):
    from_date = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
    branch_provider.parse_frequency = parse_frequency

    next_parse_date = branch_provider.get_next_parse_date(from_date)

    assert next_parse_date == from_date + expected_delta


@pytest.mark.django_db
def test_branch_provider_raises_for_unknown_parse_frequency(branch_provider):
    branch_provider.parse_frequency = "unknown"

    with pytest.raises(ValueError):
        branch_provider.get_next_parse_date()


@pytest.mark.django_db
def test_branch_provider_mark_as_parsed_updates_schedule_dates(branch_provider):
    branch_provider.parse_frequency = "daily"
    branch_provider.save(update_fields=["parse_frequency"])

    branch_provider.mark_as_parsed()
    branch_provider.refresh_from_db()

    assert branch_provider.last_parse_date is not None
    assert branch_provider.next_parse_date is not None
    assert branch_provider.next_parse_date - branch_provider.last_parse_date == (
        timedelta(days=1)
    )

import pytest

from common_parser.parsing.clients import twogis as twogis_module
from common_parser.parsing.clients.twogis import TwoGisClient
from common_parser.parsing.exceptions import (
    InvalidSourceUrlError,
    ProviderRequestError,
)


class FakeResponse:
    status_code = 500
    text = "provider error"

    def json(self) -> dict:
        return {}


def test_twogis_client_extracts_firm_id():
    client = TwoGisClient(api_key="test-key")

    assert client.extract_firm_id("https://2gis.ru/irkutsk/firm/123") == "123"


def test_twogis_client_raises_for_invalid_source_url():
    client = TwoGisClient(api_key="test-key")

    with pytest.raises(InvalidSourceUrlError):
        client.extract_firm_id("https://2gis.ru/irkutsk/search/company")


def test_twogis_client_raises_provider_request_error(monkeypatch):
    monkeypatch.setattr(twogis_module, "http_get", lambda *args, **kwargs: FakeResponse())
    client = TwoGisClient(api_key="test-key")

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_reviews_page("123")

    assert exc_info.value.provider == "2gis"
    assert exc_info.value.status_code == 500
    assert exc_info.value.response_text == "provider error"


def test_twogis_client_fetches_at_most_100_newest_reviews(monkeypatch):
    calls: list[dict] = []

    class ReviewsResponse:
        status_code = 200
        text = ""

        def __init__(self, payload: dict):
            self.payload = payload

        def json(self) -> dict:
            return self.payload

    def fake_get(url: str, *, params: dict):
        calls.append(params)
        offset = params["offset"]
        limit = params["limit"]
        return ReviewsResponse(
            {
                "meta": {"total_count": 250},
                "reviews": [
                    {"id": f"review-{index}"}
                    for index in range(offset, offset + limit)
                ],
            }
        )

    monkeypatch.setattr(twogis_module, "http_get", fake_get)

    result = TwoGisClient(api_key="test-key").get_all_reviews("123")

    assert len(result["reviews"]) == 100
    assert [call["offset"] for call in calls] == [0, 50]
    assert all(call["sort_by"] == "date_created" for call in calls)

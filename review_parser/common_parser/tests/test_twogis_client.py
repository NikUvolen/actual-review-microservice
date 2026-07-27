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

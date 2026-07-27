import pytest

from common_parser.parsing.clients import vlru as vlru_module
from common_parser.parsing.clients.vlru import VlRuClient
from common_parser.parsing.exceptions import (
    InvalidSourceUrlError,
    ProviderRequestError,
)


class FakeResponse:
    status_code = 500
    text = "provider error"

    def json(self) -> dict:
        return {}


def test_vlru_client_extracts_company_slug():
    client = VlRuClient()

    assert client.extract_company_slug("https://www.vl.ru/test-company") == "test-company"


def test_vlru_client_raises_for_invalid_source_url():
    client = VlRuClient()

    with pytest.raises(InvalidSourceUrlError):
        client.extract_company_slug("https://www.vl.ru")


def test_vlru_client_raises_provider_request_error_for_comments_thread(monkeypatch):
    monkeypatch.setattr(vlru_module, "http_get", lambda *args, **kwargs: FakeResponse())
    client = VlRuClient()

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_comments_thread("test-company")

    assert exc_info.value.provider == "vlru"
    assert exc_info.value.status_code == 500
    assert exc_info.value.response_text == "provider error"


def test_vlru_client_raises_provider_request_error_for_comments_page(monkeypatch):
    monkeypatch.setattr(vlru_module, "http_get", lambda *args, **kwargs: FakeResponse())
    client = VlRuClient()

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_comments_page(
            company_slug="test-company",
            thread_id="thread-1",
            before_comment_id="1",
        )

    assert exc_info.value.provider == "vlru"
    assert exc_info.value.status_code == 500
    assert exc_info.value.response_text == "provider error"


def test_vlru_client_raises_provider_request_error_for_company_page(monkeypatch):
    monkeypatch.setattr(vlru_module, "http_get", lambda *args, **kwargs: FakeResponse())
    client = VlRuClient()

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_company_page("test-company")

    assert exc_info.value.provider == "vlru"
    assert exc_info.value.status_code == 500
    assert exc_info.value.response_text == "provider error"

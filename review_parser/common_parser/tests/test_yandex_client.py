from urllib.parse import parse_qs, urlsplit

from common_parser.parsing.clients.yandex import YandexClient


def test_yandex_client_builds_page_url_sorted_by_time():
    client = YandexClient()

    url = client.build_reviews_page_url(
        "https://yandex.ru/maps/-/short-link",
        business_id="123",
        page=2,
    )
    query = parse_qs(urlsplit(url).query)

    assert urlsplit(url).path == "/maps/org/123/reviews/"
    assert query["page"] == ["2"]
    assert query["reviews[sort]"] == ["by_time"]


def test_yandex_client_fetches_at_most_12_pages(monkeypatch):
    client = YandexClient()
    requested_pages: list[int] = []

    monkeypatch.setattr(
        client,
        "_resolve_source",
        lambda source_url: (source_url, "123"),
    )

    def fake_get_reviews_page(
        source_url: str,
        business_id: str,
        page: int,
    ) -> dict:
        requested_pages.append(page)
        return {
            "params": {"totalPages": 100},
            "reviews": [],
        }

    monkeypatch.setattr(client, "get_reviews_page", fake_get_reviews_page)

    results = client.get_all_review_results("https://yandex.ru/maps/org/123/reviews/")

    assert len(results) == 12
    assert requested_pages == list(range(1, 13))

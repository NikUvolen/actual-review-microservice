import pytest

from common_parser.models import Branch
from common_parser.parsing.dto import ParseResult
from common_parser.parsing.ingestion import IngestionResult
from common_parser.services.review_parsing import (
    MissingReviewSourceUrlError,
    ReviewParsingService,
    UnknownProviderError,
)


def test_review_parsing_service_gets_2gis_source_url():
    branch = Branch(twogis_map_url="https://2gis.ru/irkutsk/firm/123")

    source_url = ReviewParsingService().get_source_url(branch, "2gis")

    assert source_url == "https://2gis.ru/irkutsk/firm/123"


def test_review_parsing_service_gets_vlru_source_url():
    branch = Branch(vlru_url="https://www.vl.ru/test-company")

    source_url = ReviewParsingService().get_source_url(branch, "vlru")

    assert source_url == "https://www.vl.ru/test-company"


def test_review_parsing_service_raises_for_unknown_provider():
    service = ReviewParsingService()

    with pytest.raises(UnknownProviderError):
        service.get_source_url(Branch(), "unknown")

    with pytest.raises(UnknownProviderError):
        service.get_parser("unknown")


def test_review_parsing_service_raises_for_missing_source_url():
    service = ReviewParsingService()

    with pytest.raises(MissingReviewSourceUrlError):
        service.get_source_url(Branch(twogis_map_url=""), "2gis")


def test_review_parsing_service_parses_and_saves_branch_reviews():
    class FakeParser:
        parsed_urls: list[str] = []

        def parse(self, source_url: str) -> ParseResult:
            self.parsed_urls.append(source_url)
            return ParseResult(
                provider="2gis",
                source_url=source_url,
                external_count=1,
                avg_rating=4.8,
                reviews=[],
            )

    class FakeIngestionService:
        saved_branch: Branch | None = None
        saved_result: ParseResult | None = None

        def save(self, branch: Branch, result: ParseResult) -> IngestionResult:
            self.saved_branch = branch
            self.saved_result = result
            return IngestionResult(
                parsed_count=1,
                created_count=1,
                skipped_count=0,
            )

    branch = Branch(twogis_map_url="https://2gis.ru/irkutsk/firm/123")
    ingestion_service = FakeIngestionService()
    service = ReviewParsingService(ingestion_service=ingestion_service)
    service.parser_classes = {"2gis": FakeParser}

    result = service.parse_and_save_branch_reviews(branch, "2gis")

    assert FakeParser.parsed_urls == ["https://2gis.ru/irkutsk/firm/123"]
    assert ingestion_service.saved_branch is branch
    assert ingestion_service.saved_result is not None
    assert ingestion_service.saved_result.provider == "2gis"
    assert ingestion_service.saved_result.source_url == "https://2gis.ru/irkutsk/firm/123"
    assert result.parsed_count == 1
    assert result.created_count == 1
    assert result.skipped_count == 0

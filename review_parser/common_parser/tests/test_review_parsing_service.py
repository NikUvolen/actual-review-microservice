import pytest

from common_parser.models import BranchProvider
from common_parser.parsing.dto import ParseResult
from common_parser.parsing.ingestion import IngestionResult
from common_parser.services.review_parsing import (
    MissingReviewSourceUrlError,
    ReviewParsingService,
    UnknownProviderError,
)


def test_review_parsing_service_raises_for_unknown_provider():
    service = ReviewParsingService()

    with pytest.raises(UnknownProviderError):
        service.get_parser("unknown")


def test_review_parsing_service_raises_for_missing_source_url():
    service = ReviewParsingService()
    branch_provider = BranchProvider(provider="2gis", source_url="")

    with pytest.raises(MissingReviewSourceUrlError):
        service.parse_and_save_provider_reviews(branch_provider)


def test_review_parsing_service_parses_and_saves_provider_reviews():
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
        saved_provider: BranchProvider | None = None
        saved_result: ParseResult | None = None

        def save(
            self,
            branch_provider: BranchProvider,
            result: ParseResult,
        ) -> IngestionResult:
            self.saved_provider = branch_provider
            self.saved_result = result
            return IngestionResult(
                parsed_count=1,
                created_count=1,
                skipped_count=0,
            )

    branch_provider = BranchProvider(
        provider="2gis",
        source_url="https://2gis.ru/irkutsk/firm/123",
    )
    ingestion_service = FakeIngestionService()
    service = ReviewParsingService(ingestion_service=ingestion_service)
    service.parser_classes = {"2gis": FakeParser}

    result = service.parse_and_save_provider_reviews(branch_provider)

    assert FakeParser.parsed_urls == ["https://2gis.ru/irkutsk/firm/123"]
    assert ingestion_service.saved_provider is branch_provider
    assert ingestion_service.saved_result is not None
    assert ingestion_service.saved_result.provider == "2gis"
    assert ingestion_service.saved_result.source_url == "https://2gis.ru/irkutsk/firm/123"
    assert result.parsed_count == 1
    assert result.created_count == 1
    assert result.skipped_count == 0

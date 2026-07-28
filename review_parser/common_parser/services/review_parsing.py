from common_parser.models import Branch
from common_parser.parsing.ingestion import ReviewIngestionService, IngestionResult
from common_parser.parsing.providers import (
    BaseReviewParser,
    TwoGisParser,
    VlRuParser,
)


class UnknownProviderError(Exception):
    pass


class MissingReviewSourceUrlError(Exception):
    pass


class ReviewParsingService:
    parser_classes: dict[str, type[BaseReviewParser]] = {
        '2gis': TwoGisParser,
        'vlru': VlRuParser,
    }

    branch_url_fields: dict[str, str] = {
        '2gis': 'twogis_map_url',
        'vlru': 'vlru_url',
    }

    def __init__(self, ingestion_service: ReviewIngestionService | None = None):
        self.ingestion_service = ingestion_service or ReviewIngestionService()

    def get_parser(self, provider: str) -> BaseReviewParser:
        parser_class = self.parser_classes.get(provider)
        if parser_class is None:
            raise UnknownProviderError(f'Unknown provider: {provider}')
        return parser_class()

    def get_source_url(self, branch: Branch, provider: str) -> str:
        field_name = self.branch_url_fields.get(provider)
        if field_name is None:
            raise UnknownProviderError(f'Unknown provider: {provider}')

        source_url = getattr(branch, field_name, None)
        if not source_url:
            raise MissingReviewSourceUrlError(
                f'Missing review source URL for branch {branch.pk} and provider {provider}'
            )

        return source_url

    def parse_and_save_branch_reviews(self, branch: Branch, provider: str) -> IngestionResult:
        source_url = self.get_source_url(branch, provider)
        parser = self.get_parser(provider)

        parse_result = parser.parse(source_url)

        return self.ingestion_service.save(branch, parse_result)

from common_parser.models import BranchProvider
from common_parser.parsing.ingestion import ReviewIngestionService, IngestionResult
from common_parser.parsing.providers import (
    BaseReviewParser,
    TwoGisParser,
    VlRuParser,
    YandexParser,
)


class UnknownProviderError(Exception):
    pass


class MissingReviewSourceUrlError(Exception):
    pass


class ReviewParsingService:
    parser_classes: dict[str, type[BaseReviewParser]] = {
        '2gis': TwoGisParser,
        'vlru': VlRuParser,
        'yandex': YandexParser,
    }

    def __init__(self, ingestion_service: ReviewIngestionService | None = None):
        self.ingestion_service = ingestion_service or ReviewIngestionService()

    def get_parser(self, provider: str) -> BaseReviewParser:
        parser_class = self.parser_classes.get(provider)
        if parser_class is None:
            raise UnknownProviderError(f'Unknown provider: {provider}')
        return parser_class()

    def parse_and_save_provider_reviews(self, branch_provider: BranchProvider) -> IngestionResult:
        if not branch_provider.source_url:
            raise MissingReviewSourceUrlError(
                f'Missing source URL for BranchProvider: {branch_provider.pk}'
            )

        parser = self.get_parser(branch_provider.provider)

        parse_result = parser.parse(branch_provider.source_url) 

        return self.ingestion_service.save(
            branch_provider=branch_provider,
            result=parse_result,
        )

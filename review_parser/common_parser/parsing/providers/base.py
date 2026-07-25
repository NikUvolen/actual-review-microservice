from abc import ABC, abstractmethod

from common_parser.parsing.dto import ParseResult


class BaseReviewParser(ABC):
    provider: str

    @abstractmethod
    def parse(self, source_url: str) -> ParseResult:
        """
        Parse reviews from the given URL.

        Args:
            source_url (str): The URL to parse reviews from.
        """
        pass

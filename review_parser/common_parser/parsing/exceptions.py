class ParserError(Exception):
    """Base exception for review parsing errors."""


class InvalidSourceUrlError(ParserError):
    """Raised when a parser cannot extract external object id from source URL."""


class ProviderRequestError(ParserError):
    """Raised when an external provider request fails."""

    def __init__(self, provider: str, status_code: int, response_text: str):
        self.provider = provider
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(
            f"{provider} request failed with status {status_code}: {response_text}"
        )

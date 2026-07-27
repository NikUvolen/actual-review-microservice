from datetime import datetime
from dataclasses import dataclass


@dataclass
class ParsedReview:
    """
    Parsed review data transfer object.
    """
    external_id: str | None
    author_name: str
    author_avatar_url: str | None
    rating: float | None
    text: str
    pub_date: datetime | None
    review_url: str | None
    media_urls: list[str]


@dataclass
class ParseResult:
    """
    Parse result data transfer object.
    """
    provider: str
    source_url: str
    external_count: int | None
    avg_rating: float | None
    reviews: list[ParsedReview]
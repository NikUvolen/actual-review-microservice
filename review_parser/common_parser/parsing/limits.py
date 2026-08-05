DEFAULT_REVIEW_LIMIT = 100

REVIEW_LIMITS_BY_PROVIDER = {
    "2gis": 100,
    "vlru": 100,
    "yandex": 100,
}


def get_review_limit(provider: str) -> int:
    return REVIEW_LIMITS_BY_PROVIDER.get(provider, DEFAULT_REVIEW_LIMIT)

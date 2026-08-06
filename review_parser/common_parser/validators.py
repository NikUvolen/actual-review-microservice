import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


TWOGIS_DOMAINS = ('2gis.ru', '2gis.com')
TWOGIS_FIRM_PATH_PATTERN = re.compile(r'(?:^|/)firm/\d+(?:/|$)')


def validate_twogis_source_url(source_url: str) -> None:
    parts = urlsplit(source_url)
    hostname = (parts.hostname or '').lower()

    domain_is_valid = any(
        hostname == domain or hostname.endswith(f'.{domain}')
        for domain in TWOGIS_DOMAINS
    )
    firm_path_is_valid = bool(TWOGIS_FIRM_PATH_PATTERN.search(parts.path))

    if not domain_is_valid or not firm_path_is_valid:
        raise ValidationError(
            '2GIS URL must contain a numeric firm ID: '
            'https://2gis.ru/<city>/firm/<firm_id>.'
        )

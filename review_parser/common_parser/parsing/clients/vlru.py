from urllib.parse import urlparse

from common_parser.services.http_client import get as http_get
from common_parser.parsing.exceptions import (
    InvalidSourceUrlError,
    ProviderRequestError,
)


class VlRuClient:
    base_url = 'https://www.vl.ru'

    def extract_company_slug(self, source_url: str) -> str:
        path_parts = [
            part
            for part in urlparse(source_url).path.split('/')
            if part
        ]
        if not path_parts:
            raise InvalidSourceUrlError(
                'Cannot extract vl.ru company slug from source URL.'
            )
        return path_parts[-1]

    def get_comments_thread(self, company_slug: str) -> dict:
        url = f'{self.base_url}/commentsgate/ajax/thread/company/{company_slug}/embedded'

        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/{company_slug}'
        }
        params = {
            'theme': 'company',
            'moderatorMode': '1'
        }

        response = http_get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise ProviderRequestError(
                provider='vlru',
                status_code=response.status_code,
                response_text=response.text,
            )
        return response.json()

    def get_comments_page(
        self,
        *,
        company_slug: str,
        thread_id: str,
        before_comment_id: str
    ) -> dict:
        url = f'{self.base_url}/commentsgate/ajax/comments/{thread_id}/rendered'

        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/{company_slug}'
        }
        params = {
            'theme': 'company',
            'moderatorMode': '1',
            'before': f'{before_comment_id}'
        }

        response = http_get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise ProviderRequestError(
                provider='vlru',
                status_code=response.status_code,
                response_text=response.text,
            )
        return response.json()

    def get_company_page(self, company_slug: str) -> str:
        url = f'{self.base_url}/{company_slug}'

        headers = {
            'Accept': (
                'text/html,application/xhtml+xml,'
                'application/xml;q=0.9,image/avif,'
                'image/webp,image/apng,*/*;q=0.8,'
                'application/signed-exchange;v=b3;q=0.9'
            ),
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        response = http_get(url, headers=headers)

        if response.status_code != 200:
            raise ProviderRequestError(
                provider='vlru',
                status_code=response.status_code,
                response_text=response.text,
            )

        return response.text

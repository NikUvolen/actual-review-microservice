from datetime import datetime

from bs4 import BeautifulSoup
from bs4.element import Tag

from common_parser.parsing.clients.vlru import VlRuClient
from common_parser.parsing.dto import ParseResult, ParsedReview
from common_parser.parsing.providers.base import BaseReviewParser


class VlRuParser(BaseReviewParser):
    provider = 'vlru'

    def __init__(self, client: VlRuClient | None = None):
        self.client = client or VlRuClient()

    def _parse_author(self, review_item: Tag) -> str:
        author_block = review_item.find('span', class_='user-name')
        if not author_block:
            return 'Anonymous'
        return author_block.get_text(strip=True) or 'Anonymous'

    def _parse_avatar(self, review_item: Tag) -> str | None:
        avatar_img = review_item.find('img', class_='avatar')

        if not isinstance(avatar_img, Tag):
            return None

        src = avatar_img.get('src')
        return str(src) if src else None

    def _parse_rating(self, review_item: Tag) -> float:
        rating_wrapper = review_item.find('div', class_='cmt-rating-wrapper')
        if not isinstance(rating_wrapper, Tag):
            return 0

        active_rating = rating_wrapper.find('div', class_='active')
        if not isinstance(active_rating, Tag):
            return 0

        raw_value = active_rating.get('data-value')
        if not raw_value:
            return 0

        try:
            return float(str(raw_value)) * 5
        except ValueError:
            return 0

    def _parse_text(self, review_item: Tag) -> str:
        comment_text = review_item.find('p', class_='comment-text')
        if not isinstance(comment_text, Tag):
            return ''
        return comment_text.get_text(strip=True) or ''

    def _parse_published_date(self, review_item: Tag) -> datetime | None:
        raw_timestamp = review_item.get('data-timestamp')
        if not isinstance(raw_timestamp, str):
            return None

        try:
            return datetime.fromtimestamp(int(raw_timestamp))
        except (TypeError, ValueError):
            return None

    def _parse_media_urls(self, review_item: Tag) -> list[str]:
        images_wrapper = review_item.find('div', class_='comment-images-wrapper')
        if not isinstance(images_wrapper, Tag):
            return []

        media_urls: list[str] = []
        for item in images_wrapper.find_all('div', class_='item'):
            if not isinstance(item, Tag):
                continue

            link = item.find('a')
            if not isinstance(link, Tag):
                continue

            url = link.get('href')
            if url:
                media_urls.append(str(url))

        return media_urls

    def _parse_reviews_html(self, html_content: str) -> list[ParsedReview]:
        soup = BeautifulSoup(html_content, 'html.parser')

        reviews_list = soup.find('ul', {'id': 'CommentsList'})
        if not isinstance(reviews_list, Tag):
            reviews_list = soup

        reviews = []
        for review_item in reviews_list.find_all('li', recursive=False):
            if not isinstance(review_item, Tag):
                continue

            if review_item.get('data-parent-id'):
                continue

            external_id = review_item.get('comment')
            if not external_id:
                continue

            reviews.append(
                ParsedReview(
                    external_id=str(external_id),
                    author_name=self._parse_author(review_item),
                    author_avatar_url=self._parse_avatar(review_item),
                    rating=self._parse_rating(review_item),
                    text=self._parse_text(review_item),
                    pub_date=self._parse_published_date(review_item),
                    review_url=None,
                    media_urls=self._parse_media_urls(review_item)
                )
            )
        return reviews

    def _parse_avg_rating(self, html_content: str) -> float | None:
        soup = BeautifulSoup(html_content, 'html.parser')

        stars = soup.select_one('ul.stars.control')
        if not isinstance(stars, Tag):
            return None

        data_default = stars.get('data-default')
        if data_default:
            try:
                coeff = float(str(data_default).replace(',', '.'))
                return round(coeff * 5, 2)
            except ValueError:
                pass

        return None

    # max_pages для тестов на получение только определенного количества страниц
    def parse(self, source_url: str, *, max_pages: int | None = None) -> ParseResult:
        company_slug = self.client.extract_company_slug(source_url)

        first_page = self.client.get_comments_thread(company_slug)
        data = first_page.get('data') or {}
        avg_rating = self._parse_avg_rating(self.client.get_company_page(company_slug))

        reviews = self._parse_reviews_html(data.get('content') or '')

        thread_id = data.get('threadId')
        last_comment_id = data.get('lastCommentId')

        loaded_pages = 0

        while thread_id and last_comment_id:
            if max_pages is not None and loaded_pages >= max_pages:
                break

            page = self.client.get_comments_page(
                company_slug=company_slug,
                thread_id=thread_id,
                before_comment_id=last_comment_id
            )

            loaded_pages += 1

            page_data = page.get('data') or {}
            page_reviews = self._parse_reviews_html(page_data.get('content') or '')

            reviews.extend(page_reviews)

            new_last_comment_id = page_data.get('lastCommentId')

            if not new_last_comment_id or new_last_comment_id == last_comment_id:
                break

            last_comment_id = new_last_comment_id

        return ParseResult(
            provider=self.provider,
            source_url=source_url,
            external_count=len(reviews),
            avg_rating=avg_rating,
            reviews=reviews
        )

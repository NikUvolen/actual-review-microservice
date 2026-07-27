import pytest

from common_parser.parsing.providers.vlru import VlRuParser


class FakeVlRuClient:
    def extract_company_slug(self, source_url: str) -> str:
        return "test-company"

    def get_company_page(self, company_slug: str) -> str:
        return """
        <html>
          <ul class="stars control" data-default="0,7162" style="width: 71.62%;"></ul>
        </html>
        """

    def get_comments_thread(self, company_slug: str) -> dict:
        return {
            "data": {
                "content": """
                <ul id="CommentsList">
                  <li comment="101" data-timestamp="1704067200">
                    <span class="user-name">Petr</span>
                    <img class="avatar" src="https://example.com/avatar.png"/>
                    <div class="cmt-rating-wrapper">
                      <div class="active" data-value="0.8"></div>
                    </div>
                    <p class="comment-text">Good service</p>
                    <div class="comment-images-wrapper">
                      <div class="item">
                        <a href="https://example.com/photo1.jpg"></a>
                      </div>
                    </div>
                  </li>
                  <li comment="102" data-parent-id="101" data-timestamp="1704067300">
                    <p class="comment-text">Owner answer</p>
                  </li>
                </ul>
                """,
                "threadId": "thread-1",
                "lastCommentId": None,
                "commentsCount": 1,
            },
        }

    def get_comments_page(
        self,
        *,
        company_slug: str,
        thread_id: str,
        before_comment_id: str,
    ) -> dict:
        raise AssertionError("Pagination should not be called")


def test_vlru_parser_returns_normalized_result():
    parser = VlRuParser(client=FakeVlRuClient())

    result = parser.parse("https://www.vl.ru/test-company")

    assert result.provider == "vlru"
    assert result.source_url == "https://www.vl.ru/test-company"
    assert result.external_count == 1
    assert result.avg_rating == 3.58
    assert len(result.reviews) == 1

    review = result.reviews[0]
    assert review.external_id == "101"
    assert review.author_name == "Petr"
    assert review.author_avatar_url == "https://example.com/avatar.png"
    assert review.rating == 4.0
    assert review.text == "Good service"
    assert review.review_url is None
    assert review.media_urls == ["https://example.com/photo1.jpg"]


class FakeVlRuPaginatedClient:
    def extract_company_slug(self, source_url: str) -> str:
        return "test-company"

    def get_company_page(self, company_slug: str) -> str:
        return '<ul class="stars control" data-default="1"></ul>'

    def get_comments_thread(self, company_slug: str) -> dict:
        return {
            "data": {
                "content": '<ul id="CommentsList"><li comment="2" data-timestamp="1704067200"></li></ul>',
                "threadId": "thread-1",
                "lastCommentId": "2",
                "commentsCount": 2,
            },
        }

    def get_comments_page(
        self,
        *,
        company_slug: str,
        thread_id: str,
        before_comment_id: str,
    ) -> dict:
        assert company_slug == "test-company"
        assert thread_id == "thread-1"
        assert before_comment_id == "2"
        return {
            "data": {
                "content": '<ul id="CommentsList"><li comment="1" data-timestamp="1704067100"></li></ul>',
                "lastCommentId": None,
            },
        }


def test_vlru_parser_loads_next_page():
    parser = VlRuParser(client=FakeVlRuPaginatedClient())

    result = parser.parse("https://www.vl.ru/test-company")

    assert result.avg_rating == 5.0
    assert len(result.reviews) == 2
    assert [review.external_id for review in result.reviews] == ["2", "1"]


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<ul class="stars control" data-default="0,7162"></ul>', 3.58),
        ('<ul class="stars control" data-default="1"></ul>', 5.0),
        ("<html></html>", None),
    ],
)
def test_vlru_parser_parses_average_rating(html: str, expected: float | None):
    parser = VlRuParser(client=FakeVlRuClient())

    assert parser._parse_avg_rating(html) == expected

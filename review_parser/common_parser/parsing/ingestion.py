from dataclasses import dataclass
from hashlib import sha256

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from common_parser.models import (
    BranchProvider,
    ProviderStat,
    Review,
    ReviewMedia,
)
from common_parser.parsing.dto import ParseResult, ParsedReview
from common_parser.parsing.limits import get_review_limit


@dataclass
class IngestionResult:
    parsed_count: int
    created_count: int
    skipped_count: int


class ReviewIngestionService:
    def _get_review_limit(self, branch_provider: BranchProvider) -> int:
        return get_review_limit(branch_provider.provider)

    def _make_content_hash(self, parsed_review: ParsedReview) -> str:
        if parsed_review.external_id:
            raw_value = f"external:{parsed_review.external_id}"
        else:
            published_at = parsed_review.pub_date.isoformat() if parsed_review.pub_date else ""
            raw_value = "|".join(
                [
                    parsed_review.author_name.strip().lower(),
                    str(parsed_review.rating or ""),
                    published_at,
                    parsed_review.text.strip(),
                    parsed_review.review_url or "",
                ]
            )

        return sha256(raw_value.encode("utf-8")).hexdigest()

    def _review_exists(self, branch_provider: BranchProvider, parsed_review: ParsedReview) -> bool:
        if parsed_review.external_id:
            return Review.objects.filter(
                provider=branch_provider,
                external_review_id=parsed_review.external_id,
            ).exists()

        return Review.objects.filter(
            provider=branch_provider,
            content_hash=self._make_content_hash(parsed_review),
        ).exists()

    def _create_review_media(self, review: Review, parsed_review: ParsedReview) -> None:
        ReviewMedia.objects.bulk_create(
            [
                ReviewMedia(
                    review=review,
                    media_type="photo", # TODO: заменить на ParsedMedia
                    url=media_url
                )
                for media_url in parsed_review.media_urls
            ]
        )

    def _update_provider_stats(self, branch_provider: BranchProvider, result: ParseResult) -> None:
        ProviderStat.objects.update_or_create(
            provider=branch_provider,
            defaults={
                "external_rating_avg": result.avg_rating,
                "last_parse_date": timezone.now()
            }
        )

    def _get_latest_reviews(
        self,
        reviews: list[ParsedReview],
        limit: int,
    ) -> list[ParsedReview]:
        return sorted(
            reviews,
            key=lambda review: (
                review.pub_date.timestamp() if review.pub_date else float("-inf")
            ),
            reverse=True,
        )[:limit]

    def _prune_old_reviews(
        self,
        branch_provider: BranchProvider,
        limit: int,
    ) -> None:
        review_ids_to_delete = list(
            Review.objects
            .filter(provider=branch_provider)
            .order_by(
                F("published_date").desc(nulls_last=True),
                "-pk",
            )
            .values_list("pk", flat=True)[limit:]
        )

        if review_ids_to_delete:
            Review.objects.filter(pk__in=review_ids_to_delete).delete()

    def save(self, branch_provider: BranchProvider, result: ParseResult) -> IngestionResult:
        created_count = 0
        review_limit = self._get_review_limit(branch_provider)
        reviews_to_ingest = self._get_latest_reviews(result.reviews, review_limit)
        skipped_count = len(result.reviews) - len(reviews_to_ingest)

        self._update_provider_stats(branch_provider, result)

        for parsed_review in reviews_to_ingest:
            if self._review_exists(branch_provider, parsed_review):
                skipped_count += 1
                continue

            try:
                with transaction.atomic():
                    review = Review.objects.create(
                        provider=branch_provider,
                        author_name=parsed_review.author_name,
                        author_avatar_url=parsed_review.author_avatar_url,
                        rating=parsed_review.rating,
                        text=parsed_review.text,
                        published_date=parsed_review.pub_date,
                        review_url=parsed_review.review_url,
                        external_review_id=parsed_review.external_id,
                        content_hash=self._make_content_hash(parsed_review),
                    )
                    self._create_review_media(review, parsed_review)
            except IntegrityError:
                skipped_count += 1
                continue

            created_count += 1

        self._prune_old_reviews(branch_provider, review_limit)

        return IngestionResult(
            parsed_count=len(result.reviews),
            created_count=created_count,
            skipped_count=skipped_count,
        )

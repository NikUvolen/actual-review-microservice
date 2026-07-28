from dataclasses import dataclass
from hashlib import sha256

from django.db import IntegrityError, transaction
from django.utils import timezone

from common_parser.models import (
    Branch,
    BranchProvider,
    ProviderStat,
    Review,
    ReviewMedia,
)
from common_parser.parsing.dto import ParseResult, ParsedReview


@dataclass
class IngestionResult:
    parsed_count: int
    created_count: int
    skipped_count: int


class ReviewIngestionService:
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

    def _get_or_create_branch_provider(self, branch: Branch, result: ParseResult) -> BranchProvider:
        branch_provider, _ = BranchProvider.objects.get_or_create(
            branch=branch,
            provider=result.provider,
            source_url=result.source_url,
            defaults={
                "external_place_id": None
            }
        )
        return branch_provider

    def save(self, branch: Branch, result: ParseResult) -> IngestionResult:
        created_count = 0
        skipped_count = 0

        branch_provider = self._get_or_create_branch_provider(branch, result)

        self._update_provider_stats(branch_provider, result)

        for parsed_review in result.reviews:
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

        return IngestionResult(
            parsed_count=len(result.reviews),
            created_count=created_count,
            skipped_count=skipped_count,
        )

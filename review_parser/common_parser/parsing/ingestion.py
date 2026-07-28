from dataclasses import dataclass

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
    def _review_exists(
        self, 
        branch: Branch, 
        provider: str, 
        parsed_review: ParsedReview
    ) -> bool:
        """
        Check if a review already exists 
        in the database based on the branch, provider, and external ID.
        """
        if parsed_review.review_url:
            return Review.objects.filter(
                branch=branch,
                provider=provider,
                review_url=parsed_review.review_url
            ).exists()

        return Review.objects.filter(
            branch=branch,
            provider=provider,
            author=parsed_review.author_name,
            content=parsed_review.text,
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

    def _update_legacy_branch_stats(self, branch: Branch, result: ParseResult) -> None:
        update_fields = []

        if result.provider == "2gis":
            if result.external_count is not None:
                branch.twogis_review_count = result.external_count
                update_fields.append("twogis_review_count")

            if result.avg_rating is not None:
                branch.twogis_review_avg = result.avg_rating
                update_fields.append("twogis_review_avg")

            branch.twogis_parse_date = timezone.now()
            update_fields.append("twogis_parse_date")

        elif result.provider == "vlru":
            branch.vlru_review_count = len(result.reviews)
            update_fields.append("vlru_review_count")

            if result.avg_rating is not None:
                branch.vlru_review_avg = result.avg_rating
                update_fields.append("vlru_review_avg")

            branch.vlru_parse_date = timezone.now()
            update_fields.append("vlru_parse_date")

        if update_fields:
            branch.save(update_fields=update_fields)

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
        self._update_legacy_branch_stats(branch, result)

        for parsed_review in result.reviews:
            if self._review_exists(branch, result.provider, parsed_review):
                skipped_count += 1
                continue

            review = Review.objects.create(
                branch=branch,
                author=parsed_review.author_name,
                avatar=parsed_review.author_avatar_url,
                rating=parsed_review.rating or 0,
                content=parsed_review.text,
                published_date=parsed_review.pub_date or timezone.now(), # TODO: уточнить про None
                provider=result.provider,
                photos=','.join(parsed_review.media_urls) if parsed_review.media_urls else '',
                review_url=parsed_review.review_url,
            )

            self._create_review_media(review, parsed_review)

            created_count += 1

        return IngestionResult(
            parsed_count=len(result.reviews),
            created_count=created_count,
            skipped_count=skipped_count,
        )

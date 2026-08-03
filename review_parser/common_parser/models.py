from django.db import models
from django.utils import timezone
from django.conf import settings


class Organization(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    inn = models.CharField(max_length=12, null=False, blank=False, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization',
    )
    
    def __str__(self):
        return self.name or f'Организация #{self.pk}'


class Branch(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches"
    )
    city = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'address'],
                name='unique_organization_address'
            )
        ]

    def __str__(self):
        return f'{self.pk} : {self.organization}: {self.address[:50]}'


class BranchProvider(models.Model):
    PROVIDER_CHOICES = (
        ('2gis', '2GIS'),
        ('vlru', 'VL.RU'),
        ('yandex', 'Yandex'),
        ('google', 'Google')
    )
    branch = models.ForeignKey(
        Branch,
        on_delete = models.CASCADE,
        related_name='branch_providers'
    )
    provider = models.CharField(
        max_length=30,
        choices=PROVIDER_CHOICES
    )
    source_url = models.URLField(max_length=1500)
    external_place_id = models.CharField(
        max_length=255,
        null=True, 
        blank=True,
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    last_parse_date = models.DateTimeField(
        null=True, 
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['branch', 'provider', 'source_url'],
                name='unique_branch_provider_source_url'
            )
        ]

    def mark_as_parsed(self) -> None:
        self.last_parse_date = timezone.now()
        self.save(update_fields=['last_parse_date'])

    def __str__(self):
        return f'{self.branch.pk} : {self.provider}: {self.source_url}'


class ProviderStat(models.Model):
    provider = models.OneToOneField(
        BranchProvider,
        on_delete=models.CASCADE,
        related_name='stats'
    )
    external_rating_avg = models.FloatField(
        null=True, 
        blank=True
    )
    last_parse_date = models.DateTimeField(
        null=True, 
        blank=True
    )

    def __str__(self):
        return f'Stat for {self.provider}'


class Review(models.Model):
    provider = models.ForeignKey(
        BranchProvider,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    author_name = models.CharField(max_length=255)
    author_avatar_url = models.URLField(null=True, blank=True)
    rating = models.FloatField(
        null=True, 
        blank=True
    )
    text = models.TextField()
    review_url = models.URLField(
        max_length=1500,
        null=True, 
        blank=True
    )
    published_date = models.DateTimeField(
        null=True, 
        blank=True
    )
    external_review_id = models.CharField(
        max_length=255,
        null=True, 
        blank=True,
        db_index=True
    )
    content_hash = models.CharField(
        max_length=64,
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'external_review_id'],
                condition=models.Q(external_review_id__isnull=False),
                name='unique_provider_external_review_id_not_null'
            ),
            models.UniqueConstraint(
                fields=['provider', 'content_hash'],
                name = 'unique_provider_content_hash'
            )
        ]

    def __str__(self):
        return f'{self.pk}: {self.author_name}'
    

class ReviewMedia(models.Model):
    MEDIA_TYPE_CHOICES = (
        ('photo', 'Фото'),
        ('video', 'Видео'),
        ('other', 'Другое')
    )

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='media'
    )
    media_type = models.CharField(
        max_length=50,
        choices=MEDIA_TYPE_CHOICES
    )
    url = models.URLField(max_length=1500)

    def __str__(self):
        return f'{self.review.pk}: {self.media_type}: {self.url}'


class Playlist(models.Model):
    PROVIDER_CHOICES = [
        ('youtube', 'Ютуб'),
        ('vk', 'Вк'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="playlists"
    )    
    title = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES
    )
    source_url = models.URLField(max_length=1500)
    external_playlist_id = models.CharField(
        max_length=255,
        null=True, 
        blank=True,
        db_index=True
    )
    last_parse_time = models.DateTimeField(
        null=True, 
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'source_url'],
                name='unique_organization_source_url'
            )
        ]

    def __str__(self):
        return f'{self.pk}: {self.title}'


class Video(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    external_id = models.CharField(
        max_length=255,
        null=True, 
        blank=True,
        db_index=True
    )
    url = models.URLField(max_length=1500)
    title = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    author = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True
    )
    preview_url = models.URLField(
        max_length=1000,
        null=True,
        blank=True
    )
    published_date = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['playlist', 'external_id'],
                condition=models.Q(external_id__isnull=False),
                name='unique_playlist_external_id_not_null'
            ),
            models.UniqueConstraint(
                fields=['playlist', 'url'],
                name='unique_playlist_url'
            )
        ]

    def __str__(self):
        return f'{self.pk}: {self.title}'

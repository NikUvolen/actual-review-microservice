from django.contrib import admin
from nested_admin import (
    NestedModelAdmin, # type: ignore
    NestedStackedInline, # type: ignore
    NestedTabularInline, # type: ignore
)
from common_parser.models import (
    Organization, 
    Branch,
    BranchProvider,
    ProviderStat, 
    Review,
    ReviewMedia,
    Playlist, 
    Video,
)


class BranchInline(NestedStackedInline):
    model = Branch
    extra = 0 
    show_change_link = True 


@admin.register(Branch)
class BranchAdmin(NestedModelAdmin):
    list_display = (
        'id', 
        'organization', 
        'city',
        'address'
    )
    list_filter = (
        'organization',
        'city'
    )
    search_fields = (
        'address',
        'organization__name',
        'organization__inn'
    )


@admin.register(BranchProvider)
class BranchProviderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'branch',
        'provider',
        'source_url',
        'external_place_id'
    )
    list_filter = (
        'provider',
    )
    search_fields = (
        'source_url',
        'external_place_id',
        'branch__address',
    )


@admin.register(ProviderStat)
class ProviderStatAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'provider',
        'external_rating_avg',
        'last_parse_date'
    )
    list_filter = (
        'last_parse_date',
    )


@admin.register(Organization)
class OrganizationAdmin(NestedModelAdmin):
    list_display = ('id', 'name', 'inn')  
    search_fields = ['name']        
    ordering = ['id']
    inlines = [BranchInline] 


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'provider', 
        'author_name', 
        'rating', 
        'published_date'
    )
    list_filter = (
        'provider__provider',
        'rating'
    )
    search_fields = (
        'author_name',
        'text',
        'external_review_id',
        'provider__source_url',
        'provider__branch__address',
    )
    date_hierarchy = 'published_date'
    ordering = ['-published_date']


@admin.register(ReviewMedia)
class ReviewMediaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'review',
        'media_type',
        'url'
    )
    list_filter = (
        'media_type',
    )
    search_fields = ('url',)


class VideoInline(NestedTabularInline):
    model = Video
    extra = 0
    show_change_link = True


@admin.register(Playlist)
class PlaylistAdmin(NestedModelAdmin):
    list_display = (
        'id',
        'organization',
        'title',
        'provider',
        'last_parse_time'
    )
    list_filter = (
        'organization',
        'provider',
    )
    search_fields = (
        'title',
        'source_url',
        'external_playlist_id',
    )
    inlines = [VideoInline]


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'playlist',
        'title',
        'author',
        'duration_seconds',
        'published_date'
    )
    list_filter = (
        'playlist__provider',
        'published_date'
    )
    search_fields = (
        'title',
        'author',
        'url',
        'external_id',
    )
    ordering = ['-published_date']
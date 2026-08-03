import logging

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
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
from common_parser.services.parsing_orchestrator import ParsingOrchestrator


logger = logging.getLogger(__name__)


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
        'address',
        'is_active',
    )
    list_filter = (
        'organization',
        'city',
        'is_active',
    )
    search_fields = (
        'address',
        'organization__name',
        'organization__inn'
    )


@admin.register(BranchProvider)
class BranchProviderAdmin(admin.ModelAdmin):
    change_form_template = 'admin/common_parser/branchprovider/change_form.html'

    list_display = (
        'id',
        'branch',
        'provider',
        'source_url',
        'external_place_id',
        'is_active',
    )
    list_filter = (
        'provider',
        'is_active',
    )
    search_fields = (
        'source_url',
        'external_place_id',
        'branch__address',
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/parse-sync/',
                self.admin_site.admin_view(self.parse_sync_view),
                name='common_parser_branchprovider_parse_sync',
            ),
        ]
        return custom_urls + urls

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = '',
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        context = {'show_sync_parse_button': settings.DEBUG}
        if extra_context:
            context.update(extra_context)

        return super().changeform_view(
            request,
            object_id,
            form_url,
            extra_context=context,
        )

    def parse_sync_view(
        self,
        request: HttpRequest,
        object_id: str,
    ) -> HttpResponse:
        if not settings.DEBUG:
            raise PermissionDenied(
                'Synchronous parsing is available only in debug mode.'
            )
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])

        branch_provider = get_object_or_404(BranchProvider, pk=object_id)

        try:
            result = ParsingOrchestrator().parse_branch_provider_sync(
                branch_provider.pk
            )
        except Exception:
            logger.exception(
                'Synchronous admin parsing failed: branch_provider_id=%s',
                branch_provider.pk,
            )
            self.message_user(
                request,
                'Парсинг завершился с ошибкой. Подробности доступны в логах.',
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                (
                    f'Парсинг завершён: обработано {result.parsed_count}, '
                    f'создано {result.created_count}, пропущено {result.skipped_count}.'
                ),
                level=messages.SUCCESS,
            )

        return redirect(
            reverse(
                'admin:common_parser_branchprovider_change',
                args=[branch_provider.pk],
            )
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
    list_display = ('id', 'name', 'inn', 'user')
    search_fields = ['name', 'inn', 'user__username', 'user__email']
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

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .yasg import urlpatterns as doc_urls


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('common_parser.urls')),

    path(
        'api/auth/token/',
        TokenObtainPairView.as_view(),
        name='token_obtain_pair'
    ),
    path(
        'api/auth/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh'
    ),
] + doc_urls

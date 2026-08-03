from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .yasg import urlpatterns as doc_urls
from common_parser.webhooks import webhook



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/yandex/', include('yandex_parser.urls')),
    path('api/twogis/', include('twogis_parser.urls')),
    path('api/vlru/', include('vl_parser.urls')),
    path('api/common/', include('common_parser.urls')),
    path('api/test/webhook', webhook),

    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
] + doc_urls

from django.urls import path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Review Parser API",
      default_version='v1',
      description="""
API для управления организациями, филиалами и источниками отзывов, запуска
парсинга и получения сохраненных отзывов.

**Основные эндпоинты:**
- `POST /api/auth/token/` — получить access и refresh JWT
- `POST /api/auth/token/refresh/` — обновить access JWT
- `GET/PATCH /api/v1/organization/` — получить или изменить свою организацию
- `GET/POST /api/v1/branches/` — список и создание филиалов
- `GET/PUT/PATCH/DELETE /api/v1/branches/{id}/` — управление филиалом
- `GET/POST /api/v1/branches/{id}/providers/` — источники отзывов филиала
- `GET/PUT/PATCH/DELETE /api/v1/branch-providers/{id}/` — управление источником
- `POST /api/v1/branch_providers/{id}/parse/` — запустить парсинг через Celery
- `GET /api/v1/parsing-tasks/{task_id}/` — получить статус фоновой задачи
- `GET /api/v1/branches/{id}/reviews/` — отзывы филиала
- `GET /api/v1/branch_providers/{id}/reviews/` — отзывы одного источника

Все прикладные эндпоинты требуют JWT. В Swagger нажмите **Authorize** и введите
`Bearer <access_token>`.

**Работающие провайдеры отзывов:** `2gis`, `vlru`, `yandex`.
""",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
   path(
      'swagger.<str:format>',
      schema_view.without_ui(cache_timeout=0),
      name='schema-json',
   ),
   path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

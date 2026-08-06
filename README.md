# Actual Review Microservice

Django-сервис для сбора отзывов о филиалах организаций из внешних источников,
нормализации данных и предоставления их через REST API.

Рабочий pipeline:

```text
BranchProvider
 -> ReviewParsingService
 -> provider parser
 -> ReviewIngestionService
 -> Review / ReviewMedia / ProviderStat
```

## Текущий статус

Реализовано:

- нормализованные модели организаций, филиалов, источников, отзывов и медиа;
- единый интерфейс review-парсеров через `BaseReviewParser`;
- парсеры `2GIS`, `VL.ru` и `Yandex Maps`;
- нормализация внешних данных в `ParsedReview` и `ParseResult`;
- сохранение отзывов через `ReviewIngestionService`;
- дедупликация по внешнему ID или хешу содержимого;
- ограничение количества отзывов на один `BranchProvider`;
- синхронный и асинхронный запуск через `ParsingOrchestrator`;
- фоновые задачи Celery с retry для временных ошибок провайдеров;
- расписание Celery Beat по вторникам и субботам в 06:00;
- JWT-аутентификация и изоляция данных по организации пользователя;
- CRUD для филиалов и их источников;
- API запуска парсинга, проверки статуса задачи и получения отзывов;
- фильтрация отзывов по провайдеру и диапазону дат;
- пагинация списка отзывов;
- Swagger и ReDoc;
- тесты клиентов, парсеров, ingestion, application services, Celery и API.

Пока не реализовано:

- Google Maps, YouTube и VK Video;
- история запусков парсинга `ParseRun`;
- production-конфигурация Docker, Gunicorn и Nginx;
- регистрация клиентов через публичный API.

## Стек

- Python `3.12`
- Django `5.2`
- Django REST Framework
- Simple JWT
- Celery и Celery Beat
- Redis
- PostgreSQL
- django-celery-results
- BeautifulSoup
- drf-yasg
- pytest / pytest-django
- uv

## Модели

### Organization

Организация-клиент. Связана с пользователем отношением `OneToOne`.

Основные поля:

- `user`
- `name`
- `inn`

### Branch

Филиал организации:

- `organization`
- `city`
- `address`
- `is_active`

Пара `organization + address` уникальна. Удаление через API является мягким:
филиал и его источники переводятся в неактивное состояние.

### BranchProvider

Источник отзывов конкретного филиала:

- `branch`
- `provider`
- `source_url`
- `external_place_id`
- `is_active`
- `last_parse_date`

Пара `branch + provider + source_url` уникальна. Реально поддерживаются `2gis`,
`vlru` и `yandex`.

### ProviderStat

Статистика внешнего источника:

- `provider`
- `external_rating_avg`
- `last_parse_date`

### Review

Нормализованный отзыв:

- `provider`
- `author_name`
- `author_avatar_url`
- `rating`
- `text`
- `review_url`
- `published_date`
- `external_review_id`
- `content_hash`

Уникальность контролируется ограничениями:

```text
provider + external_review_id
provider + content_hash
```

### ReviewMedia

Медиа отзыва:

- `review`
- `media_type`
- `url`

### Playlist и Video

Модели подготовлены для будущей поддержки YouTube и VK Video, но parser pipeline
и публичный API для них пока не реализованы.

## Структура

```text
review_parser/
  manage.py

  review_parser/
    settings.py
    urls.py
    celery.py
    yasg.py

  common_parser/
    models.py
    admin.py
    tasks.py
    urls.py

    parsing/
      dto.py
      exceptions.py
      ingestion.py
      limits.py

      clients/
        twogis.py
        vlru.py
        yandex.py

      providers/
        base.py
        twogis.py
        vlru.py
        yandex.py

    services/
      http_client.py
      parsing_orchestrator.py
      review_parsing.py

    serializers/
      organizations.py
      branches.py
      reviews.py
      parsing_tasks.py
      videos.py

    views/
      crud.py
      review_parsing.py

    tests/
```

## Review pipeline

### 1. BranchProvider

Для филиала создается источник:

```text
branch = филиал организации
provider = 2gis
source_url = https://2gis.ru/irkutsk/firm/1549095919422612
```

### 2. ReviewParsingService

`ReviewParsingService` выбирает parser по коду провайдера:

```python
{
    "2gis": TwoGisParser,
    "vlru": VlRuParser,
    "yandex": YandexParser,
}
```

### 3. Parser

Каждый parser реализует `BaseReviewParser` и возвращает единый DTO:

```python
ParseResult(
    provider="2gis",
    source_url="...",
    external_count=160,
    avg_rating=4.4,
    reviews=[ParsedReview(...)],
)
```

### 4. ReviewIngestionService

Ingestion service:

- обновляет `ProviderStat`;
- выбирает последние отзывы в пределах лимита;
- проверяет дубли;
- создает `Review` и `ReviewMedia`;
- удаляет отзывы сверх лимита для данного `BranchProvider`;
- возвращает `parsed_count`, `created_count`, `skipped_count`.

Лимиты:

```text
2gis   100
vlru   100
yandex 600
```

### 5. Celery и оркестратор

`ParsingOrchestrator` запускает один источник, все источники филиала или все
активные источники. Фоновый task:

```python
parse_branch_reviews_async(branch_provider_id)
```

Пример результата:

```json
{
  "branch_provider_id": 1,
  "branch_id": 1,
  "provider": "2gis",
  "parsed": 100,
  "created": 10,
  "skipped": 90,
  "duration_ms": 3014
}
```

Celery Beat дважды в неделю запускает задачу
`enqueue_scheduled_branch_provider_parsing`, которая ставит в очередь все
активные источники активных филиалов.

## Переменные окружения

Минимальная локальная конфигурация:

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=parser_microservice
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

CELERY_BROKER_URL=redis://localhost:6379/0
```

При запуске внутри Docker Compose брокер обычно доступен как:

```env
CELERY_BROKER_URL=redis://redis:6379/0
```

## Локальный запуск

Установить зависимости:

```bash
uv sync
```

Проверить конфигурацию и применить миграции:

```bash
uv run python review_parser/manage.py check
uv run python review_parser/manage.py migrate
```

Запустить API:

```bash
uv run python review_parser/manage.py runserver
```

Запустить worker и beat в отдельных терминалах:

```bash
uv run celery -A review_parser worker -l info --pool=solo --concurrency=1
uv run celery -A review_parser beat -l info
```

На macOS для локальной разработки используется `--pool=solo`, чтобы избежать
проблем `fork` с worker-процессами.

## Проверка через Django shell

```python
from django.contrib.auth import get_user_model

from common_parser.models import Organization, Branch, BranchProvider
from common_parser.services.review_parsing import ReviewParsingService

User = get_user_model()
user = User.objects.create_user(
    username="test-owner",
    password="test-password",
)
organization = Organization.objects.create(
    user=user,
    name="Test company",
    inn="123456789012",
)
branch = Branch.objects.create(
    organization=organization,
    city="Иркутск",
    address="Тестовый адрес",
)
provider = BranchProvider.objects.create(
    branch=branch,
    provider="2gis",
    source_url="https://2gis.ru/irkutsk/firm/1549095919422612",
)

result = ReviewParsingService().parse_and_save_provider_reviews(provider)
result.parsed_count
result.created_count
result.skipped_count
```

Фоновый запуск:

```python
from common_parser.tasks import parse_branch_reviews_async

task = parse_branch_reviews_async.delay(provider.pk)
task.id
```

## API и JWT

Получить токены:

```http
POST /api/auth/token/
Content-Type: application/json

{
  "username": "test-owner",
  "password": "test-password"
}
```

При обращении к API передается access token:

```http
Authorization: Bearer <access_token>
```

Основные endpoints:

| Метод | URL | Назначение |
|---|---|---|
| `POST` | `/api/auth/token/` | Получить access и refresh token |
| `POST` | `/api/auth/token/refresh/` | Обновить access token |
| `GET`, `PATCH` | `/api/v1/organization/` | Своя организация |
| `GET`, `POST` | `/api/v1/branches/` | Список и создание филиалов |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/branches/{id}/` | Управление филиалом |
| `GET`, `POST` | `/api/v1/branches/{id}/providers/` | Источники филиала |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/branch-providers/{id}/` | Управление источником |
| `POST` | `/api/v1/branch_providers/{id}/parse/` | Запустить парсинг |
| `GET` | `/api/v1/parsing-tasks/{task_id}/` | Статус Celery task |
| `GET` | `/api/v1/branches/{id}/reviews/` | Отзывы филиала |
| `GET` | `/api/v1/branch_providers/{id}/reviews/` | Отзывы источника |

Отзывы филиала поддерживают параметры:

```text
provider=2gis
date_from=2026-07-01
date_to=2026-07-31
ordering=-published_date
page=1
page_size=20
```

Доступные варианты `ordering`: `-published_date`, `published_date`, `-rating`
и `rating`. Значения `NULL` помещаются в конец выдачи.

Для чередования отзывов разных провайдеров используются:

```text
mode=interleave
interleave_size=2
provider_order=vlru,2gis
```

`interleave_size` задает количество последовательных отзывов одного провайдера
и принимает значения от `1` до `100`. Переданные через `provider_order`
подключенные провайдеры идут первыми; остальные добавляются в стандартном
порядке `2gis, yandex, google, vlru`. Известные, но не подключенные к филиалу
провайдеры игнорируются. Неизвестные коды и дубли возвращают `400`.

Максимальный `page_size` равен `100`. Чередование доступно только для endpoint
отзывов филиала; endpoint одного источника поддерживает обычную сортировку.

Пользователь получает доступ только к организации, филиалам, источникам и
отзывам, связанным с его учетной записью. Чужие объекты возвращают `404`.

## Swagger

- Swagger UI: `http://127.0.0.1:8000/swagger/`
- ReDoc: `http://127.0.0.1:8000/redoc/`
- OpenAPI JSON: `http://127.0.0.1:8000/swagger.json`
- OpenAPI YAML: `http://127.0.0.1:8000/swagger.yaml`

Для авторизации в Swagger нажмите **Authorize** и введите:

```text
Bearer <access_token>
```

## Тесты

Запустить весь набор:

```bash
uv run pytest
```

Проверить отсутствие незаписанных изменений моделей:

```bash
uv run python review_parser/manage.py makemigrations --check --dry-run
```

## Production-деплой через Docker Compose

Production-контур состоит из следующих контейнеров:

- `nginx` принимает HTTP-запросы на порту `80` и отдаёт статику;
- `web` запускает Django через Gunicorn, применяет миграции и собирает статику;
- `celery` обрабатывает фоновые задачи с `concurrency=1`;
- `celery_beat` ставит периодические задачи в очередь;
- `db` хранит данные в PostgreSQL;
- `redis` используется как брокер Celery.

На сервере установить Git и Docker с Compose plugin, затем клонировать проект:

```bash
git clone <repository-url> actual-review-microservice
cd actual-review-microservice
```

Создать production-конфигурацию:

```bash
cp .env_example .env
openssl rand -hex 32
```

Результат `openssl` записать в `DJANGO_SECRET_KEY`. В `.env` также необходимо:

- заменить `SERVER_IP` на реальный IP сервера;
- задать отдельный надёжный `DB_PASSWORD`;
- указать рабочий `TWOGIS_API_KEY`;
- оставить `DJANGO_DEBUG=False`;
- использовать `DB_HOST=db` и `CELERY_BROKER_URL=redis://redis:6379/0`.

Собрать и запустить сервис:

```bash
docker compose up -d --build
docker compose ps
```

Создать администратора:

```bash
docker compose exec web python manage.py createsuperuser
```

Просмотреть логи:

```bash
docker compose logs -f web celery celery_beat nginx
```

После запуска доступны:

- `http://SERVER_IP/admin/`;
- `http://SERVER_IP/swagger/`;
- `http://SERVER_IP/api/v1/`.

При обновлении приложения:

```bash
git pull
docker compose up -d --build
```

PostgreSQL, Redis, статика, расписание Celery Beat и логи находятся в Docker
volumes и сохраняются при пересоздании контейнеров. Команда
`docker compose down -v` удаляет эти данные и не должна использоваться при
обычном обновлении.

## Дедупликация

Дедупликация выполняется отдельно внутри каждого `BranchProvider`.

Если провайдер возвращает стабильный внешний ID, проверяется:

```text
provider + external_review_id
```

Если ID отсутствует, вычисляется SHA-256 `content_hash` из нормализованных полей
отзыва. Ограничения уникальности в базе дополнительно защищают от конкурентного
создания дублей.

Дедупликация одинаковых отзывов между разными площадками не выполняется.

## Ограничения

- endpoint статуса Celery показывает текущее состояние и результат, но отдельной
  модели истории запусков `ParseRun` пока нет;
- внутренние API внешних провайдеров могут измениться и потребовать обновления
  clients/parsers;
- Google Maps, YouTube и VK Video пока не подключены к рабочему pipeline;
- HTTPS пока не настроен: после подключения домена необходимо выпустить TLS
  сертификат и включить secure cookie/redirect параметры в `.env`.

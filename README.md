# Actual Review Microservice

Учебный Django-сервис для сбора отзывов о филиалах компаний из внешних источников и сохранения их в нормализованную базу данных.

Сейчас основной рабочий pipeline построен вокруг отзывов из `2GIS` и `VL.ru`:

```text
BranchProvider
 -> ReviewParsingService
 -> provider parser
 -> ReviewIngestionService
 -> Review / ReviewMedia / ProviderStat
```

## Текущий статус

Реализовано:

- нормализованные модели для организаций, филиалов, провайдеров отзывов, отзывов, медиа, плейлистов и видео;
- единый интерфейс review-парсеров через `BaseReviewParser`;
- DTO для результата парсинга: `ParsedReview`, `ParseResult`;
- парсер `2GIS`;
- парсер `VL.ru`;
- кастомные ошибки парсеров;
- сервис сохранения результатов парсинга в БД;
- дедупликация отзывов внутри одного `BranchProvider`;
- Celery task для фонового запуска парсинга одного `BranchProvider`;
- тесты для клиентов, парсеров, ingestion-сервиса, application-сервиса и Celery task.

В разработке:

- API под новую нормализованную БД;
- сериализаторы под новые модели;
- orchestration layer для управления сценариями запуска;
- история запусков парсинга;
- расписание парсинга через Celery Beat;
- инкрементальный парсинг;
- JWT-доступы;
- новые провайдеры: Yandex Maps, Google, YouTube, VK Video.

В проекте еще есть legacy-код старой реализации. Часть старых `views`, `tools` и `tasks` временно отключена или не используется новым pipeline.

## Стек

- Python `3.12`
- Django `5.2`
- Django REST Framework
- Celery
- Redis
- PostgreSQL
- django-celery-results
- BeautifulSoup
- pytest / pytest-django
- uv

## Основные модели

### Organization

Компания-клиент.

Основные поля:

- `name`
- `inn`

### Branch

Филиал организации.

Основные поля:

- `organization`
- `city`
- `address`

Ограничение уникальности:

```text
organization + address
```

### BranchProvider

Источник отзывов для конкретного филиала.

Например, один филиал может иметь несколько источников:

- `2GIS`
- `VL.ru`
- `Yandex Maps`
- `Google`

Основные поля:

- `branch`
- `provider`
- `source_url`
- `external_place_id`

Ограничение уникальности:

```text
branch + provider + source_url
```

### ProviderStat

Агрегированная статистика по источнику отзывов.

Основные поля:

- `provider`
- `external_rating_avg`
- `last_parse_date`

### Review

Нормализованный отзыв.

Основные поля:

- `provider`
- `author_name`
- `author_avatar_url`
- `rating`
- `text`
- `review_url`
- `published_date`
- `external_review_id`
- `content_hash`

Дедупликация:

```text
provider + external_review_id
provider + content_hash
```

### ReviewMedia

Медиа, прикрепленные к отзыву.

Основные поля:

- `review`
- `media_type`
- `url`

### Playlist

Плейлист организации на видеохостинге.

Основные поля:

- `organization`
- `title`
- `provider`
- `source_url`
- `external_playlist_id`
- `last_parse_time`

### Video

Видео из плейлиста.

Основные поля:

- `playlist`
- `external_id`
- `url`
- `title`
- `author`
- `duration_seconds`
- `preview_url`
- `published_date`

## Структура важной части проекта

```text
review_parser/
  manage.py

  review_parser/
    settings.py
    urls.py
    celery.py

  common_parser/
    models.py
    admin.py
    tasks.py
    serializers.py
    views.py
    urls.py

    services/
      review_parsing.py

    parsing/
      dto.py
      exceptions.py
      ingestion.py

      clients/
        twogis.py
        vlru.py

      providers/
        base.py
        twogis.py
        vlru.py

    tests/
      test_twogis_client.py
      test_vlru_client.py
      test_twogis_parser.py
      test_vlru_parser.py
      test_review_parsers.py
      test_review_ingestion.py
      test_review_parsing_service.py
      test_review_parsing_tasks.py
```

## Как работает новый review pipeline

### 1. BranchProvider

В базе создается `BranchProvider`.

Пример:

```text
branch = филиал компании
provider = 2gis
source_url = https://2gis.ru/irkutsk/firm/1549095919422612
```

### 2. ReviewParsingService

`ReviewParsingService` получает `BranchProvider`, выбирает нужный parser по полю `provider` и запускает парсинг.

Поддерживаемые parser classes сейчас:

```python
{
    "2gis": TwoGisParser,
    "vlru": VlRuParser,
}
```

### 3. Parser

Parser приводит внешний ответ к единому формату:

```python
ParseResult(
    provider="2gis",
    source_url="...",
    external_count=160,
    avg_rating=4.4,
    reviews=[ParsedReview(...)]
)
```

### 4. ReviewIngestionService

`ReviewIngestionService` сохраняет результат парсинга:

- обновляет `ProviderStat`;
- проверяет дубли;
- создает `Review`;
- создает связанные `ReviewMedia`;
- возвращает счетчики `parsed_count`, `created_count`, `skipped_count`.

### 5. Celery task

Фоновый запуск выполняется через task:

```python
parse_branch_reviews_async(branch_provider_id)
```

Task возвращает:

```json
{
  "branch_provider_id": 1,
  "branch_id": 1,
  "provider": "2gis",
  "parsed": 156,
  "created": 156,
  "skipped": 0,
  "duration_ms": 3014
}
```

## Переменные окружения

Минимально для локального запуска:

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=parser_microservice
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

YOUTUBE_API_KEY=dummy
```

По умолчанию Celery настроен на Redis:

```text
redis://redis:6379/0
```

Для локального запуска worker вне Docker обычно нужно переопределить broker:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
```

Сейчас в `settings.py` broker задан константой, поэтому при локальном запуске Redis должен быть доступен как `redis`, либо настройку нужно временно заменить на `localhost`.

## Установка через uv

```bash
uv sync
```

Проверить Django:

```bash
uv run python review_parser/manage.py check
```

Применить миграции:

```bash
uv run python review_parser/manage.py migrate
```

Запустить shell:

```bash
uv run python review_parser/manage.py shell
```

Запустить dev server:

```bash
uv run python review_parser/manage.py runserver
```

## Запуск Celery

Worker:

```bash
uv run celery -A review_parser worker -l info --pool=solo --concurrency=1
```

Beat:

```bash
uv run celery -A review_parser beat -l info
```

На macOS для локальной разработки лучше использовать:

```bash
--pool=solo
```

Это снижает риск падения worker из-за multiprocessing.

## Запуск через Docker Compose

```bash
docker compose up --build
```

Сервисы:

- `web`
- `redis`
- `celery`
- `celery_beat`

## Быстрая проверка парсинга в Django shell

```python
from common_parser.models import Organization, Branch, BranchProvider
from common_parser.services.review_parsing import ReviewParsingService

organization = Organization.objects.create(
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

Проверить сохраненные отзывы:

```python
from common_parser.models import Review, ProviderStat

Review.objects.filter(provider=provider).count()
ProviderStat.objects.get(provider=provider).external_rating_avg
```

## Запуск Celery task из shell

```python
from common_parser.tasks import parse_branch_reviews_async

task = parse_branch_reviews_async.delay(provider.id)
task.id
```

Проверить результат:

```python
from celery.result import AsyncResult

result = AsyncResult(task.id)
result.status
result.result
```

## Тесты

Запустить основные тесты нового pipeline:

```bash
uv run pytest \
  review_parser/common_parser/tests/test_review_parsers.py \
  review_parser/common_parser/tests/test_review_parsing_service.py \
  review_parser/common_parser/tests/test_review_ingestion.py \
  review_parser/common_parser/tests/test_review_parsing_tasks.py
```

Запустить все тесты:

```bash
uv run pytest
```

## Дедупликация

Сейчас дедупликация работает внутри одного `BranchProvider`.

Если внешний провайдер отдает стабильный id отзыва, используется:

```text
provider + external_review_id
```

Если внешнего id нет, используется `content_hash`.

Хеш строится из нормализованных данных отзыва:

```text
author_name
rating
published_date
text
review_url
```

Это защищает от повторного сохранения тех же отзывов при повторном парсинге одного и того же источника.

Дедупликация между разными провайдерами пока не реализована. Ее лучше делать отдельной research-задачей, потому что похожие отзывы с разных площадок не всегда являются дублями.

## Swagger

Swagger подключен через `drf-yasg`.

URL задаются в:

```text
review_parser/review_parser/yasg.py
```

Основные URL проекта:

```text
/admin/
/api/common/
/api/yandex/
/api/twogis/
/api/vlru/
```

Новый API под нормализованную БД еще находится в разработке.

## Ограничения текущей реализации

- `common_parser/serializers.py` еще частично описывает старые поля и требует адаптации под новые модели.
- `common_parser/views.py` сейчас содержит закомментированный legacy API.
- В `common_parser/tasks.py` есть старые задачи, которые зависят от удаленных полей старой модели `Branch`.
- Celery Beat пока содержит старую weekly-задачу.
- Нет модели истории запусков `ParseRun`.
- Нет полноценного orchestration layer.
- Нет JWT-доступов и ограничения данных по организации пользователя.
- Нет production-ready Docker/Nginx-конфигурации.


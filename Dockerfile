FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN useradd --create-home --uid 1000 app

COPY --chown=app:app review_parser ./review_parser
COPY --chown=app:app docker ./docker

RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/logs /app/review_parser/staticfiles /var/lib/celery \
    && chown -R app:app /app/logs /app/review_parser/staticfiles /var/lib/celery

WORKDIR /app/review_parser

USER app

EXPOSE 8000

CMD ["/app/docker/entrypoint.sh"]

# syntax=docker/dockerfile:1
# Hrček: one process, one SQLite file in /data. See docs/dev/deployment.md.

FROM ghcr.io/astral-sh/uv:0.12.18 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY manage.py ./
COPY src ./src
COPY locale ./locale
COPY docker ./docker
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Production settings demand these; only collectstatic sees the values.
RUN HRCEK_SECRET_KEY=collectstatic HRCEK_ALLOWED_HOSTS=localhost \
    HRCEK_SMTP_HOST=localhost DJANGO_SETTINGS_MODULE=hrcek.settings.prod \
    /app/.venv/bin/python manage.py collectstatic --no-input

FROM python:3.13-slim
ARG HRCEK_RELEASE=dev
RUN groupadd --system --gid 10001 hrcek \
    && useradd --system --uid 10001 --gid hrcek --no-create-home hrcek \
    && mkdir /data && chown hrcek:hrcek /data
COPY --from=build /app /app
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=hrcek.settings.prod \
    HRCEK_DB_PATH=/data/db.sqlite3 \
    HRCEK_MEDIA_PATH=/data/media \
    HRCEK_RELEASE=$HRCEK_RELEASE
USER hrcek
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --start-interval=2s \
    --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status != 200)"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["serve"]

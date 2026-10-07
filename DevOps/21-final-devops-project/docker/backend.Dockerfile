# syntax=docker/dockerfile:1
# TicketHub API — build context: application/backend
# docker build -f docker/backend.Dockerfile -t tickethub-backend:local application/backend

# ---- stage 1: build a virtualenv with all runtime dependencies
FROM python:3.13-alpine AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install -r requirements.txt \
    # pip itself is not needed at runtime and its vendored libs (urllib3, msgpack ...) carry CVEs
    && /venv/bin/pip uninstall -y pip

# ---- stage 2: minimal runtime, no compilers / pip cache
FROM python:3.13-alpine
ARG APP_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/Astro-Dude/devops-assignments" \
      org.opencontainers.image.title="tickethub-backend" \
      org.opencontainers.image.description="TicketHub FastAPI backend (Session 21 capstone)"
ENV PATH="/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_VERSION=${APP_VERSION}
RUN apk upgrade --no-cache && addgroup -S -g 10001 app && adduser -S -D -H -u 10001 -G app app \
    && pip uninstall -y pip setuptools 2>/dev/null || true
WORKDIR /app
COPY --from=build /venv /venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8000/health || exit 1
# Kubernetes runs `python -m app.migrate` in an initContainer; compose runs it via `command:`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

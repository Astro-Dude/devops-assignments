# syntax=docker/dockerfile:1
# Hardened image for hw-devsecops
#   * base image pinned by digest (reproducible, cannot be swapped under us)
#   * multi-stage: build tooling never reaches the runtime image
#   * dependencies installed with --require-hashes (pinned + integrity-checked)
#   * runs as an unprivileged, numeric UID (works with runAsNonRoot in k8s)
#   * no shell form CMD, no secrets, no package caches

ARG PYTHON_IMAGE=python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f

# ---------- stage 1: build a self-contained virtualenv ----------
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --require-hashes --no-deps -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y pip \
 && find /opt/venv -name '__pycache__' -prune -exec rm -rf {} +

# ---------- stage 2: minimal runtime ----------
FROM ${PYTHON_IMAGE} AS runtime
ARG GIT_SHA=local
ARG APP_VERSION=1.0.0
LABEL org.opencontainers.image.source="https://github.com/Astro-Dude/devops-assignments" \
      org.opencontainers.image.description="Session 17 DevSecOps demo app (hw-devsecops)" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="MIT"

# pip/setuptools in the base image are not needed at runtime and are a
# recurring source of image-scan findings, so remove them.
RUN pip uninstall -y pip setuptools wheel 2>/dev/null || true \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION}

WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY --chown=root:root app ./app

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# --worker-tmp-dir /tmp lets the container run with readOnlyRootFilesystem
# (k8s mounts an emptyDir at /tmp).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-tmp-dir", "/tmp", \
     "--access-logfile", "-", "app.main:app"]

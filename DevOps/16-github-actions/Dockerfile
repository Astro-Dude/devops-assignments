# syntax=docker/dockerfile:1

# ---- stage 1: install dependencies into an isolated prefix ----
FROM python:3.13-slim AS deps
WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/pkgs -r requirements.txt

# ---- stage 2: small runtime image, non-root ----
FROM python:3.13-slim
ARG GIT_SHA=dev
LABEL org.opencontainers.image.source="https://github.com/Astro-Dude/devops-assignments" \
      org.opencontainers.image.description="Session 16 CI/CD demo - calculator API" \
      org.opencontainers.image.revision="${GIT_SHA}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_SHA=${GIT_SHA} \
    PORT=8000
COPY --from=deps /install/pkgs /usr/local
WORKDIR /srv
COPY app/ app/
RUN useradd --uid 10001 --create-home appuser
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "app.main:app"]

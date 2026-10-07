# syntax=docker/dockerfile:1
# TicketHub web UI — build context: application/frontend
# docker build -f docker/frontend.Dockerfile -t tickethub-frontend:local application/frontend

# ---- stage 1: Node toolchain builds the static bundle
FROM node:24-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm test && npm run build

# ---- stage 2: unprivileged nginx serves dist/ (runs as uid 101, listens on 8080)
FROM nginxinc/nginx-unprivileged:1.29-alpine
LABEL org.opencontainers.image.source="https://github.com/Astro-Dude/devops-assignments" \
      org.opencontainers.image.title="tickethub-frontend" \
      org.opencontainers.image.description="TicketHub React UI served by nginx (Session 21 capstone)"
USER root
RUN apk upgrade --no-cache
USER 101
# BACKEND_URL is substituted into the template by the nginx image entrypoint (envsubst).
ENV BACKEND_URL=http://backend:8000
COPY --chown=101:101 nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build --chown=101:101 /src/dist /usr/share/nginx/html
EXPOSE 8080

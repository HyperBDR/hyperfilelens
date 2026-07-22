# Gateway image: hyperfilelens-frontend (SPA build + nginx reverse proxy).
# Development targets keep dependencies in the image and bind-mount source.
FROM node:22-alpine AS frontend-dependencies

LABEL org.opencontainers.image.title="hyperfilelens-frontend"

ARG NPM_REGISTRY
ARG SENTRY_ENABLED=false
ARG SENTRY_DSN=
ARG SENTRY_ENVIRONMENT=
ARG SENTRY_RELEASE=
ARG SENTRY_TRACES_SAMPLE_RATE=0
ARG SENTRY_SEND_DEFAULT_PII=false
ARG VITE_SHOW_EULA=false

WORKDIR /app
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN if [ -n "${NPM_REGISTRY}" ]; then npm config set registry "${NPM_REGISTRY}"; fi
RUN npm ci \
 && sha256sum package-lock.json | awk '{print $1}' > node_modules/.hfl-package-lock.sha

FROM frontend-dependencies AS frontend-development

COPY deploy/docker/frontend-dev-entrypoint.sh /usr/local/bin/hfl-frontend-dev
RUN chmod 0755 /usr/local/bin/hfl-frontend-dev

EXPOSE 5173

ENTRYPOINT ["/usr/local/bin/hfl-frontend-dev"]

# Release build stage.
FROM frontend-dependencies AS frontend-build

COPY src/frontend/ ./
ENV SENTRY_ENABLED=${SENTRY_ENABLED} \
    SENTRY_DSN=${SENTRY_DSN} \
    SENTRY_ENVIRONMENT=${SENTRY_ENVIRONMENT} \
    SENTRY_RELEASE=${SENTRY_RELEASE} \
    SENTRY_TRACES_SAMPLE_RATE=${SENTRY_TRACES_SAMPLE_RATE} \
    SENTRY_SEND_DEFAULT_PII=${SENTRY_SEND_DEFAULT_PII} \
    VITE_SHOW_EULA=${VITE_SHOW_EULA}
RUN npm run build

# Stage 2: Serve the SPA and reverse proxy through the official stable Nginx Alpine image.
FROM nginx:stable-alpine

ARG IMAGE_VERSION=dev
ARG IMAGE_REVISION=unknown

LABEL org.opencontainers.image.version="${IMAGE_VERSION}" \
    org.opencontainers.image.revision="${IMAGE_REVISION}"

ENV TZ=UTC \
    LOGROTATE_INTERVAL_SECONDS=3600 \
    LOGROTATE_CONF=/etc/logrotate.d/hyperfilelens \
    LOGROTATE_STATE=/var/log/hyperfilelens/.logrotate.status \
    LOGROTATE_LOCK=/var/log/hyperfilelens/.logrotate.lock

RUN apk add --no-cache logrotate

COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY deploy/nginx/snippets /etc/nginx/snippets
COPY deploy/logrotate/hyperfilelens.conf /etc/logrotate.d/hyperfilelens
COPY deploy/docker/frontend-logrotate-loop.sh /usr/local/bin/logrotate-loop.sh

RUN chmod 0644 /etc/logrotate.d/hyperfilelens \
 && chmod 0755 /usr/local/bin/logrotate-loop.sh \
 && printf '%s\n' '#!/bin/sh' 'exec /usr/local/bin/logrotate-loop.sh --daemon' \
    > /docker-entrypoint.d/99-logrotate-loop.sh \
 && chmod 0755 /docker-entrypoint.d/99-logrotate-loop.sh

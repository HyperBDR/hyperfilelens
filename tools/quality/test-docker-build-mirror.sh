#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/docker-images.sh
source "${ROOT}/tools/lib/docker-images.sh"

hfl_docker_export_build_base_images ""
[[ "${HFL_BACKEND_BASE_IMAGE}" == "ubuntu:24.04" ]]
[[ "${HFL_FRONTEND_NODE_BASE_IMAGE}" == "node:22-alpine" ]]
[[ "${HFL_FRONTEND_NGINX_BASE_IMAGE}" == "nginx:stable-alpine" ]]
[[ "${HFL_WEBSITE_BASE_IMAGE}" == "node:22-alpine" ]]

hfl_docker_export_build_base_images "https://mirror.example.test/"
[[ "${HFL_BACKEND_BASE_IMAGE}" == "mirror.example.test/library/ubuntu:24.04" ]]
[[ "${HFL_FRONTEND_NODE_BASE_IMAGE}" == "mirror.example.test/library/node:22-alpine" ]]
[[ "${HFL_FRONTEND_NGINX_BASE_IMAGE}" == "mirror.example.test/library/nginx:stable-alpine" ]]

grep -F 'ARG BACKEND_BASE_IMAGE=ubuntu:24.04' \
	"${ROOT}/deploy/docker/backend.Dockerfile" >/dev/null
grep -F 'FROM ${BACKEND_BASE_IMAGE} AS backend-dependencies' \
	"${ROOT}/deploy/docker/backend.Dockerfile" >/dev/null
grep -F 'ARG FRONTEND_NODE_BASE_IMAGE=node:22-alpine' \
	"${ROOT}/deploy/docker/frontend.Dockerfile" >/dev/null
grep -F 'FROM ${FRONTEND_NODE_BASE_IMAGE} AS frontend-dependencies' \
	"${ROOT}/deploy/docker/frontend.Dockerfile" >/dev/null
grep -F 'FROM ${FRONTEND_NGINX_BASE_IMAGE}' \
	"${ROOT}/deploy/docker/frontend.Dockerfile" >/dev/null
grep -F 'FROM ${WEBSITE_BASE_IMAGE}' "${ROOT}/website/Dockerfile" >/dev/null
grep -F 'BACKEND_BASE_IMAGE: ${HFL_BACKEND_BASE_IMAGE:-ubuntu:24.04}' \
	"${ROOT}/docker-compose.yml" >/dev/null
grep -F -- '--build-arg "BACKEND_BASE_IMAGE=${HFL_BACKEND_BASE_IMAGE}"' \
	"${ROOT}/release/build.sh" >/dev/null
grep -F -- '--base-image "${HFL_WEBSITE_BASE_IMAGE}"' \
	"${ROOT}/release/build.sh" >/dev/null

printf 'Docker build mirror propagation checks passed.\n'

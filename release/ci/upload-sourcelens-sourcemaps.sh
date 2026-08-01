#!/usr/bin/env bash
# Upload hidden SourceLens UI Source Maps without changing or shipping its source tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../tools/sourcelens/common.sh
source "${ROOT}/tools/sourcelens/common.sh"

release=${1:-}
if [[ -z "${release}" ]]; then
	printf 'Usage: %s RELEASE\n' "$0" >&2
	exit 2
fi
if [[ -z "${SENTRY_AUTH_TOKEN:-}" || -z "${SENTRY_URL:-}" \
	|| -z "${SENTRY_ORG:-}" || -z "${SENTRY_FRONTEND_PROJECT:-}" ]]; then
	printf '::warning title=Sentry Source Maps::Bundled SourceLens Source Map upload is not configured; continuing.\n'
	exit 0
fi

sourcelens_load_config
sourcelens_resolve_version
SOURCELENS_BUILD_SOURCE_MAPS=1
sourcelens_restore_source_dockerfiles "${SOURCELENS_SOURCE_CACHE}"
sourcelens_patch_frontend_dockerfile_npm_registry "${SOURCELENS_SOURCE_CACHE}"
sourcelens_patch_frontend_dockerfile_source_maps "${SOURCELENS_SOURCE_CACHE}"

tmp="$(mktemp -d)"
image="hyperfilelens-sourcelens-symbols:${GITHUB_RUN_ID:-local}"
container=""
cleanup() {
	[[ -z "${container}" ]] || docker rm -f "${container}" >/dev/null 2>&1 || true
	docker image rm "${image}" >/dev/null 2>&1 || true
	rm -rf "${tmp}"
}
trap cleanup EXIT

docker build \
	--platform "${SOURCELENS_DOCKER_PLATFORM}" \
	--target builder \
	--build-arg "NPM_REGISTRY=${SOURCELENS_NPM_REGISTRY}" \
	-t "${image}" \
	"${SOURCELENS_SOURCE_CACHE}/frontend"
container="$(docker create "${image}")"
docker cp "${container}:/app/dist/." "${tmp}/"
find "${tmp}" -type f -name '*.map' -print -quit | grep -q . || {
	printf '::warning title=Sentry Source Maps::No bundled SourceLens Source Maps were produced; continuing.\n'
	exit 0
}

npm ci --prefix "${ROOT}/src/frontend" --ignore-scripts
if ! SENTRY_URL="${SENTRY_URL}" SENTRY_AUTH_TOKEN="${SENTRY_AUTH_TOKEN}" \
	"${ROOT}/src/frontend/node_modules/.bin/sentry-cli" sourcemaps upload \
		--org "${SENTRY_ORG}" \
		--project "${SENTRY_FRONTEND_PROJECT}" \
		--release "${release}" \
		--url-prefix '~/' \
		"${tmp}"; then
	printf '::warning title=Sentry Source Maps::Bundled SourceLens Source Map upload failed; continuing.\n'
	exit 0
fi
printf 'Bundled SourceLens Source Maps uploaded for %s.\n' "${release}"

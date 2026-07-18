#!/usr/bin/env bash
# Fast release workflow contract checks that do not require Docker or network access.
set -euo pipefail
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=../lib/version.sh
source "${ROOT}/tools/lib/version.sh"
actual="$(release_package_basename_for_version v0.1.0 69F809F)"
[[ "${actual}" == "hyperfilelens-0.1.0-69f809f.tar.gz" ]] || {
	printf 'ERROR: unexpected release package basename: %s\n' "${actual}" >&2
	exit 1
}

# shellcheck source=../sourcelens/common.sh
source "${ROOT}/tools/sourcelens/common.sh"
for function_name in \
	sourcelens_build_app_images \
	sourcelens_patch_compose_npm_registry \
	sourcelens_patch_runtime_nginx; do
	declare -F "${function_name}" >/dev/null || {
		printf 'ERROR: missing SourceLens function: %s\n' "${function_name}" >&2
		exit 1
	}
done

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

cat >"${tmp}/docker-compose.yml" <<'YAML'
services:
  frontend:
    build:
      context: ./frontend
      args:
        VITE_GA_ID: ${VITE_GA_ID:-}
    image: example/frontend:latest
YAML
sourcelens_patch_compose_npm_registry "${tmp}"
sourcelens_patch_compose_npm_registry "${tmp}"
[[ "$(grep -c 'NPM_REGISTRY:' "${tmp}/docker-compose.yml")" -eq 1 ]] || {
	printf 'ERROR: SourceLens npm registry Compose patch is not idempotent\n' >&2
	exit 1
}
grep -F 'NPM_REGISTRY: ${NPM_REGISTRY:-}' "${tmp}/docker-compose.yml" >/dev/null

cat >"${tmp}/nginx.conf" <<'NGINX'
ssl_certificate /etc/nginx/certs/nginx-selfsigned.crt;
ssl_certificate_key /etc/nginx/certs/nginx-selfsigned.key;
set $ui_upstream http://frontend:80;
NGINX
sourcelens_patch_runtime_nginx "${tmp}/nginx.conf"
grep -F '/etc/nginx/certs/tls.crt' "${tmp}/nginx.conf" >/dev/null
grep -F '/etc/nginx/certs/tls.key' "${tmp}/nginx.conf" >/dev/null
grep -F 'set $ui_upstream http://ui:80;' "${tmp}/nginx.conf" >/dev/null

grep -F 'archive.extractall(destination, filter="data")' \
	"${ROOT}/src/agent/scripts/package.sh" >/dev/null
grep -F 'chown postgres:postgres /var/lib/postgresql/data' \
	"${ROOT}/deploy/installer/sourcelens/docker-compose.template.yml" >/dev/null
if rg -n 'sourcelens_prepare_source_build_env' \
	"${ROOT}/release" "${ROOT}/dev" "${ROOT}/tools/sourcelens" >/dev/null; then
	printf 'ERROR: obsolete SourceLens prepare helper is still referenced\n' >&2
	exit 1
fi

config="$(${ROOT}/release/build.sh --no-cache --print-config)"
grep -F 'no_cache=1' <<<"${config}" >/dev/null

grep -F -- '--prebuilt' "${ROOT}/release/build-sourcelens.sh" >/dev/null
grep -F 'ln "${source_archive}" "${temporary}"' \
	"${ROOT}/tools/sourcelens/common.sh" >/dev/null
grep -F 'SOURCELENS_GIT_REF="${SOURCELENS_GIT_REF:-v0.4.0}"' \
	"${ROOT}/tools/sourcelens/defaults.env" >/dev/null
grep -F 'set_key("DJANGO_DEBUG", "true")' \
	"${ROOT}/deploy/installer/sourcelens/patch-env-runtime.py" >/dev/null

workflow="${ROOT}/.github/workflows/build_and_deploy.yml"
[[ -f "${workflow}" ]] || {
	printf 'ERROR: tag release workflow is missing\n' >&2
	exit 1
}
if grep -F 'workflow_dispatch:' "${workflow}" >/dev/null; then
	printf 'ERROR: release workflow must not allow manual dispatch\n' >&2
	exit 1
fi
grep -F 'tags:' "${workflow}" >/dev/null
for job in \
	prepare quality build-hfl-images build-sourcelens-images build-agent \
	build-host-debs export-hfl-images export-sourcelens-bundle \
	export-runtime-images assemble-release verify-release publish-release deploy; do
	grep -F "  ${job}:" "${workflow}" >/dev/null || {
		printf 'ERROR: release workflow job is missing: %s\n' "${job}" >&2
		exit 1
	}
done
grep -F "if: \${{ vars.HFL_AUTO_DEPLOY == 'true' }}" "${workflow}" >/dev/null
grep -F "select(.name | startswith(\"_internal-\") | not)" "${workflow}" >/dev/null
grep -F 'uv run python src/backend/manage.py test' "${workflow}" >/dev/null
grep -F 'npm run test:ci' "${workflow}" >/dev/null
grep -F './tools/quality/test-ci-release-assembly.sh' "${workflow}" >/dev/null
if grep -F 'uv run pytest src/backend' "${workflow}" >/dev/null; then
	printf 'ERROR: backend CI must initialize Django through manage.py\n' >&2
	exit 1
fi

remote_deploy="${ROOT}/.github/scripts/remote-deploy.sh"
[[ -x "${remote_deploy}" ]] || {
	printf 'ERROR: remote deployment script is missing or not executable\n' >&2
	exit 1
}
grep -F 'browser_download_url' "${remote_deploy}" >/dev/null
grep -F 'bash "${INSTALL_DIR}/install.sh" upgrade --from "${package_root}" --yes' \
	"${remote_deploy}" >/dev/null
if grep -E 'docker (pull|compose pull)' "${remote_deploy}" >/dev/null; then
	printf 'ERROR: production deployment must consume the complete Release package\n' >&2
	exit 1
fi

installer="${ROOT}/deploy/installer/install.sh"
grep -F 'PUBLIC_HOST="${HFL_PUBLIC_HOST:-}"' "${installer}" >/dev/null
grep -F 'values are hidden in non-interactive logs' "${installer}" >/dev/null
grep -F 'apply_upgrade_files "${src_root}" "${remove_sourcelens}"' "${installer}" >/dev/null
fingerprint_body="$(sed -n '/^sourcelens_bundle_fingerprint()/,/^}/p' "${installer}")"
grep -F 'BUILD_INFO.identity' <<<"${fingerprint_body}" >/dev/null
if grep -F 'upstream_ref' <<<"${fingerprint_body}" >/dev/null; then
	printf 'ERROR: SourceLens fingerprint must ignore per-release registry transit refs\n' >&2
	exit 1
fi

for executable in \
	"${ROOT}/.github/scripts/remote-deploy.sh" \
	"${ROOT}"/release/ci/*.sh \
	"${ROOT}/release/ci/write-sbom.py"; do
	[[ -x "${executable}" ]] || {
		printf 'ERROR: CI entry point is not executable: %s\n' "${executable}" >&2
		exit 1
	}
done

printf 'Release contract checks passed.\n'

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
if grep -R -n 'sourcelens_prepare_source_build_env' \
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
[[ "$(awk '/^  assemble-release:/{job=1} job && /timeout-minutes:/{print $2; exit}' "${workflow}")" == "90" ]] || {
	printf 'ERROR: release assembly timeout must cover large GitHub asset uploads\n' >&2
	exit 1
}
[[ "$(awk '/^  verify-release:/{job=1} job && /timeout-minutes:/{print $2; exit}' "${workflow}")" == "120" ]] || {
	printf 'ERROR: release verification timeout must cover package download and offline install\n' >&2
	exit 1
}
grep -F 'timeout-minutes: 120' "${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'turnstile_enabled: ${{ vars.PROD_TURNSTILE_ENABLED' "${workflow}" >/dev/null
grep -F '"TURNSTILE_ENABLED=$TURNSTILE_ENABLED"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
if git -C "${ROOT}" grep -n 'CAPTCHA_PROVIDER' -- . \
	':!tools/config/sync_env.py' \
	':!tools/quality/check-release-contracts.sh'; then
	printf 'ERROR: CAPTCHA_PROVIDER must not remain in runtime or deployment configuration\n' >&2
	exit 1
fi
grep -F 'Capture failed install diagnostics' "${workflow}" >/dev/null
grep -F 'logs --no-color --tail 200' "${workflow}" >/dev/null
if grep -F 'workflow_dispatch:' "${workflow}" >/dev/null; then
	printf 'ERROR: release workflow must not allow manual dispatch\n' >&2
	exit 1
fi
grep -F 'tags:' "${workflow}" >/dev/null
for job in \
	prepare quality build-hfl-images build-sourcelens-images build-agent \
	build-host-debs export-hfl-images export-sourcelens-bundle \
	export-runtime-images assemble-release verify-release publish-release \
	deploy-preprod deploy-prod; do
	grep -F "  ${job}:" "${workflow}" >/dev/null || {
		printf 'ERROR: release workflow job is missing: %s\n' "${job}" >&2
		exit 1
	}
done
grep -F "if: \${{ vars.PREPROD_DEPLOY_ENABLED == 'true' }}" "${workflow}" >/dev/null
grep -F "vars.PROD_DEPLOY_ENABLED == 'true'" "${workflow}" >/dev/null
grep -F 'repository: hyperfilelens-backend' "${workflow}" >/dev/null
grep -F 'repository: hyperfilelens-frontend' "${workflow}" >/dev/null
grep -F '"$REGISTRY_PREFIX"' "${workflow}" >/dev/null
grep -F "select(.name | startswith(\"_internal-\") | not)" "${workflow}" >/dev/null
grep -F 'gh release delete-asset' "${workflow}" >/dev/null
grep -F -- '--repo "${GITHUB_REPOSITORY}"' "${workflow}" >/dev/null
grep -F "awk '\$2 ~ /^hyperfilelens-.*\\.tar\\.gz\$/" "${workflow}" >/dev/null
grep -F 'uv run python src/backend/manage.py test' "${workflow}" >/dev/null
grep -F 'uv run --isolated --no-project --python 3.8 python tools/quality/check-python38-runtime.py' \
	"${workflow}" >/dev/null
grep -F 'npm run test:ci' "${workflow}" >/dev/null
grep -F './tools/quality/test-ci-release-assembly.sh' "${workflow}" >/dev/null
if grep -F 'uv run pytest src/backend' "${workflow}" >/dev/null; then
	printf 'ERROR: backend CI must initialize Django through manage.py\n' >&2
	exit 1
fi

worker_healthcheck="$(sed -n '/^  worker:/,/^  scheduler:/p' "${ROOT}/deploy/docker-compose.yml")"
grep -F "/proc/1/cmdline" <<<"${worker_healthcheck}" >/dev/null
grep -F "s.connect((pg_host,pg_port))" <<<"${worker_healthcheck}" >/dev/null
grep -F "s.connect(('redis',6379))" <<<"${worker_healthcheck}" >/dev/null
if grep -F 'celery -A common inspect ping' <<<"${worker_healthcheck}" >/dev/null; then
	printf 'ERROR: worker healthcheck must not start another Django/Celery process\n' >&2
	exit 1
fi

backend_dockerfile="${ROOT}/deploy/docker/backend.Dockerfile"
grep -F '/etc/apt/sources.list.d/ubuntu.sources' "${backend_dockerfile}" >/dev/null
grep -F 'uv export --quiet --locked --no-dev --no-emit-project --output-file /tmp/runtime-requirements.txt' \
	"${backend_dockerfile}" >/dev/null
grep -F -- '--require-hashes -r /tmp/runtime-requirements.txt' "${backend_dockerfile}" >/dev/null
if grep -F 'UV_DEFAULT_INDEX' "${backend_dockerfile}" >/dev/null; then
	printf 'ERROR: backend build must not bind the official uv.lock to a download mirror\n' >&2
	exit 1
fi
if grep -F 'PIP_NO_CACHE_DIR' "${backend_dockerfile}" >/dev/null; then
	printf 'ERROR: backend build must not disable its BuildKit-managed pip cache\n' >&2
	exit 1
fi

sourcelens_image_builder="${ROOT}/release/ci/build-sourcelens-image.sh"
grep -F 'target_ref="${registry_prefix}/hyperfilelens-sourcelens-${component}:${hfl_version}-sl${SOURCELENS_VERSION}"' \
	"${sourcelens_image_builder}" >/dev/null
grep -F 'registry prefix must include host and namespace' \
	"${sourcelens_image_builder}" >/dev/null

agent_publisher="${ROOT}/tools/agent/publish.sh"
grep -F 'all | standard | ubuntu2004 | ubuntu2404' "${agent_publisher}" >/dev/null
grep -F 'for ubuntu_flavor in ubuntu2004 ubuntu2404' "${agent_publisher}" >/dev/null
grep -F 'build/dependencies/docker/ubuntu-${ubuntu_release}/amd64' "${agent_publisher}" >/dev/null

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
for incompatible in removeprefix retry-all-errors; do
	if grep -F "${incompatible}" "${remote_deploy}" >/dev/null; then
		printf 'ERROR: remote deployment uses Ubuntu 20.04-incompatible feature: %s\n' "${incompatible}" >&2
		exit 1
	fi
done
grep -F 'Verified that unrelated Docker containers, networks, and volumes are unchanged' "${remote_deploy}" >/dev/null
grep -F 'project in {"hyperfilelens-sourcelens", "sourcelens"}' "${remote_deploy}" >/dev/null
grep -F './tools/quality/test-shared-host-guard.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-default-certificates.sh' "${workflow}" >/dev/null

installer="${ROOT}/deploy/installer/install.sh"
materialize_body="$(sed -n '/^materialize_to_install_dir()/,/^}/p' "${installer}")"
grep -F -- '--checksum' <<<"${materialize_body}" >/dev/null
grep -F -- '--delete' <<<"${materialize_body}" >/dev/null
if grep -F -- '--delete-excluded' <<<"${materialize_body}" >/dev/null; then
	printf 'ERROR: release materialization must preserve excluded runtime state\n' >&2
	exit 1
fi
grep -F 'PUBLIC_HOST="${HFL_PUBLIC_HOST:-}"' "${installer}" >/dev/null
grep -F 'values are hidden in non-interactive logs' "${installer}" >/dev/null
grep -F 'validate_default_tls_bundle "${src_root}/deploy/nginx/certs"' "${installer}" >/dev/null
grep -F 'sync_default_tls_bundle "${from_root}/deploy/nginx/certs"' "${installer}" >/dev/null
grep -F 'Preserving existing TLS certificate directory' "${installer}" >/dev/null
grep -F 'apply_upgrade_files "${src_root}" "${remove_sourcelens}"' "${installer}" >/dev/null
grep -F 'python3 "${sync_script}" --env-file "${env_file}" --example "${example}"' "${installer}" >/dev/null
grep -F 'host must be Ubuntu 20.04 or 24.04' "${installer}" >/dev/null
grep -F 'gateway-install-docker-ubuntu-amd64.sh' "${installer}" >/dev/null
grep -F 'docker-debs-ubuntu2004-amd64.tar.gz' "${installer}" >/dev/null
grep -F 'docker-debs-ubuntu2404-amd64.tar.gz' "${installer}" >/dev/null
if grep -E 'tomllib|extractall\([^)]*filter=' "${installer}" >/dev/null; then
	printf 'ERROR: installer contains Python APIs unavailable on Ubuntu 20.04\n' >&2
	exit 1
fi

release_verifier="${ROOT}/release/ci/verify-release.sh"
grep -F 'smoke_host="${SMOKE_HOST:-host.docker.internal}"' "${release_verifier}" >/dev/null
grep -F 'HFL_PUBLIC_HOST="${smoke_host}"' "${release_verifier}" >/dev/null
grep -F 'export SMOKE_HOST="${smoke_host}"' "${release_verifier}" >/dev/null
grep -F 'SEED_ADMIN_EMAIL="$(sudo sed' "${release_verifier}" >/dev/null
grep -F 'sudo env \' "${release_verifier}" >/dev/null
grep -F 'cp "${ROOT}/tools/config/sync_env.py" "${pkg_root}/sync-env.py"' \
	"${ROOT}/release/ci/assemble-release.sh" >/dev/null
grep -F 'stage_default_tls_bundle "${pkg_root}"' \
	"${ROOT}/release/ci/assemble-release.sh" >/dev/null
grep -F 'hyperfilelens-root-ca.crt' "${workflow}" >/dev/null
fingerprint_body="$(sed -n '/^sourcelens_bundle_fingerprint()/,/^}/p' "${installer}")"
grep -F 'BUILD_INFO.identity' <<<"${fingerprint_body}" >/dev/null
if grep -F 'upstream_ref' <<<"${fingerprint_body}" >/dev/null; then
	printf 'ERROR: SourceLens fingerprint must ignore per-release registry transit refs\n' >&2
	exit 1
fi

for executable in \
	"${ROOT}/.github/scripts/remote-deploy.sh" \
	"${ROOT}/tools/quality/check-python38-runtime.py" \
	"${ROOT}/tools/quality/test-shared-host-guard.sh" \
	"${ROOT}"/release/ci/*.sh \
	"${ROOT}/release/ci/write-sbom.py"; do
	[[ -x "${executable}" ]] || {
		printf 'ERROR: CI entry point is not executable: %s\n' "${executable}" >&2
		exit 1
	}
done

grep -F 'HFL_TENANT_PORT=11443' "${ROOT}/.env.example" >/dev/null
grep -F 'HFL_ADMIN_PORT=11444' "${ROOT}/.env.example" >/dev/null
grep -F 'FRONTEND_URL=https://127.0.0.1:11443' "${ROOT}/.env.example" >/dev/null
grep -F 'SOURCELENS_CONSOLE_PORT=11445' "${ROOT}/.env.example" >/dev/null
grep -F 'SEED_ADMIN_PASSWORD=Admin@123' "${ROOT}/.env.example" >/dev/null
if grep -E 'HFL_TLS_SAN_(IP|DNS)' "${ROOT}/.env.example" "${installer}" >/dev/null; then
	printf 'ERROR: runtime-generated TLS SAN configuration must not remain\n' >&2
	exit 1
fi
for runtime_tls_script in \
	"${installer}" \
	"${ROOT}/deploy/installer/sourcelens/install.sh" \
	"${ROOT}/dev/stack.sh" \
	"${ROOT}/tools/sourcelens/common.sh"; do
	if grep -F 'openssl req -x509' "${runtime_tls_script}" >/dev/null; then
		printf 'ERROR: runtime TLS generation remains in %s\n' "${runtime_tls_script}" >&2
		exit 1
	fi
done
for cert_file in tls.crt tls.key root-ca.crt SHA256SUMS README.md; do
	[[ -s "${ROOT}/deploy/nginx/certs/${cert_file}" ]] || {
		printf 'ERROR: default TLS file is missing: %s\n' "${cert_file}" >&2
		exit 1
	}
done
[[ ! -e "${ROOT}/deploy/nginx/certs/.gitignore" ]]
legacy_public_port_pattern='104(43|45|46)'
if git -C "${ROOT}" grep -n -E "${legacy_public_port_pattern}" -- .; then
	printf 'ERROR: tracked HFL files must not reference legacy 104xx public ports\n' >&2
	exit 1
fi
for runtime_alias in \
	'nginx:stable-alpine hyperfilelens-sourcelens-nginx:stable-alpine' \
	'postgres:17 hyperfilelens-postgres:17' \
	'redis:alpine hyperfilelens-redis:alpine'; do
	grep -F "${runtime_alias}" "${ROOT}/tools/sourcelens/common.sh" >/dev/null
done
smoke_runner="${ROOT}/tools/dev/browser-smoke.sh"
grep -F -- '--add-host host.docker.internal:host-gateway' "${smoke_runner}" >/dev/null
grep -F 'SMOKE_HOST' "${smoke_runner}" >/dev/null
smoke_script="${ROOT}/tools/dev/browser-smoke.mjs"
grep -F 'host.docker.internal' "${smoke_script}" >/dev/null
grep -F "submit.waitFor({ state: 'visible'" "${smoke_script}" >/dev/null
if grep -F 'captchaImage' "${smoke_script}" >/dev/null; then
	printf 'ERROR: local browser smoke must not depend on image captcha\n' >&2
	exit 1
fi
grep -F 'waitForPlatformOps' "${smoke_script}" >/dev/null
grep -F 'const hfl = await browser.newContext' "${smoke_script}" >/dev/null
grep -F "allowedHosts: ['host.docker.internal']" "${ROOT}/src/frontend/vite.config.ts" >/dev/null
if grep -F -- '--network host' "${smoke_runner}" >/dev/null; then
	printf 'ERROR: browser smoke must reach published ports through host-gateway\n' >&2
	exit 1
fi
grep -F 'image: hyperfilelens-postgres:17' "${ROOT}/deploy/docker-compose.yml" >/dev/null
grep -F 'absolute_redirect off;' "${ROOT}/deploy/nginx/default.conf" >/dev/null
grep -F 'mem_limit: 448m' "${ROOT}/deploy/docker-compose.yml" >/dev/null
grep -F 'name: hyperfilelens-sourcelens' \
	"${ROOT}/deploy/installer/sourcelens/docker-compose.template.yml" >/dev/null
[[ -f "${ROOT}/.github/workflows/deploy_release.yml" ]] || {
	printf 'ERROR: manual published-release deployment workflow is missing\n' >&2
	exit 1
}

printf 'Release contract checks passed.\n'

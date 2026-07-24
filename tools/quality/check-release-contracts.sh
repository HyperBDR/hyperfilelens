#!/usr/bin/env bash
# Fast release workflow contract checks that do not require Docker or network access.
set -euo pipefail
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

grep -F './tools/quality/test-docker-image-digest-alias.sh' \
	"${ROOT}/.github/workflows/artifact_pipeline.yml" >/dev/null
grep -F './tools/quality/test-offline-docker-package-plan.sh' \
	"${ROOT}/.github/workflows/artifact_pipeline.yml" >/dev/null

# shellcheck source=../lib/version.sh
source "${ROOT}/tools/lib/version.sh"
actual="$(release_package_basename_for_version v0.1.0 69F809F)"
[[ "${actual}" == "hyperfilelens-0.1.0-69f809f.tar.gz" ]] || {
	printf 'ERROR: unexpected release package basename: %s\n' "${actual}" >&2
	exit 1
}
main_actual="$(release_package_basename_for_version main-69f809f 69F809F)"
[[ "${main_actual}" == "hyperfilelens-main-69f809f.tar.gz" ]] || {
	printf 'ERROR: unexpected Main package basename: %s\n' "${main_actual}" >&2
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
grep -F 'SOURCELENS_UV_VERSION="${SOURCELENS_UV_VERSION:-0.10.2}"' \
	"${ROOT}/tools/sourcelens/defaults.env" >/dev/null
grep -F 'set_key("DJANGO_DEBUG", "true")' \
	"${ROOT}/deploy/installer/sourcelens/patch-env-runtime.py" >/dev/null

sourcelens_common="${ROOT}/tools/sourcelens/common.sh"
sourcelens_build_body="$(sed -n '/^sourcelens_build_app_images()/,/^}/p' "${sourcelens_common}")"
grep -F 'http://archive.ubuntu.com/ubuntu' <<<"${sourcelens_build_body}" >/dev/null
grep -F 'https://deb.debian.org/debian' <<<"${sourcelens_build_body}" >/dev/null
grep -F 'https://pypi.org/simple' <<<"${sourcelens_build_body}" >/dev/null
if grep -F 'mirrors.tuna.tsinghua.edu.cn' <<<"${sourcelens_build_body}" >/dev/null; then
	printf 'ERROR: SourceLens build must not enable a third-party mirror by default\n' >&2
	exit 1
fi

mkdir -p "${tmp}/source-patch/lensnode"
cat >"${tmp}/source-patch/Dockerfile" <<'DOCKERFILE'
FROM ubuntu:24.04
ARG PIP_TRUSTED_HOST=pypi.org
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
RUN set -eux; \
    pip install \
        uv; \
    uv pip install --system .
DOCKERFILE
cp "${tmp}/source-patch/Dockerfile" "${tmp}/source-patch/lensnode/Dockerfile"
sourcelens_patch_dockerfile_uv_network "${tmp}/source-patch" 120 2 0.10.2
for dockerfile in "${tmp}/source-patch/Dockerfile" "${tmp}/source-patch/lensnode/Dockerfile"; do
	grep -F 'ARG UV_VERSION=0.10.2' "${dockerfile}" >/dev/null
	grep -F '"uv==${UV_VERSION}"' "${dockerfile}" >/dev/null
done

cat >"${tmp}/source-patch/docker-compose.yml" <<'YAML'
services:
  backend-api:
    build:
      context: .
      args:
        APT_MIRROR_URL: ${APT_MIRROR_URL:-https://mirrors.tuna.tsinghua.edu.cn/ubuntu}
        PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}
        PIP_TRUSTED_HOST: ${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}
  lensnode:
    build:
      context: ./lensnode
      args:
        PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}
        PIP_TRUSTED_HOST: ${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}
YAML
sourcelens_patch_compose_lensnode_apt_mirror \
	"${tmp}/source-patch" https://deb.debian.org/debian
sourcelens_patch_compose_build_sources \
	"${tmp}/source-patch" \
	http://archive.ubuntu.com/ubuntu \
	https://deb.debian.org/debian \
	https://pypi.org/simple \
	pypi.org
sourcelens_patch_compose_uv_network "${tmp}/source-patch" 120 2 0.10.2
if grep -F 'mirrors.tuna.tsinghua.edu.cn' \
	"${tmp}/source-patch/docker-compose.yml" >/dev/null; then
	printf 'ERROR: patched SourceLens Compose still defaults to a third-party mirror\n' >&2
	exit 1
fi
grep -F 'APT_MIRROR_URL: ${APT_MIRROR_URL:-http://archive.ubuntu.com/ubuntu}' \
	"${tmp}/source-patch/docker-compose.yml" >/dev/null
grep -F 'APT_MIRROR_URL: ${DEBIAN_APT_MIRROR_URL:-https://deb.debian.org/debian}' \
	"${tmp}/source-patch/docker-compose.yml" >/dev/null
[[ "$(grep -Fc 'PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.org/simple}' \
	"${tmp}/source-patch/docker-compose.yml")" -eq 2 ]]
[[ "$(grep -Fc 'UV_VERSION: ${UV_VERSION:-0.10.2}' \
	"${tmp}/source-patch/docker-compose.yml")" -eq 2 ]]

workflow="${ROOT}/.github/workflows/artifact_pipeline.yml"
release_workflow="${ROOT}/.github/workflows/release.yml"
test_workflow="${ROOT}/.github/workflows/test.yml"
production_workflow="${ROOT}/.github/workflows/production_deploy.yml"
agent_certification="${ROOT}/release/ci/certify-agent-candidate.py"
[[ -f "${workflow}" ]] || {
	printf 'ERROR: reusable artifact workflow is missing\n' >&2
	exit 1
}
for entrypoint in "${release_workflow}" "${test_workflow}" "${production_workflow}"; do
	[[ -f "${entrypoint}" ]] || {
		printf 'ERROR: deployment entrypoint is missing: %s\n' "${entrypoint}" >&2
		exit 1
	}
done
[[ "$(awk '/^  assemble-release:/{job=1} job && /timeout-minutes:/{print $2; exit}' "${workflow}")" == "90" ]] || {
	printf 'ERROR: release assembly timeout must cover large GitHub asset uploads\n' >&2
	exit 1
}
[[ "$(awk '/^  verify-release:/{job=1} job && /timeout-minutes:/{print $2; exit}' "${workflow}")" == "120" ]] || {
	printf 'ERROR: release verification timeout must cover package download and offline install\n' >&2
	exit 1
}
grep -F 'timeout-minutes: 120' "${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'docker_preexisting=0' "${ROOT}/.github/scripts/remote-deploy.sh" >/dev/null
grep -F 'Existing Docker not found; the verified offline release bundle will install Docker CE' \
	"${ROOT}/.github/scripts/remote-deploy.sh" >/dev/null
grep -F 'existing Docker daemon is not reachable' \
	"${ROOT}/.github/scripts/remote-deploy.sh" >/dev/null
grep -F 'turnstile_enabled: ${{ vars.PREPROD_TURNSTILE_ENABLED' "${workflow}" >/dev/null
grep -F 'public_url: ${{ vars.PREPROD_PUBLIC_URL }}' "${workflow}" >/dev/null
grep -F 'turnstile_enabled: ${{ vars.TEST_TURNSTILE_ENABLED' "${workflow}" >/dev/null
grep -F 'public_url: ${{ vars.TEST_PUBLIC_URL }}' "${workflow}" >/dev/null
grep -F 'turnstile_enabled: ${{ vars.PROD_TURNSTILE_ENABLED' "${production_workflow}" >/dev/null
grep -F 'public_url: ${{ vars.PROD_PUBLIC_URL }}' "${production_workflow}" >/dev/null
grep -F 'hfl_insecure_tls: ${{ vars.TEST_HFL_INSECURE_TLS }}' "${workflow}" >/dev/null
grep -F 'hfl_insecure_tls: ${{ vars.PREPROD_HFL_INSECURE_TLS }}' "${workflow}" >/dev/null
grep -F 'hfl_insecure_tls: ${{ vars.PREPROD_HFL_INSECURE_TLS }}' "${release_workflow}" >/dev/null
grep -F 'hfl_insecure_tls: ${{ vars.PROD_HFL_INSECURE_TLS }}' "${production_workflow}" >/dev/null
grep -F 'release_download_proxy_url: ${{ vars.TEST_RELEASE_DOWNLOAD_PROXY_URL }}' "${workflow}" >/dev/null
grep -F 'release_download_proxy_url: ${{ vars.PREPROD_RELEASE_DOWNLOAD_PROXY_URL }}' "${workflow}" >/dev/null
grep -F 'release_download_proxy_url: ${{ vars.PROD_RELEASE_DOWNLOAD_PROXY_URL }}' "${production_workflow}" >/dev/null
if grep -F 'PROD_PUBLIC_HOST' "${workflow}" "${production_workflow}" >/dev/null; then
	printf 'ERROR: release workflow still uses the ambiguous PROD_PUBLIC_HOST variable\n' >&2
	exit 1
fi
grep -F '"TURNSTILE_ENABLED=$TURNSTILE_ENABLED"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F '"HFL_INSECURE_TLS=$HFL_INSECURE_TLS"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'test:1|preprod:1|prod:0' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
for variable in \
	SMTP_HOST SMTP_PORT SMTP_USERNAME SMTP_SECURITY EMAIL_FROM; do
	grep -F "TEST_${variable}" "${workflow}" >/dev/null
	grep -F "PREPROD_${variable}" "${workflow}" >/dev/null
	grep -F "PROD_${variable}" "${production_workflow}" >/dev/null
done
grep -F 'smtp_password: ${{ secrets.TEST_SMTP_PASSWORD }}' "${workflow}" >/dev/null
grep -F 'smtp_password: ${{ secrets.PREPROD_SMTP_PASSWORD }}' "${workflow}" >/dev/null
grep -F 'smtp_password: ${{ secrets.PROD_SMTP_PASSWORD }}' "${production_workflow}" >/dev/null
for variable in AI_MODEL_PROVIDER AI_MODEL_ID AI_MODEL_DISPLAY_NAME; do
	grep -F "TEST_${variable}" "${workflow}" >/dev/null
	grep -F "PREPROD_${variable}" "${workflow}" >/dev/null
	grep -F "PROD_${variable}" "${production_workflow}" >/dev/null
done
for secret in AI_MODEL_API_BASE AI_MODEL_API_KEY; do
	grep -F "secrets.TEST_${secret}" "${workflow}" >/dev/null
	grep -F "secrets.PREPROD_${secret}" "${workflow}" >/dev/null
	grep -F "secrets.PROD_${secret}" "${production_workflow}" >/dev/null
done
grep -F 'python manage.py ensure_platform_ai_model' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'HFL_AI_MODEL_CONNECTIVITY=failed' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'exit "$command_status"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
if grep -F '"AI_MODEL_API_KEY=$AI_MODEL_API_KEY"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null; then
	printf 'ERROR: AI model API key must not be persisted in the runtime .env\n' >&2
	exit 1
fi
grep -F '"HFL_EMAIL_SIGNUP_ENABLED=false"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F '"SMTP_PASSWORD=$SMTP_PASSWORD"' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'umask 077 && cat > /var/tmp/hyperfilelens-runtime-' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
if git -C "${ROOT}" grep -n -E \
	'HFL_SELF_SERVICE_PASSWORD_RESET|HFL_EMAIL_SETTINGS_MODE' -- . \
	':!tools/quality/check-release-contracts.sh'; then
	printf 'ERROR: obsolete email deployment feature flags remain\n' >&2
	exit 1
fi
if git -C "${ROOT}" grep -n 'CAPTCHA_PROVIDER' -- . \
	':!tools/config/sync_env.py' \
	':!tools/quality/check-release-contracts.sh'; then
	printf 'ERROR: CAPTCHA_PROVIDER must not remain in runtime or deployment configuration\n' >&2
	exit 1
fi
grep -F 'Capture failed install diagnostics' "${workflow}" >/dev/null
grep -F 'logs --no-color --tail 200' "${workflow}" >/dev/null
if grep -E '^  (workflow_dispatch|push|schedule):' "${workflow}" >/dev/null; then
	printf 'ERROR: reusable artifact workflow must not expose a direct trigger\n' >&2
	exit 1
fi
grep -F 'workflow_call:' "${workflow}" >/dev/null
grep -F 'tags:' "${release_workflow}" >/dev/null
grep -F 'workflow_dispatch:' "${release_workflow}" >/dev/null
grep -F 'Validate manual pre-production redeployment' "${release_workflow}" >/dev/null
grep -F 'uses: ./.github/workflows/deploy_target.yml' "${release_workflow}" >/dev/null
grep -F 'channel: release' "${release_workflow}" >/dev/null
grep -F 'workflow_dispatch:' "${test_workflow}" >/dev/null
grep -F 'schedule:' "${test_workflow}" >/dev/null
grep -F 'channel: main' "${test_workflow}" >/dev/null
grep -F 'workflow_dispatch:' "${production_workflow}" >/dev/null
grep -F 'Production deployment must be dispatched from refs/heads/main' \
	"${production_workflow}" >/dev/null
grep -F 'Production requires a published, non-prerelease GitHub Release' \
	"${production_workflow}" >/dev/null
for job in \
	prepare quality build-hfl-images build-sourcelens-images build-agent \
	certify-source-host agent-release-gate \
	build-host-debs export-hfl-images export-sourcelens-bundle \
	export-runtime-images assemble-release verify-release publish-release \
	deploy-test deploy-preprod; do
	grep -F "  ${job}:" "${workflow}" >/dev/null || {
		printf 'ERROR: artifact workflow job is missing: %s\n' "${job}" >&2
		exit 1
	}
done
if grep -F 'deploy-prod:' "${workflow}" >/dev/null \
	|| grep -E '(^|[^A-Z])PROD_' "${workflow}" >/dev/null; then
	printf 'ERROR: automatic artifact workflow must not contain production deployment configuration\n' >&2
	exit 1
fi
grep -F "vars.TEST_DEPLOY_ENABLED == 'true'" "${workflow}" >/dev/null
grep -F "vars.PREPROD_DEPLOY_ENABLED == 'true'" "${workflow}" >/dev/null
grep -F 'PROD_DEPLOY_ENABLED' "${production_workflow}" >/dev/null

for job in build-hfl-images build-sourcelens-images build-host-debs export-runtime-images; do
	body="$(sed -n "/^  ${job}:/,/^  [a-zA-Z0-9_-]*:/p" "${workflow}")"
	grep -F 'needs: [prepare, quality]' <<<"${body}" >/dev/null || {
		printf 'ERROR: %s must start after quality without waiting for Agent certification\n' "${job}" >&2
		exit 1
	}
done
grep -F 'cancel-in-progress: ${{ inputs.channel == '\''main'\'' }}' "${workflow}" >/dev/null
grep -F 'Retain only the current successful Main build' "${workflow}" >/dev/null
grep -F 'needs: [prepare, publish-release]' "${workflow}" >/dev/null
grep -F 'BUILD_REQUIRED: ${{ needs.prepare.outputs.build_required }}' "${workflow}" >/dev/null
grep -F '[[ "$BUILD_REQUIRED" != "false" || "$PUBLISH_RESULT" != "skipped" ]]' "${workflow}" >/dev/null
cleanup_body="$(sed -n '/^  cleanup-main-builds:/,$p' "${workflow}")"
grep -F 'delete_main_artifact()' <<<"${cleanup_body}" >/dev/null
grep -F 'gh release delete "$artifact_id" --repo "$GITHUB_REPOSITORY" --yes' \
  <<<"${cleanup_body}" >/dev/null
grep -F 'git/ref/tags/${artifact_id}' <<<"${cleanup_body}" >/dev/null
grep -F 'git/refs/tags/${artifact_id}' <<<"${cleanup_body}" >/dev/null
if grep -F -- '--cleanup-tag' <<<"${cleanup_body}" >/dev/null; then
  printf 'ERROR: idempotent Main cleanup must not fail when a Release has no Git tag\n' >&2
  exit 1
fi
grep -F 'ubuntu_release: "22.04"' "${workflow}" >/dev/null
grep -F 'asset: ubuntu2204' "${workflow}" >/dev/null

grep -F 'actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6' "${workflow}" >/dev/null
grep -F 'actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6' "${workflow}" >/dev/null
grep -F 'actions/setup-go@924ae3a1cded613372ab5595356fb5720e22ba16 # v6' "${workflow}" >/dev/null

grep -F '_internal-hfl-images.tar' "${workflow}" >/dev/null
if grep -E '_internal-[^[:space:]"'\'']*\.tar\.gz' "${workflow}" >/dev/null; then
	printf 'ERROR: CI-only envelopes must not recompress already-compressed payloads\n' >&2
	exit 1
fi

runtime_pins="${ROOT}/tools/dependencies/versions/runtime-images.env"
for image in POSTGRES_IMAGE REDIS_IMAGE NGINX_IMAGE; do
	grep -E "^${image}=[^[:space:]]+@sha256:[0-9a-f]{64}$" "${runtime_pins}" >/dev/null
done
grep -F 'slcache-${fingerprint}' "${ROOT}/release/ci/build-sourcelens-image.sh" >/dev/null
grep -F 'docker buildx imagetools create --tag "${target_ref}" "${cache_ref}"' \
	"${ROOT}/release/ci/build-sourcelens-image.sh" >/dev/null

if grep -R -n 'docker-buildx-plugin\|BUILDX_PLUGIN_VERSION' \
	"${ROOT}/tools/dependencies" "${ROOT}/deploy/bootstrap" "${ROOT}/release/ci" >/dev/null; then
	printf 'ERROR: runtime Docker bundles must not include the Buildx plugin\n' >&2
	exit 1
fi

grep -F 'configure_macos_dev_shell' "${ROOT}/dev/stack.sh" >/dev/null
grep -F 'verify_amd64_runtime' "${ROOT}/dev/stack.sh" >/dev/null
grep -F 'DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/amd64}"' \
	"${ROOT}/dev/stack.sh" >/dev/null
[[ -x "${ROOT}/dev/bootstrap-macos.sh" && -f "${ROOT}/dev/Brewfile" ]]
deploy_workflow="${ROOT}/.github/workflows/deploy_target.yml"
[[ "$(grep -c -- '-o ServerAliveInterval=30' "${deploy_workflow}")" -eq 5 ]] || {
	printf 'ERROR: every deployment SSH call must enable ServerAliveInterval\n' >&2
	exit 1
}
[[ "$(grep -c -- '-o ServerAliveCountMax=20' "${deploy_workflow}")" -eq 5 ]] || {
	printf 'ERROR: every deployment SSH call must set ServerAliveCountMax\n' >&2
	exit 1
}
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
grep -F './tools/quality/test-installer-image-refresh.sh' "${workflow}" >/dev/null
grep -F "'.register-form-box, .login-form-box'" \
	"${ROOT}/tools/dev/browser-smoke.mjs" >/dev/null
grep -F "'.dashboard-page, .main-content, .platform-ops-main, .login-form-box, .register-form-box'" \
	"${ROOT}/tools/dev/browser-smoke.mjs" >/dev/null
grep -F 'verifyResponsivePlatformPrimaryAction' \
	"${ROOT}/tools/dev/browser-smoke.mjs" >/dev/null
grep -F 'python3 -m unittest tools/quality/test_agent_certification_gate.py' "${workflow}" >/dev/null
grep -F 'release/ci/certify-agent-candidate.py' "${workflow}" >/dev/null
grep -F '"KOPIA_USE_KEYRING": "false"' "${agent_certification}" >/dev/null
grep -F '"KOPIA_PERSIST_CREDENTIALS_ON_CONNECT": "false"' "${agent_certification}" >/dev/null
grep -F 'apt source: official Ubuntu (HTTPS after CA bootstrap)' \
	"${ROOT}/src/agent/scripts/fetch-deps.sh" >/dev/null
grep -F 'using official Ubuntu sources (HTTPS after CA bootstrap)' \
	"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh" >/dev/null
grep -F 'NAS_DOCKER_TIMEOUT=900' "${ROOT}/src/agent/scripts/fetch-deps.sh" >/dev/null
for dependency_fetcher in \
	"${ROOT}/src/agent/scripts/fetch-deps.sh" \
	"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh"; do
	grep -F 'Acquire::https::Verify-Peer=false' "${dependency_fetcher}" >/dev/null
	grep -F 'Acquire::https::Verify-Host=false' "${dependency_fetcher}" >/dev/null
	grep -F 'Acquire::Retries=5' "${dependency_fetcher}" >/dev/null
	grep -F 'for attempt in 1 2 3' "${dependency_fetcher}" >/dev/null
	grep -F 'if [[ -z "${apt_mirror_url}" ]]; then' "${dependency_fetcher}" >/dev/null
	grep -F 'Dir::State::status="${baseline_status}"' "${dependency_fetcher}" >/dev/null
done
if grep -E -n 'apt_mirror_http|default Ubuntu HTTP sources' \
	"${ROOT}/src/agent/scripts/fetch-deps.sh" \
	"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh" >/dev/null; then
	printf 'ERROR: offline dependency fetchers must not force apt mirrors to HTTP\n' >&2
	exit 1
fi
grep -F 'release/ci/verify-agent-certifications.py' "${workflow}" >/dev/null
grep -F 'runner: ubuntu-24.04-arm' "${workflow}" >/dev/null
grep -F 'runner: macos-15-intel' "${workflow}" >/dev/null
grep -F 'runner: macos-15' "${workflow}" >/dev/null
grep -F 'runner: windows-2022' "${workflow}" >/dev/null
[[ "$(grep -c 'APT_MIRROR: \${{ vars.CI_UBUNTU_APT_MIRROR }}' "${workflow}")" -eq 2 ]]
[[ "$(awk '/^  build-host-debs:/{job=1} job && /timeout-minutes:/{print $2; exit}' "${workflow}")" == "60" ]]
grep -F 'bootstrap_tools_ok=0' "${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh" >/dev/null
grep -F 'Dir::Etc::sourcelist=/etc/apt/sources.list.d/docker.list' \
	"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh" >/dev/null
grep -F -- '--required-target linux:arm64' "${workflow}" >/dev/null
grep -F -- '--required-target darwin:arm64' "${workflow}" >/dev/null
grep -F -- '--required-target windows:amd64' "${workflow}" >/dev/null
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
frontend_dockerfile="${ROOT}/deploy/docker/frontend.Dockerfile"
grep -F 'ARG KOPIA_BINARY=build/kopia/dist/linux/amd64/kopia' "${backend_dockerfile}" >/dev/null
grep -F 'COPY --chmod=0755 ${KOPIA_BINARY} /usr/local/bin/kopia' "${backend_dockerfile}" >/dev/null
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
grep -F 'org.opencontainers.image.revision="${IMAGE_REVISION}"' "${backend_dockerfile}" >/dev/null
grep -F 'org.opencontainers.image.revision="${IMAGE_REVISION}"' "${frontend_dockerfile}" >/dev/null
grep -F 'IMAGE_REVISION=${{ needs.prepare.outputs.commit }}' "${workflow}" >/dev/null

installer="${ROOT}/deploy/installer/install.sh"
grep -F 'loading image {rel}' "${installer}" >/dev/null
grep -F 'org.opencontainers.image.revision' "${installer}" >/dev/null
grep -F 'does not match release' "${installer}" >/dev/null
if grep -F 'image already loaded' "${installer}" >/dev/null; then
	printf 'ERROR: installer must refresh verified release images even when tags already exist\n' >&2
	exit 1
fi

sourcelens_image_builder="${ROOT}/release/ci/build-sourcelens-image.sh"
grep -F 'target_ref="${registry_prefix}/hyperfilelens-sourcelens-${component}:${hfl_version}-sl${SOURCELENS_VERSION}"' \
	"${sourcelens_image_builder}" >/dev/null
grep -F 'registry prefix must include host and namespace' \
	"${sourcelens_image_builder}" >/dev/null

agent_publisher="${ROOT}/tools/agent/publish.sh"
grep -F 'all | standard | ubuntu2004 | ubuntu2204 | ubuntu2404' "${agent_publisher}" >/dev/null
grep -F 'for ubuntu_flavor in ubuntu2004 ubuntu2204 ubuntu2404' "${agent_publisher}" >/dev/null
grep -F 'build/dependencies/docker/ubuntu-${ubuntu_release}/amd64' "${agent_publisher}" >/dev/null

agent_bootstrap_linux="${ROOT}/deploy/bootstrap/agent-bootstrap-linux.sh"
agent_bootstrap_macos="${ROOT}/deploy/bootstrap/agent-bootstrap-macos.sh"
agent_bootstrap_windows="${ROOT}/deploy/bootstrap/agent-bootstrap-windows.ps1"
grep -F 'requires a systemd-based Linux distribution' "${agent_bootstrap_linux}" >/dev/null
grep -F 'systemctl show-environment' "${agent_bootstrap_linux}" >/dev/null
grep -F 'launchd is required to install the agent service on macOS' "${agent_bootstrap_macos}" >/dev/null
grep -F 'Windows ARM64 is not supported by this release' "${agent_bootstrap_windows}" >/dev/null
if grep -F 'hfl-enroll-windows-$archRel.exe' "${agent_bootstrap_windows}" >/dev/null \
	&& ! grep -F '"ARM64" {' "${agent_bootstrap_windows}" >/dev/null; then
	printf 'ERROR: Windows bootstrap may request an unsupported ARM64 enrollment binary\n' >&2
	exit 1
fi

remote_deploy="${ROOT}/.github/scripts/remote-deploy.sh"
[[ -x "${remote_deploy}" ]] || {
	printf 'ERROR: remote deployment script is missing or not executable\n' >&2
	exit 1
}
grep -F 'browser_download_url' "${remote_deploy}" >/dev/null
grep -F 'bash "${package_root}/install.sh" "${install_args[@]}"' \
	"${remote_deploy}" >/dev/null
if grep -F 'install.sh" platform-gateway ensure' "${remote_deploy}" >/dev/null; then
	printf 'ERROR: remote deployment must not repeat installer-owned Gateway ensure\n' >&2
	exit 1
fi
grep -F -- '--public-url) PUBLIC_URL=' "${remote_deploy}" >/dev/null
grep -F -- '--direct-host) DIRECT_HOST=' "${remote_deploy}" >/dev/null
grep -F -- '--runtime-env-file "${RUNTIME_ENV_FILE}"' "${remote_deploy}" >/dev/null
grep -F 'Download and deploy the complete release package on the target' "${deploy_workflow}" >/dev/null
grep -F 'download_proxy_args=(--download-proxy-url "$RELEASE_DOWNLOAD_PROXY_URL")' \
	"${deploy_workflow}" >/dev/null
grep -F '"${download_proxy_args[@]}"' "${deploy_workflow}" >/dev/null
grep -F -- '--download-proxy-url) DOWNLOAD_PROXY_URL=' "${remote_deploy}" >/dev/null
grep -F 'Target-side Release download proxy is enabled' "${remote_deploy}" >/dev/null
grep -F 'retrying directly' "${remote_deploy}" >/dev/null
grep -F -- '--proxy "${DOWNLOAD_PROXY_URL}"' "${remote_deploy}" >/dev/null
grep -F 'DOWNLOAD_PROXY_URL}" == "UNCONFIGURED"' "${remote_deploy}" >/dev/null
[[ "$(grep -c 'RELEASE_DOWNLOAD_PROXY_URL.*!=.*UNCONFIGURED' "${deploy_workflow}")" -eq 2 ]] || {
	printf 'ERROR: UNCONFIGURED Release proxy placeholders must select direct target downloads\n' >&2
	exit 1
}
if grep -E 'gh release download|(^|[[:space:]])scp([[:space:]]|$)|staged-assets-dir|STAGED_ASSETS_DIR' \
	"${deploy_workflow}" "${remote_deploy}" >/dev/null; then
	printf 'ERROR: deployment must download the complete Release package on the target host\n' >&2
	exit 1
fi
if grep -F -- '--force-recreate' "${remote_deploy}" >/dev/null; then
	printf 'ERROR: production deployment must apply runtime configuration before startup\n' >&2
	exit 1
fi
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
grep -F './tools/quality/test-release-download-proxy.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-default-certificates.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-gateway-bootstrap-health.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-platform-gateway-auto-deploy.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-agent-gateway-uninstall.sh' "${workflow}" >/dev/null
grep -F 'HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=false' "${ROOT}/.env.example" >/dev/null
grep -F 'com.hyperfilelens.component: "gateway-lensnode"' \
	"${ROOT}/deploy/bootstrap/gateway-install-lensnode-sidecar.sh" >/dev/null
grep -F './tools/quality/test-deployment-optional-config.sh' "${workflow}" >/dev/null
grep -F './tools/quality/test-payload-tree-hash.sh' "${workflow}" >/dev/null
grep -F 'Post-deploy internal health checks' "${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F 'https://127.0.0.1:11443/health/ready' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
grep -F '::warning::Public endpoint is not ready' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null
if grep -F 'APP_PUBLIC_HOST' "${ROOT}/.github/workflows/deploy_target.yml" >/dev/null; then
	printf 'ERROR: deployment checks must not append internal ports to a public hostname\n' >&2
	exit 1
fi

installer="${ROOT}/deploy/installer/install.sh"
grep -F 'platform-gateway ensure' "${installer}" >/dev/null
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
grep -F 'apply_runtime_configuration' "${installer}" >/dev/null
backup_body="$(sed -n '/^backup_postgresql_dump()/,/^}/p' "${installer}")"
grep -F 'COMPOSE=(docker compose)' <<<"${backup_body}" >/dev/null
grep -F 'skipping logical database backup before file backup' <<<"${backup_body}" >/dev/null
[[ "$(grep -Fc 'sourcelens_compose exec -T postgres' <<<"${backup_body}")" -eq 2 ]]
if grep -E 'sourcelens_compose (ps -q|exec -T) postgresql' <<<"${backup_body}" >/dev/null; then
	printf 'ERROR: bundled SourceLens PostgreSQL Compose service is named postgres\n' >&2
	exit 1
fi
file_backup_body="$(sed -n '/^backup_env_and_data()/,/^}/p' "${installer}")"
grep -F -- "--exclude='data/postgresql'" <<<"${file_backup_body}" >/dev/null
grep -F -- "--exclude='data/sourcelens/postgresql'" <<<"${file_backup_body}" >/dev/null
grep -F 'prune_upgrade_backups' "${installer}" >/dev/null
grep -F 'HFL_BACKUP_RETENTION_COUNT' "${installer}" >/dev/null
grep -F 'HFL_BACKUP_RETENTION_DAYS' "${installer}" >/dev/null
grep -F 'HFL_BACKUP_RETENTION_BYTES' "${installer}" >/dev/null
grep -F 'python3 "${sync_script}" --env-file "${env_file}" --example "${example}"' "${installer}" >/dev/null
grep -F 'host must be Ubuntu 20.04, 22.04, or 24.04' "${installer}" >/dev/null
grep -F 'gateway-install-docker-ubuntu-amd64.sh' "${installer}" >/dev/null
grep -F 'docker-debs-ubuntu2004-amd64.tar.gz' "${installer}" >/dev/null
grep -F 'docker-debs-ubuntu2204-amd64.tar.gz' "${installer}" >/dev/null
grep -F 'docker-debs-ubuntu2404-amd64.tar.gz' "${installer}" >/dev/null
if grep -E 'tomllib|extractall\([^)]*filter=' "${installer}" >/dev/null; then
	printf 'ERROR: installer contains Python APIs unavailable on Ubuntu 20.04\n' >&2
	exit 1
fi

grep -F 'verify-host-debs-asset.sh' \
	"${workflow}" >/dev/null
grep -F 'verify-ubuntu-agent-bundle.sh' \
	"${workflow}" >/dev/null
grep -F 'Offline NAS dependency install pass ${attempt}/3' \
	"${ROOT}/release/ci/verify-ubuntu-agent-bundle.sh" >/dev/null
grep -F 'Offline NAS dependency install pass ${attempt}/3' \
	"${ROOT}/src/agent/packaging/install/install.sh" >/dev/null
for verification_script in \
	"${ROOT}/release/ci/verify-host-debs-asset.sh" \
	"${ROOT}/release/ci/verify-ubuntu-agent-bundle.sh"; do
	[[ -x "${verification_script}" ]] || {
		printf 'ERROR: Ubuntu verification script is not executable: %s\n' "${verification_script}" >&2
		exit 1
	}
done

if grep -ER 'uses:[[:space:]]+[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@' \
	"${ROOT}/.github/workflows" \
	| grep -Ev '@[0-9a-f]{40}([[:space:]]|$)' >/dev/null; then
	printf 'ERROR: external GitHub Actions must be pinned to full commit SHAs\n' >&2
	exit 1
fi

release_verifier="${ROOT}/release/ci/verify-release.sh"
grep -F 'smoke_host="${SMOKE_HOST:-host.docker.internal}"' "${release_verifier}" >/dev/null
grep -F 'HFL_PUBLIC_HOST="${smoke_host}"' "${release_verifier}" >/dev/null
grep -F 'export SMOKE_HOST="${smoke_host}"' "${release_verifier}" >/dev/null
grep -F 'SEED_ADMIN_EMAIL="$(sudo sed' "${release_verifier}" >/dev/null
grep -F 'upgrade --from "${pkg_root}" --yes' "${release_verifier}" >/dev/null
grep -F 'Full release install, upgrade, and login verification passed' "${release_verifier}" >/dev/null
grep -F 'sudo env \' "${release_verifier}" >/dev/null
grep -F 'cp "${ROOT}/tools/config/sync_env.py" "${pkg_root}/sync-env.py"' \
	"${ROOT}/release/ci/assemble-release.sh" >/dev/null
grep -F 'cp "${ROOT}/deploy/installer/apply-runtime-config.py" "${pkg_root}/apply-runtime-config.py"' \
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
	"${ROOT}/tools/quality/test-main-channel-contracts.sh" \
	"${ROOT}/tools/quality/test-upgrade-backup-retention.sh" \
	"${ROOT}/tools/quality/test-shared-host-guard.sh" \
	"${ROOT}/tools/quality/test-release-download-proxy.sh" \
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
grep -F 'HFL_LOGIN_PORT="${login_port}"' "${smoke_runner}" >/dev/null
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
grep -F 'map $server_port $hfl_site {' \
	"${ROOT}/deploy/nginx/snippets/hfl-log-format.conf" >/dev/null
grep -E '^[[:space:]]*10444[[:space:]]+ops;' \
	"${ROOT}/deploy/nginx/snippets/hfl-log-format.conf" >/dev/null
grep -F 'proxy_set_header X-HFL-Site-Role $hfl_site;' \
	"${ROOT}/deploy/nginx/snippets/hfl-backend-proxy-headers.inc" >/dev/null
grep -F 'mem_limit: 448m' "${ROOT}/deploy/docker-compose.yml" >/dev/null
grep -F 'name: hyperfilelens-sourcelens' \
	"${ROOT}/deploy/installer/sourcelens/docker-compose.template.yml" >/dev/null
grep -F 'target: prod' "${production_workflow}" >/dev/null
grep -F 'channel: release' "${production_workflow}" >/dev/null
grep -F 'Production deployment requires a manual workflow_dispatch event' \
	"${ROOT}/.github/workflows/deploy_target.yml" >/dev/null

printf 'Release contract checks passed.\n'

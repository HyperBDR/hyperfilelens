#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Source stack functions without executing the command dispatcher.
# shellcheck source=../../dev/stack.sh
source "${ROOT_REPO}/dev/stack.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# A stale runtime metadata value must not pin bundled development or release builds.
mkdir -p "${tmp}/repo"
printf '%s\n' 'SOURCELENS_GIT_REF=v0.4.0' >"${tmp}/repo/.env"
original_root="${ROOT}"
ROOT="${tmp}/repo"
SOURCELENS_GIT_REF=""
load_repo_env_defaults
# shellcheck source=../sourcelens/defaults.env
source "${ROOT_REPO}/tools/sourcelens/defaults.env"
[[ "${SOURCELENS_GIT_REF}" == "v0.20.0" ]]
ROOT="${original_root}"

dev_env_loader="$(sed -n '/^load_repo_env_defaults()/,/^}/p' "${ROOT_REPO}/dev/stack.sh")"
release_env_loader="$(sed -n '/^load_repo_env_defaults()/,/^}/p' "${ROOT_REPO}/release/build.sh")"
if grep -qw SOURCELENS_GIT_REF <<<"${dev_env_loader}${release_env_loader}"; then
	printf 'ERROR: runtime .env must not select the bundled SourceLens build ref\n' >&2
	exit 1
fi

# CLI mirror options must reach HFL Compose builds even when SourceLens is skipped.
MIRROR_GITHUB_DOWNLOAD=""
MIRROR_GITHUB_TOKEN=""
MIRROR_DOCKER_DOWNLOAD=""
MIRROR_APT=""
OPT_GO_PROXY=""
OPT_GO_SUMDB=""
OPT_PIP_INDEX_URL=""
OPT_PIP_TRUSTED_HOST=""
OPT_NPM_REGISTRY=""
parse_common_option --github-download-mirror https://github-mirror.example.test
parse_common_option --github-token test-token
parse_common_option --docker-download-mirror docker-mirror.example.test
parse_common_option --apt-mirror https://apt-mirror.example.test
parse_common_option --go-proxy https://go-proxy.example.test,direct
parse_common_option --go-sumdb sumdb.example.test
parse_common_option --pip-index-url https://pip-mirror.example.test/simple
parse_common_option --pip-trusted-host pip-mirror.example.test
parse_common_option --npm-registry https://npm-mirror.example.test
parse_common_option --no-sourcelens
apply_mirror_env_defaults
prepare_sourcelens_dev 0

[[ "${WITH_SOURCELENS}" == "0" ]]
[[ "${GITHUB_DOWNLOAD_MIRROR}" == "https://github-mirror.example.test" ]]
[[ "${GITHUB_TOKEN}" == "test-token" ]]
[[ "${DOCKER_DOWNLOAD_MIRROR}" == "docker-mirror.example.test" ]]
[[ "${APT_MIRROR}" == "https://apt-mirror.example.test" ]]
[[ "${GOPROXY}" == "https://go-proxy.example.test,direct" ]]
[[ "${GOSUMDB}" == "sumdb.example.test" ]]
[[ "${PIP_INDEX_URL}" == "https://pip-mirror.example.test/simple" ]]
[[ "${PIP_TRUSTED_HOST}" == "pip-mirror.example.test" ]]
[[ "${NPM_REGISTRY}" == "https://npm-mirror.example.test" ]]

# SourceLens management must use its image virtualenv without a login shell.
# shellcheck source=../sourcelens/common.sh
source "${ROOT_REPO}/tools/sourcelens/common.sh"
sourcelens_log() { :; }
compose_calls=()
migration_status=0
sourcelens_dev_compose() {
	compose_calls+=("$*")
	if [[ "$*" == *"manage.py migrate --check"* ]]; then
		return "${migration_status}"
	fi
}

sourcelens_ensure_database_initialized
[[ " ${compose_calls[*]} " == *" exec -T --workdir /opt/backend api /opt/venv/bin/python manage.py migrate --check "* ]]
[[ " ${compose_calls[*]} " == *" exec -T --workdir /opt/backend api /opt/venv/bin/python manage.py collectstatic --noinput "* ]]
[[ " ${compose_calls[*]} " != *" sh -lc "* ]]

compose_calls=()
migration_status=1
sourcelens_ensure_database_initialized
[[ " ${compose_calls[*]} " == *" exec -T --workdir /opt/backend api /opt/venv/bin/python manage.py sourcelens_init --skip-collectstatic "* ]]

# The runtime metadata must be synchronized to the version that was actually built.
HFL_ROOT="${tmp}/hfl"
mkdir -p "${HFL_ROOT}"
printf '%s\n' \
	'SOURCELENS_GIT_REF=v0.4.0' \
	'FRONTEND_URL=https://127.0.0.1:11443' \
	'NO_PROXY=localhost' >"${HFL_ROOT}/.env"
SOURCELENS_GIT_REF=v0.20.0
sourcelens_configure_hfl_env >/dev/null
grep -Fx 'SOURCELENS_GIT_REF=v0.20.0' "${HFL_ROOT}/.env" >/dev/null

# Fresh runtime trees are created under a restrictive umask but remain readable
# by non-root processes inside the generated SourceLens containers.
runtime_root="${tmp}/runtime"
mkdir -p "${runtime_root}/deploy/postgresql/initdb.d"
printf '%s\n' 'SELECT 1;' >"${runtime_root}/deploy/postgresql/initdb.d/000-init.sql"
printf '%s\n' '#!/usr/bin/env bash' >"${runtime_root}/deploy/postgresql/initdb.d/001-init.sh"
printf '%s\n' 'services: {}' >"${runtime_root}/docker-compose.yml"
chmod -R 0700 "${runtime_root}"
sourcelens_normalize_dev_runtime_permissions "${runtime_root}"
[[ "$(stat -c '%a' "${runtime_root}/deploy/postgresql/initdb.d")" == "755" ]]
[[ "$(stat -c '%a' "${runtime_root}/deploy/postgresql/initdb.d/000-init.sql")" == "644" ]]
[[ "$(stat -c '%a' "${runtime_root}/deploy/postgresql/initdb.d/001-init.sh")" == "755" ]]
[[ "$(stat -c '%a' "${runtime_root}/docker-compose.yml")" == "644" ]]

grep -F 'find "${temporary}" -type d -exec chmod 0755 {} +' \
	"${ROOT_REPO}/website/build.sh" >/dev/null
grep -F 'find "${temporary}" -type f -exec chmod 0644 {} +' \
	"${ROOT_REPO}/website/build.sh" >/dev/null
grep -F 'chmod 0755 "${temporary}/runtime-config.sh"' \
	"${ROOT_REPO}/website/build.sh" >/dev/null

# Replacing the Website artifact directory leaves an existing Docker bind mount
# attached to the old inode. Recreate only Nginx when a rebuild occurred.
compose_calls=()
compose() { compose_calls+=("$*"); }
WEBSITE_ARTIFACT_REBUILT=0
refresh_website_nginx_mount
[[ "${#compose_calls[@]}" -eq 0 ]]

WEBSITE_ARTIFACT_REBUILT=1
refresh_website_nginx_mount
[[ "${#compose_calls[@]}" -eq 1 ]]
[[ "${compose_calls[0]}" == "up -d --no-deps --no-build --pull never --force-recreate nginx" ]]

cmd_up_body="$(sed -n '/^cmd_up()/,/^}/p' "${ROOT_REPO}/dev/stack.sh")"
cmd_restart_body="$(sed -n '/^cmd_restart()/,/^}/p' "${ROOT_REPO}/dev/stack.sh")"
grep -F 'refresh_website_nginx_mount' <<<"${cmd_up_body}" >/dev/null
grep -F 'refresh_website_nginx_mount' <<<"${cmd_restart_body}" >/dev/null

printf 'Development stack upgrade regression checks passed.\n'

#!/usr/bin/env bash
# One-shot local development stack: prepare host artifacts + agent publish + Docker Compose.
#
# Usage:
#   ./dev/stack.sh up
#   ./dev/stack.sh down
#   ./dev/stack.sh restart
#   ./dev/stack.sh restart --force
#
# up      — full prepare + build dependency images + start bind-mounted HFL source
# down    — docker compose down
# restart — full prepare with cache + recreate services when configuration changed
# restart --force — clean build caches, rebuild dependency images, force-recreate containers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../tools/lib/logging.sh
source "${ROOT}/tools/lib/logging.sh"
# shellcheck source=../tools/lib/env-file.sh
source "${ROOT}/tools/lib/env-file.sh"
# shellcheck source=../tools/dependencies/versions/kopia.env
source "${ROOT}/tools/dependencies/versions/kopia.env"

COMPOSE=()

MIRROR_GITHUB_DOWNLOAD=""
MIRROR_GITHUB_TOKEN=""
MIRROR_DOCKER_DOWNLOAD=""
MIRROR_APT=""
OPT_GO_PROXY=""
OPT_GO_SUMDB=""
OPT_PIP_INDEX_URL=""
OPT_PIP_TRUSTED_HOST=""
OPT_NPM_REGISTRY=""
WITH_SOURCELENS=""
SOURCELENS_GIT_REF="${SOURCELENS_GIT_REF:-}"
SOURCELENS_GIT_URL="${SOURCELENS_GIT_URL:-}"
HFL_ONLY_DOWN=0
LOG_FILE="${HFL_LOG_FILE:-}"
VERBOSE="${HFL_LOG_VERBOSE:-0}"
PRINT_CONFIG=0

usage() {
	cat <<'USAGE'
Usage: ./dev/stack.sh <command> [options]

Commands:
  up                 Prepare dependencies and start the hot-reload development stack
  down               Stop HyperFileLens + bundled SourceLens
  down --hfl-only    Stop HyperFileLens only; leave SourceLens running
  restart            Refresh dependencies/configuration and recreate changed services
  restart --force    Clean caches and rebuild development dependency images without cache

Prepare (up / restart) always includes:
  .env (create from .env.example if missing)
  TLS certs (self-signed if missing)
  Kopia .deb for the backend development dependency image
  backend source bind mount with automatic API/worker/scheduler restart
  frontend source bind mount with Vite HMR and persistent node_modules
  agent publish (full bundle) → data/media/agent-releases/
  SourceLens bundled mode (default): clone/update only as a build input, then run images
  SourceLens external mode: prepare the Gateway LensNode bundle without touching the external stack

SourceLens options (default: enabled for up/restart):
  --no-sourcelens                  Skip SourceLens clone/build/start
  --sourcelens-ref REF             SourceLens release tag in vX.Y.Z form
  --sourcelens-git-url URL         Override SourceLens repository URL (env: SOURCELENS_GIT_URL)

Mirror options (Kopia fetch + Agent publishing + SourceLens git clone; env fallback):
  --github-download-mirror URL     GitHub download mirror (env: GITHUB_DOWNLOAD_MIRROR)
  --github-token TOKEN             GitHub token for API/release fetch and private SourceLens clone (env: GITHUB_TOKEN)
  --docker-download-mirror URL     Docker Hub mirror for NAS ubuntu:24.04 (env: DOCKER_DOWNLOAD_MIRROR)
  --apt-mirror URL                 Ubuntu apt mirror for NAS container (env: APT_MIRROR)
  --ubuntu2404-arch ARCH           NAS deb arch for agent bundle: amd64 | arm64 | all (default: amd64)
  --kopia-version VERSION          Kopia version without v prefix (default: version pin file)
  --go-proxy URL                   Go module proxy (env: GOPROXY)
  --go-sumdb VALUE                 Go checksum database (env: GOSUMDB)
  --pip-index-url URL              Python package index (env: PIP_INDEX_URL)
  --pip-trusted-host HOST          Trusted pip host (env: PIP_TRUSTED_HOST)
  --npm-registry URL               npm registry (env: NPM_REGISTRY)

Output options:
  --log-file FILE                  Append runtime logs to FILE; normal output remains on stderr
  --verbose                        Enable debug logs
  --print-config                   Print effective non-secret configuration and exit
  -h, --help                       Show this help

Examples:
  ./dev/stack.sh up
  ./dev/stack.sh up --ubuntu2404-arch amd64
  ./dev/stack.sh down
  ./dev/stack.sh restart
  ./dev/stack.sh restart --force
  ./dev/stack.sh up --github-download-mirror https://ghfast.top --docker-download-mirror docker.m.daocloud.io --apt-mirror https://mirrors.tuna.tsinghua.edu.cn
USAGE
}

log() { hfl_log_info "$@"; }
warn() { hfl_log_warn "$@"; }
die() { hfl_die "$1" "${2:-1}"; }

require_value() {
	if [[ $# -lt 2 || -z "${2:-}" || "${2:0:1}" == "-" ]]; then
		die "${1} requires a value" 2
	fi
}

load_repo_env_defaults() {
	hfl_env_select_repo_file "${ROOT}"
	local key
	for key in \
		GITHUB_DOWNLOAD_MIRROR GITHUB_TOKEN DOCKER_DOWNLOAD_MIRROR \
		APT_MIRROR GOPROXY GOSUMDB PIP_INDEX_URL PIP_TRUSTED_HOST \
		NPM_REGISTRY BUILD_SOURCELENS SOURCELENS_GIT_REF SOURCELENS_GIT_URL; do
		hfl_env_load_default "${key}"
	done
}

apply_mirror_env_defaults() {
	MIRROR_GITHUB_DOWNLOAD="${MIRROR_GITHUB_DOWNLOAD:-${GITHUB_DOWNLOAD_MIRROR:-}}"
	MIRROR_GITHUB_TOKEN="${MIRROR_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
	MIRROR_DOCKER_DOWNLOAD="${MIRROR_DOCKER_DOWNLOAD:-${DOCKER_DOWNLOAD_MIRROR:-}}"
	MIRROR_APT="${MIRROR_APT:-${APT_MIRROR:-}}"
	OPT_GO_PROXY="${OPT_GO_PROXY:-${GOPROXY:-}}"
	OPT_GO_SUMDB="${OPT_GO_SUMDB:-${GOSUMDB:-}}"
	OPT_PIP_INDEX_URL="${OPT_PIP_INDEX_URL:-${PIP_INDEX_URL:-}}"
	OPT_PIP_TRUSTED_HOST="${OPT_PIP_TRUSTED_HOST:-${PIP_TRUSTED_HOST:-}}"
	OPT_NPM_REGISTRY="${OPT_NPM_REGISTRY:-${NPM_REGISTRY:-}}"
}

print_config() {
	local sourcelens_version
	apply_mirror_env_defaults
	apply_ubuntu2404_arch_default
	[[ "${SOURCELENS_GIT_REF}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]] \
		|| die "invalid SourceLens release ref: ${SOURCELENS_GIT_REF} (expected vX.Y.Z)" 2
	sourcelens_version="${BASH_REMATCH[1]}"
	cat <<EOF
command=${CMD:-<none>}
compose_file=${ROOT}/docker-compose.yml
data_dir=${ROOT}/data
source_check=${ROOT}/tools/quality/check-english-source.py
backend_source_mount=${ROOT}/src/backend:/opt/backend
frontend_source_mount=${ROOT}/src/frontend:/app
frontend_modules_volume=frontend-node-modules
with_sourcelens=${WITH_SOURCELENS}
sourcelens_runtime=image-only
sourcelens_ref=${SOURCELENS_GIT_REF}
sourcelens_version=${sourcelens_version}
sourcelens_git_url=${SOURCELENS_GIT_URL:-<default>}
sourcelens_upstream_image_prefix=${SOURCELENS_UPSTREAM_IMAGE_PREFIX}
sourcelens_image_registry=${SOURCELENS_IMAGE_REGISTRY:-<local>}
ubuntu2404_arch=${UBUNTU2404_ARCH}
kopia_version=${KOPIA_VERSION}
github_download_mirror=${MIRROR_GITHUB_DOWNLOAD:-<official>}
github_token=$(hfl_redact "${MIRROR_GITHUB_TOKEN}")
docker_download_mirror=${MIRROR_DOCKER_DOWNLOAD:-<official>}
apt_mirror=${MIRROR_APT:-<official>}
go_proxy=${OPT_GO_PROXY:-<official>}
go_sumdb=${OPT_GO_SUMDB:-<official>}
pip_index_url=${OPT_PIP_INDEX_URL:-<official>}
pip_trusted_host=${OPT_PIP_TRUSTED_HOST:-<unset>}
npm_registry=${OPT_NPM_REGISTRY:-<official>}
log_file=${LOG_FILE:-<none>}
verbose=${VERBOSE}
EOF
}

mirror_args() {
	local args=()
	[[ -n "${MIRROR_GITHUB_DOWNLOAD}" ]] && args+=(--github-download-mirror "${MIRROR_GITHUB_DOWNLOAD}")
	[[ -n "${MIRROR_GITHUB_TOKEN}" ]] && args+=(--github-token "${MIRROR_GITHUB_TOKEN}")
	[[ -n "${MIRROR_DOCKER_DOWNLOAD}" ]] && args+=(--docker-download-mirror "${MIRROR_DOCKER_DOWNLOAD}")
	[[ -n "${MIRROR_APT}" ]] && args+=(--apt-mirror "${MIRROR_APT}")
	((${#args[@]})) && printf '%s\0' "${args[@]}"
}

validate_ubuntu2404_arch() {
	case "${UBUNTU2404_ARCH}" in
	amd64 | arm64 | all) ;;
	*)
		die "invalid --ubuntu2404-arch ${UBUNTU2404_ARCH} (use amd64, arm64, or all)" 2
		;;
	esac
}

apply_ubuntu2404_arch_default() {
	UBUNTU2404_ARCH="${UBUNTU2404_ARCH:-amd64}"
	validate_ubuntu2404_arch
}

require_docker() {
	command -v docker >/dev/null 2>&1 || die "docker not found in PATH" 2
	docker info >/dev/null 2>&1 || die "docker daemon is not reachable"
	if docker compose version >/dev/null 2>&1; then
		COMPOSE=(docker compose)
	elif command -v docker-compose >/dev/null 2>&1; then
		COMPOSE=(docker-compose)
	else
		die "docker compose v2 (or docker-compose) not found" 2
	fi
}

compose() {
	(
		cd "${ROOT}"
		"${COMPOSE[@]}" --env-file "${ROOT}/.env" "$@"
	)
}

ensure_bridge_network() {
	local network="hyperfilelens-bridge"
	if docker network inspect "${network}" >/dev/null 2>&1; then
		return 0
	fi
	log "Creating shared bridge network ${network}"
	docker network create "${network}" >/dev/null
}

ensure_env_file() {
	local env_file="${ROOT}/.env"
	local example="${ROOT}/.env.example"
	[[ -f "${example}" ]] || die ".env.example not found"
	if [[ -f "${env_file}" ]]; then
		log ".env exists"
	else
		cp "${example}" "${env_file}"
		log "Created .env from .env.example"
	fi
}

ensure_tls_certs() {
	local cert="${ROOT}/deploy/nginx/certs/tls.crt"
	local key="${ROOT}/deploy/nginx/certs/tls.key"
	mkdir -p "${ROOT}/deploy/nginx/certs"
	if [[ -s "${cert}" && -s "${key}" ]]; then
		log "TLS certificates present"
		return 0
	fi
	command -v openssl >/dev/null 2>&1 || die "openssl required for dev TLS certificates"
	log "Generating self-signed TLS certificate"
	openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
		-keyout "${key}" \
		-out "${cert}" \
		-subj "/CN=localhost" \
		-addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1" 2>/dev/null
	chmod 600 "${key}"
}

ensure_data_dirs() {
	mkdir -p \
		"${ROOT}/data/postgresql" \
		"${ROOT}/data/redis" \
		"${ROOT}/data/logs" \
		"${ROOT}/data/lang-packs" \
		"${ROOT}/data/media/agent-releases" \
		"${ROOT}/data/media/enroll-bootstrap" \
		"${ROOT}/data/media/gateway-bootstrap" \
		"${ROOT}/data/media/snapshot-downloads" \
		"${ROOT}/data/staticfiles"
}

fetch_kopia_deb() {
	local force=$1
	local args=(--kopia-version "${KOPIA_VERSION}")
	[[ "${force}" -eq 1 ]] && args+=(--force)
	if [[ -n "${MIRROR_GITHUB_DOWNLOAD}" ]]; then
		args+=(--github-download-mirror "${MIRROR_GITHUB_DOWNLOAD}")
	fi
	log "Fetching Kopia deb (force=${force})"
	"${ROOT}/tools/dependencies/fetch-kopia-deb.sh" "${args[@]}"
}

# Remove artifacts left by older multilingual development builds.
strip_bundled_lang_packs() {
	local frontend=$1
	local removed=0
	local path
	for path in \
		"${frontend}/public/locales/installed.json" \
		"${frontend}/dist/locales/installed.json"; do
		if [[ -f "${path}" ]]; then
			rm -f "${path}"
			removed=1
		fi
	done
	shopt -s nullglob
	local -a message_bundles=(
		"${frontend}/public/locales/"*.messages.js
		"${frontend}/dist/locales/"*.messages.js
	)
	shopt -u nullglob
	if ((${#message_bundles[@]})); then
		rm -f "${message_bundles[@]}"
		removed=1
	fi
	if [[ "${removed}" -eq 1 ]]; then
		log "Removed generated language pack files from frontend public/dist"
	fi
}

prepare_sourcelens_dev() {
	local force=$1
	[[ "${WITH_SOURCELENS}" -eq 1 ]] || return 0
	local mode
	mode="$(read_env_value_or SOURCELENS_MODE bundled "${ROOT}/.env" | tr 'A-Z' 'a-z')"
	case "${mode}" in
	bundled | external) ;;
	*) die "invalid SOURCELENS_MODE=${mode} (use bundled or external)" ;;
	esac
	local args
	if [[ "${mode}" == "bundled" ]]; then
		args=(up)
	else
		args=(gateway)
	fi
	[[ "${force}" -eq 1 ]] && args+=(--force-build)
	[[ -n "${SOURCELENS_GIT_REF}" ]] && args+=(--sourcelens-ref "${SOURCELENS_GIT_REF}")
	[[ -n "${SOURCELENS_GIT_URL}" ]] && args+=(--sourcelens-git-url "${SOURCELENS_GIT_URL}")
	[[ -n "${MIRROR_APT}" ]] && export APT_MIRROR="${MIRROR_APT}"
	[[ -n "${MIRROR_DOCKER_DOWNLOAD}" ]] && export DOCKER_DOWNLOAD_MIRROR="${MIRROR_DOCKER_DOWNLOAD}"
	if [[ -n "${MIRROR_GITHUB_TOKEN}" ]]; then
		export GITHUB_TOKEN="${MIRROR_GITHUB_TOKEN}"
	fi
	[[ -n "${OPT_PIP_INDEX_URL}" ]] && export PIP_INDEX_URL="${OPT_PIP_INDEX_URL}"
	[[ -n "${OPT_PIP_TRUSTED_HOST}" ]] && export PIP_TRUSTED_HOST="${OPT_PIP_TRUSTED_HOST}"
	[[ -n "${OPT_NPM_REGISTRY}" ]] && export NPM_REGISTRY="${OPT_NPM_REGISTRY}"
	export SOURCELENS_CONSOLE_BIND_ADDRESS SOURCELENS_CONSOLE_PORT SOURCELENS_NGINX_HTTPS_PORT
	SOURCELENS_CONSOLE_BIND_ADDRESS="$(read_env_value_or SOURCELENS_CONSOLE_BIND_ADDRESS 0.0.0.0 "${ROOT}/.env")"
	SOURCELENS_CONSOLE_PORT="$(read_env_value_or SOURCELENS_CONSOLE_PORT 10446 "${ROOT}/.env")"
	SOURCELENS_NGINX_HTTPS_PORT="${SOURCELENS_CONSOLE_PORT}"
	log "Preparing SourceLens ${mode} integration (force_build=${force})"
	"${ROOT}/dev/sourcelens.sh" "${args[@]}"
}

stop_sourcelens_dev() {
	[[ "${WITH_SOURCELENS}" -eq 1 ]] || return 0
	[[ "${HFL_ONLY_DOWN}" -eq 1 ]] && return 0
	[[ "$(read_env_value_or SOURCELENS_MODE bundled "${ROOT}/.env" | tr 'A-Z' 'a-z')" == "bundled" ]] || return 0
	if [[ -x "${ROOT}/dev/sourcelens.sh" ]]; then
		log "Stopping SourceLens dev stack"
		"${ROOT}/dev/sourcelens.sh" down || true
	fi
}

publish_agent() {
	local force=$1
	if [[ "${force}" -eq 1 ]]; then
		log "Cleaning Agent build output"
		"${ROOT}/src/agent/scripts/build.sh" --clean
	fi
	local args=(--bundle all --ubuntu2404-arch "${UBUNTU2404_ARCH}")
	args+=(--kopia-version "${KOPIA_VERSION}")
	[[ "${force}" -eq 1 ]] && args+=(--force-fetch)
	local mirror
	while IFS= read -r -d '' mirror; do
		args+=("${mirror}")
	done < <(mirror_args || true)
	[[ -n "${OPT_GO_PROXY}" ]] && args+=(--go-proxy "${OPT_GO_PROXY}")
	[[ -n "${OPT_GO_SUMDB}" ]] && args+=(--go-sumdb "${OPT_GO_SUMDB}")
	log "Publishing Agent packages (bundle=all, ubuntu2404-arch=${UBUNTU2404_ARCH}, force_fetch=${force})"
	"${ROOT}/tools/agent/publish.sh" "${args[@]}"
}

prepare_dev() {
	local force=$1
	apply_mirror_env_defaults
	apply_ubuntu2404_arch_default
	command -v python3 >/dev/null 2>&1 || die "python3 not found"
	log "Checking English-only public source trees"
	python3 "${ROOT}/tools/quality/check-english-source.py"
	require_docker
	ensure_env_file
	ensure_tls_certs
	ensure_data_dirs
	fetch_kopia_deb "${force}"
	strip_bundled_lang_packs "${ROOT}/src/frontend"
	publish_agent "${force}"
}

read_env_value() {
	local key=$1
	local env_file="${2:-${ROOT}/.env}"
	[[ -f "${env_file}" ]] || return 0
	grep -E "^${key}=" "${env_file}" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'
}

read_env_value_or() {
	local key=$1
	local default=$2
	local env_file="${3:-${ROOT}/.env}"
	local val
	val="$(read_env_value "${key}" "${env_file}")"
	if [[ -n "${val}" ]]; then
		printf '%s' "${val}"
	else
		printf '%s' "${default}"
	fi
}

print_urls() {
	local env_file="${ROOT}/.env"
	local sl_env="${ROOT}/data/sourcelens/config/.env"
	local seed seed_email seed_pass seed_org sourcelens_mode sourcelens_console_port
	local tenant_bind tenant_port admin_bind admin_port sourcelens_console_bind
	local pg_user pg_pass pg_db frontend_url lens_base lens_gw lens_user lens_pass
	local sl_user sl_email sl_pass

	seed="$(read_env_value_or SEED_INITIAL_DATA 1 "${env_file}")"
	seed_email="$(read_env_value_or SEED_ADMIN_EMAIL admin@hyperfilelens.com "${env_file}")"
	seed_pass="$(read_env_value_or SEED_ADMIN_PASSWORD 'Admin@123' "${env_file}")"
	seed_org="$(read_env_value_or SEED_ORG_NAME HyperFileLens "${env_file}")"
	sourcelens_mode="$(read_env_value_or SOURCELENS_MODE bundled "${env_file}" | tr 'A-Z' 'a-z')"
	tenant_bind="$(read_env_value_or HFL_TENANT_BIND_ADDRESS 0.0.0.0 "${env_file}")"
	tenant_port="$(read_env_value_or HFL_TENANT_PORT 10443 "${env_file}")"
	admin_bind="$(read_env_value_or HFL_ADMIN_BIND_ADDRESS 0.0.0.0 "${env_file}")"
	admin_port="$(read_env_value_or HFL_ADMIN_PORT 10444 "${env_file}")"
	sourcelens_console_bind="$(read_env_value_or SOURCELENS_CONSOLE_BIND_ADDRESS 0.0.0.0 "${env_file}")"
	sourcelens_console_port="$(read_env_value_or SOURCELENS_CONSOLE_PORT 10446 "${env_file}")"
	pg_user="$(read_env_value_or POSTGRES_USER postgres "${env_file}")"
	pg_pass="$(read_env_value_or POSTGRES_PASSWORD postgres "${env_file}")"
	pg_db="$(read_env_value_or POSTGRES_DB hyperfilelens "${env_file}")"
	frontend_url="$(read_env_value_or FRONTEND_URL "https://127.0.0.1:${tenant_port}" "${env_file}")"
	lens_base="$(read_env_value_or LENS_BASE_URL http://sourcelens-nginx "${env_file}")"
	if [[ "${sourcelens_mode}" == "external" ]]; then
		lens_gw="$(read_env_value_or LENS_GATEWAY_BASE_URL "${lens_base}" "${env_file}")"
	else
		lens_gw="$(read_env_value_or LENS_GATEWAY_BASE_URL "${frontend_url%/}/sourcelens" "${env_file}")"
	fi
	lens_user="$(read_env_value_or LENS_BRIDGE_USERNAME admin "${env_file}")"
	lens_pass="$(read_env_value_or LENS_BRIDGE_PASSWORD adminpassword "${env_file}")"

	cat <<EOF

======================================================================
  Dev stack ready
======================================================================

HyperFileLens
  Tenant           https://localhost:${tenant_port}/  (${tenant_bind})
  Platform Ops     https://localhost:${admin_port}/  (${admin_bind})
  Django Admin     https://localhost:${admin_port}/admin/
  API / Swagger    https://localhost:${tenant_port}/swagger
EOF

	cat <<EOF

  Login (tenant)   ${seed_email} / ${seed_pass}
  Organization     ${seed_org}
EOF

	if [[ "${seed}" == "1" ]]; then
		echo "  Seeding          enabled (worker creates admin on first startup)"
	else
		echo "  Seeding          disabled (SEED_INITIAL_DATA=${seed})"
	fi

	cat <<EOF
  Postgres         ${pg_user}/${pg_pass} @ postgres:5432 / ${pg_db} (private)
  Config           ${env_file#${ROOT}/}

Agent / Gateway bootstrap
  Agent releases   https://localhost:${tenant_port}/media/agent-releases/
  LensNode bundle  https://localhost:${tenant_port}/media/gateway-bootstrap/lensnode-image-linux-amd64.tar.gz
EOF

	if [[ "${WITH_SOURCELENS}" -eq 1 && "${sourcelens_mode}" == "bundled" ]]; then
		if [[ -f "${sl_env}" ]]; then
			sl_user="$(read_env_value_or DJANGO_SUPERUSER_USERNAME admin "${sl_env}")"
			sl_email="$(read_env_value_or DJANGO_SUPERUSER_EMAIL admin@example.com "${sl_env}")"
			sl_pass="$(read_env_value_or DJANGO_SUPERUSER_PASSWORD adminpassword "${sl_env}")"
		else
			sl_user=admin
			sl_email=admin@example.com
			sl_pass=adminpassword
		fi

		cat <<EOF

SourceLens
  Console          https://localhost:${sourcelens_console_port}/  (${sourcelens_console_bind})
  Network          hyperfilelens-bridge (private)
  Gateway API      https://localhost:${tenant_port}/sourcelens/api/
  Gateway WSS      wss://localhost:${tenant_port}/sourcelens/ws/lens/lensnodes/
  Login            ${sl_user} / ${sl_pass}  (email: ${sl_email})

  HFL bridge       ${lens_base}
  Gateway URL      ${lens_gw}
  Bridge account   ${lens_user} / ${lens_pass}  (LENS_BRIDGE_* in .env)
EOF
		if [[ -f "${sl_env}" ]]; then
			echo "  SL config        data/sourcelens/config/.env"
		fi
	elif [[ "${WITH_SOURCELENS}" -eq 1 && "${sourcelens_mode}" == "external" ]]; then
		cat <<EOF

SourceLens
  Mode             external (not managed by stack.sh)
  Base URL         ${lens_base}
  Gateway URL      ${lens_gw}
  Bridge account   ${lens_user} / ${lens_pass}  (LENS_BRIDGE_* in .env)
EOF
	fi

	cat <<EOF

Notes
  - HFL backend and frontend source changes reload automatically; no stack restart is required
  - SourceLens always runs from images; its source cache is never mounted into a container
  - Self-signed TLS: accept the browser warning for localhost
  - Change default passwords after first login
  - Stop stack: ./dev/stack.sh down
======================================================================
EOF
}

cmd_up() {
	apply_mirror_env_defaults
	ensure_env_file
	require_docker
	ensure_bridge_network
	prepare_sourcelens_dev 0
	prepare_dev 0
	log "Starting hot-reload HFL stack: docker compose up -d --build"
	compose up -d --build --remove-orphans
	print_urls
}

cmd_down() {
	require_docker
	[[ -f "${ROOT}/.env" ]] || warn ".env missing; using compose defaults where applicable"
	log "Stopping stack: docker compose down"
	compose down
	stop_sourcelens_dev
	log "Stopped"
}

cmd_restart() {
	local force=$1

	apply_mirror_env_defaults
	ensure_env_file
	require_docker
	ensure_bridge_network
	prepare_sourcelens_dev "${force}"
	prepare_dev "${force}"

	if [[ "${force}" -eq 1 ]]; then
		log "Force restart: rebuild development dependency images without cache"
		compose down || true
		compose build --no-cache worker ui
		compose up -d --force-recreate --remove-orphans
	else
		log "Refreshing development dependency images and recreating changed services"
		compose up -d --build --remove-orphans
	fi
	print_urls
}

parse_common_option() {
	case "$1" in
	--github-download-mirror)
		require_value "$1" "${2:-}"
		MIRROR_GITHUB_DOWNLOAD="$2"
		return 0
		;;
	--github-token)
		require_value "$1" "${2:-}"
		MIRROR_GITHUB_TOKEN="$2"
		return 0
		;;
	--docker-download-mirror)
		require_value "$1" "${2:-}"
		MIRROR_DOCKER_DOWNLOAD="$2"
		return 0
		;;
	--apt-mirror)
		require_value "$1" "${2:-}"
		MIRROR_APT="$2"
		return 0
		;;
	--ubuntu2404-arch)
		require_value "$1" "${2:-}"
		UBUNTU2404_ARCH="$2"
		return 0
		;;
	--kopia-version)
		require_value "$1" "${2:-}"
		KOPIA_VERSION="${2#v}"
		[[ "${KOPIA_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
			|| die "invalid Kopia version: ${KOPIA_VERSION}" 2
		export KOPIA_VERSION
		return 0
		;;
	--no-sourcelens)
		WITH_SOURCELENS=0
		return 0
		;;
	--sourcelens-ref)
		require_value "$1" "${2:-}"
		SOURCELENS_GIT_REF="$2"
		return 0
		;;
	--sourcelens-git-url)
		require_value "$1" "${2:-}"
		SOURCELENS_GIT_URL="$2"
		return 0
		;;
	--go-proxy)
		require_value "$1" "${2:-}"
		OPT_GO_PROXY="$2"
		return 0
		;;
	--go-sumdb)
		require_value "$1" "${2:-}"
		OPT_GO_SUMDB="$2"
		return 0
		;;
	--pip-index-url)
		require_value "$1" "${2:-}"
		OPT_PIP_INDEX_URL="$2"
		return 0
		;;
	--pip-trusted-host)
		require_value "$1" "${2:-}"
		OPT_PIP_TRUSTED_HOST="$2"
		return 0
		;;
	--npm-registry)
		require_value "$1" "${2:-}"
		OPT_NPM_REGISTRY="$2"
		return 0
		;;
	--hfl-only)
		HFL_ONLY_DOWN=1
		return 0
		;;
	esac
	return 1
}

main() {
	[[ $# -ge 1 ]] || {
		usage
		exit 2
	}
	load_repo_env_defaults
	# shellcheck source=../tools/sourcelens/defaults.env
	source "${ROOT}/tools/sourcelens/defaults.env"
	WITH_SOURCELENS="${BUILD_SOURCELENS:-1}"

	local cmd=""
	local restart_force=0

	while [[ $# -gt 0 ]]; do
		case "$1" in
		up | down | restart)
			[[ -z "${cmd}" ]] || die "multiple commands specified"
			cmd="$1"
			shift
			;;
		--force)
			restart_force=1
			shift
			;;
		-h | --help | help)
			usage
			exit 0
			;;
		--print-config)
			PRINT_CONFIG=1
			shift
			;;
		--verbose)
			VERBOSE=1
			shift
			;;
		--log-file)
			require_value "$1" "${2:-}"
			LOG_FILE="$2"
			shift 2
			;;
		--github-download-mirror | --github-token | --docker-download-mirror | --apt-mirror | --ubuntu2404-arch | --kopia-version | --sourcelens-ref | --sourcelens-git-url | --go-proxy | --go-sumdb | --pip-index-url | --pip-trusted-host | --npm-registry | --no-sourcelens | --hfl-only)
			parse_common_option "$@" || die "failed to parse option: $1"
			if [[ "$1" == "--no-sourcelens" || "$1" == "--hfl-only" ]]; then
				shift
			else
				shift 2
			fi
			;;
		*)
			die "unknown argument: $1 (try --help)" 2
			;;
		esac
	done
	CMD="${cmd}"
	hfl_logging_configure dev "${LOG_FILE}" "${VERBOSE}"
	if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
		print_config
		return 0
	fi
	hfl_logging_start

	[[ -n "${cmd}" ]] || {
		usage
		exit 2
	}

	if [[ "${restart_force}" -eq 1 && "${cmd}" != "restart" ]]; then
		die "--force is only valid with restart" 2
	fi
	if [[ "${HFL_ONLY_DOWN}" -eq 1 && "${cmd}" != "down" ]]; then
		die "--hfl-only is only valid with down" 2
	fi

	case "${cmd}" in
	up) cmd_up ;;
	down) cmd_down ;;
	restart) cmd_restart "${restart_force}" ;;
	esac
}

hfl_logging_configure dev
trap 'rc=$?; hfl_logging_finish "${rc}"' EXIT
trap 'exit 130' INT TERM
main "$@"

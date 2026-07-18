#!/usr/bin/env bash
# SourceLens LensNode sidecar install for HyperFileLens Data Gateways.
# Invoked by hfl-enroll gateway-install after agent registration.
set -euo pipefail

ENV_FILE="${HFL_LENS_ENV_FILE:-/etc/hyperfilelens/lensnode.env}"
COMPOSE_DIR="/etc/hyperfilelens/lensnode"
COMPOSE_PROJECT="sourcelens"
DEFAULT_LENSNODE_IMAGE="${LENSNODE_IMAGE:-sourcelens-lensnode:latest}"

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_step() {
	printf '[%s] [STEP ] %s\n' "$(hfl_now)" "$1"
}

hfl_ok() {
	printf '[%s] [ OK  ] %s\n' "$(hfl_now)" "$1"
}

hfl_warn() {
	printf '[%s] [WARN ] %s\n' "$(hfl_now)" "$1" >&2
}

hfl_fail() {
	printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$1" >&2
	exit "${2:-1}"
}

if [[ "$(id -u)" -ne 0 ]]; then
	hfl_fail "Administrator privileges are required." 1
fi

if [[ "${HFL_FORCE_SIDECAR_INSTALL:-0}" != "1" ]] && command -v docker >/dev/null 2>&1; then
	if docker ps --format '{{.Names}}' 2>/dev/null | grep -Eq '^sourcelens[-_]lensnode[-_]1$'; then
		hfl_ok "LensNode sidecar (sourcelens-lensnode-1) is already running."
		printf '[%s] [INFO ] Set HFL_FORCE_SIDECAR_INSTALL=1 to force reinstall.\n' "$(hfl_now)"
		exit 0
	fi
fi

if [[ ! -f "${ENV_FILE}" ]]; then
	hfl_fail "Missing ${ENV_FILE} (run hfl-enroll gateway-install first)." 2
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

for var in LENS_BASE_URL LENSNODE_TOKEN LENSNODE_UUID HFL_WORKSPACE_ROOT; do
	if [[ -z "${!var:-}" ]]; then
		hfl_fail "Missing ${var} in ${ENV_FILE}." 2
	fi
done

# host.docker.internal only resolves inside Docker; gateway install runs on the host OS.
resolve_lens_host_url() {
	local url="$1"
	url="${url//host.docker.internal/127.0.0.1}"
	printf '%s' "$url"
}

# LensNode containers reach SourceLens on the host via host.docker.internal.
resolve_lens_container_url() {
	local url="$1"
	if [[ "$url" == *127.0.0.1* || "$url" == *localhost* ]]; then
		url="${url//127.0.0.1/host.docker.internal}"
		url="${url//localhost/host.docker.internal}"
	fi
	printf '%s' "$url"
}

lens_url_needs_extra_hosts() {
	local url="$1"
	[[ "$url" == *host.docker.internal* ]]
}

LENS_HOST_URL="$(resolve_lens_host_url "${LENS_BASE_URL}")"
LENS_CONTAINER_URL="$(resolve_lens_container_url "${LENS_BASE_URL}")"
LENSNODE_NAME="${LENSNODE_NAME:-hfl-gw-sidecar}"
HFL_INSECURE_TLS="${HFL_INSECURE_TLS:-1}"

CURL_TLS=(-k)
if [[ "${HFL_INSECURE_TLS}" == "0" ]]; then
	CURL_TLS=()
fi

hfl_step "Verifying SourceLens connectivity at ${LENS_HOST_URL}."
curl "${CURL_TLS[@]}" -fsSL "${LENS_HOST_URL%/}/health" >/dev/null
hfl_ok "SourceLens health check passed."

hfl_step "Creating workspace ${HFL_WORKSPACE_ROOT}."
mkdir -p "${HFL_WORKSPACE_ROOT}"

mkdir -p "${COMPOSE_DIR}"

resolve_lensnode_image() {
	local candidate
	if [[ -n "${LENSNODE_IMAGE:-}" ]] && docker image inspect "${LENSNODE_IMAGE}" >/dev/null 2>&1; then
		printf '%s' "${LENSNODE_IMAGE}"
		return 0
	fi
	if command -v docker >/dev/null 2>&1; then
		for candidate in \
			sourcelens-lensnode:latest \
			oneprocloud/sourcelens-lensnode:latest \
			"${DEFAULT_LENSNODE_IMAGE}"; do
			if docker image inspect "${candidate}" >/dev/null 2>&1; then
				printf '%s' "${candidate}"
				return 0
			fi
		done
	fi
	printf '%s' "${DEFAULT_LENSNODE_IMAGE}"
}

install_docker_sidecar() {
	local image="$1"
	local ssl_verify="${LENSNODE_SSL_VERIFY:-}"
	if [[ -z "${ssl_verify}" ]]; then
		if [[ "${HFL_INSECURE_TLS}" == "1" ]]; then
			ssl_verify="false"
		else
			ssl_verify="true"
		fi
	fi
	if ! docker image inspect "${image}" >/dev/null 2>&1; then
		hfl_fail "LensNode image ${image} is not available locally. Load the bundled lensnode-image archive before running gateway-install." 3
	fi
	hfl_step "Installing LensNode sidecar via Docker (${image})."
	EXTRA_HOSTS_BLOCK=""
	if lens_url_needs_extra_hosts "${LENS_CONTAINER_URL}"; then
		EXTRA_HOSTS_BLOCK=$'    extra_hosts:\n      - "host.docker.internal:host-gateway"\n'
	fi
	cat >"${COMPOSE_DIR}/docker-compose.yml" <<EOF
name: ${COMPOSE_PROJECT}

services:
  lensnode:
    image: ${image}
    restart: unless-stopped
${EXTRA_HOSTS_BLOCK}    environment:
      LENSNODE_NAME: ${LENSNODE_NAME}
      LENSNODE_TOKEN: ${LENSNODE_TOKEN}
      LENSNODE_SERVER_URL: ${LENS_CONTAINER_URL}
      LENSNODE_WORKSPACE_PATH: ${HFL_WORKSPACE_ROOT}
      HFL_INSECURE_TLS: "${HFL_INSECURE_TLS}"
      LENSNODE_INSECURE_TLS: "${HFL_INSECURE_TLS}"
      LENSNODE_SSL_VERIFY: "${ssl_verify}"
    volumes:
      - ${HFL_WORKSPACE_ROOT}:${HFL_WORKSPACE_ROOT}
EOF
	if docker compose version >/dev/null 2>&1; then
		# Remove pre-normalization explicit container names during upgrades.
		docker rm -f hfl-lensnode-sidecar hfl-gw-lensnode 2>/dev/null || true
		(
			cd "${COMPOSE_DIR}"
			docker compose -p "${COMPOSE_PROJECT}" up -d --pull never
		)
	elif command -v docker-compose >/dev/null 2>&1; then
		# Remove pre-normalization explicit container names during upgrades.
		docker rm -f hfl-lensnode-sidecar hfl-gw-lensnode 2>/dev/null || true
		(
			cd "${COMPOSE_DIR}"
			docker-compose -p "${COMPOSE_PROJECT}" up -d --pull never
		)
	else
		hfl_fail "docker compose is required when using a LensNode container image." 3
	fi
	hfl_ok "LensNode sidecar container started."
}

SIDECAR_MODE=""
if ! command -v docker >/dev/null 2>&1; then
	hfl_fail "Docker is required to install the LensNode sidecar." 3
fi
RESOLVED_IMAGE="$(resolve_lensnode_image)"
install_docker_sidecar "${RESOLVED_IMAGE}"
SIDECAR_MODE="docker"

hfl_ok "LensNode sidecar install completed (${SIDECAR_MODE})."

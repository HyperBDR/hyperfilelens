#!/usr/bin/env bash
# HyperFileLens Data Gateway enrollment bootstrap (Linux only).
# Rendered by GET /enrollment/bootstrap-gateway — installs agent + SourceLens sidecar.
set -euo pipefail

export HFL_ORG_KEY="__HFL_ORG_KEY__"
export HFL_NODE_ROLE="gateway"
export HFL_NODE_TOKEN="__HFL_NODE_TOKEN__"
export HFL_API_BASE="__HFL_API_BASE__"
export HFL_WSS_URL="__HFL_WSS_URL__"
export HFL_INSECURE_TLS="__HFL_INSECURE_TLS__"

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_step() {
	printf '[%s] [STEP ] %s\n' "$(hfl_now)" "$1"
}

hfl_ok() {
	printf '[%s] [ OK  ] %s\n' "$(hfl_now)" "$1"
}

hfl_fail() {
	printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$1" >&2
	exit "${2:-1}"
}

hfl_build_enroll_args() {
	HFL_ENROLL_ARGS=()
	local has_yes=0
	local arg
	for arg in "$@"; do
		case "${arg}" in
		--yes | -y) has_yes=1 ;;
		esac
		HFL_ENROLL_ARGS+=("${arg}")
	done
	if [[ "${HFL_ASSUME_YES:-1}" != "0" && "${has_yes}" -eq 0 ]]; then
		HFL_ENROLL_ARGS=(--yes "$@")
	fi
}

hfl_sourcelens_health_retry() {
	local url="$1"
	local label="$2"
	local attempts="${3:-3}"
	local delay="${4:-5}"
	local n=1
	local response=""
	while [[ "${n}" -le "${attempts}" ]]; do
		if response="$(curl "${CURL_TLS[@]}" -fsSL "${url}" 2>/dev/null)" \
			&& grep -Eq '"health"[[:space:]]*:[[:space:]]*"OK"' <<<"${response}"; then
			return 0
		fi
		if [[ "${n}" -lt "${attempts}" ]]; then
			printf '[%s] [WARN ] %s not ready (attempt %s/%s); retrying in %ss.\n' \
				"$(hfl_now)" "${label}" "${n}" "${attempts}" "${delay}" >&2
			sleep "${delay}"
		fi
		n=$((n + 1))
	done
	hfl_fail "${label} unreachable or unhealthy at ${url} after ${attempts} attempts." 3
}

MIN_ENGINE_VERSION="${HFL_DOCKER_MIN_ENGINE:-24.0.0}"
MIN_COMPOSE_VERSION="${HFL_COMPOSE_MIN_VERSION:-2.20.0}"

docker_engine_version() {
	docker version --format '{{.Server.Version}}' 2>/dev/null || true
}

docker_compose_version() {
	if docker compose version >/dev/null 2>&1; then
		docker compose version --short 2>/dev/null || docker compose version 2>/dev/null | awk '{print $NF}'
		return 0
	fi
	printf ''
}

docker_version_ge() {
	local have="$1"
	local want="$2"
	[[ -n "${have}" && -n "${want}" ]] || return 1
	dpkg --compare-versions "${have#v}" ge "${want#v}" 2>/dev/null
}

docker_runtime_ready() {
	local min_version="${1:-${MIN_ENGINE_VERSION}}"
	command -v docker >/dev/null 2>&1 || return 1
	docker info >/dev/null 2>&1 || return 1
	local engine compose
	engine="$(docker_engine_version)"
	[[ -n "${engine}" ]] || return 1
	docker_version_ge "${engine}" "${min_version}" || return 1
	compose="$(docker_compose_version)"
	[[ -n "${compose}" ]] || return 1
	docker_version_ge "${compose}" "${MIN_COMPOSE_VERSION}" || return 1
	return 0
}

docker_existing_not_ready_reason() {
	local min_version="${1:-${MIN_ENGINE_VERSION}}"
	local engine compose
	engine="$(docker_engine_version)"
	compose="$(docker_compose_version)"
	if ! docker info >/dev/null 2>&1; then
		printf '%s' "Docker daemon is not running (try: sudo systemctl start docker)"
		return 0
	fi
	if [[ -z "${engine}" ]]; then
		printf '%s' "Docker engine version could not be determined"
		return 0
	fi
	if ! docker_version_ge "${engine}" "${min_version}"; then
		printf '%s' "Docker engine ${engine} is below required ${min_version}"
		return 0
	fi
	if [[ -z "${compose}" ]]; then
		printf '%s' "Docker Compose v2 is missing or below ${MIN_COMPOSE_VERSION}"
		return 0
	fi
	printf '%s' "Docker is installed but not ready"
}

ensure_docker_for_gateway() {
	hfl_step "Checking Docker environment."
	if docker_runtime_ready "${MIN_ENGINE_VERSION}"; then
		hfl_ok "Using existing Docker (engine $(docker_engine_version), compose $(docker_compose_version))."
		return 0
	fi
	if command -v docker >/dev/null 2>&1; then
		hfl_fail "$(docker_existing_not_ready_reason "${MIN_ENGINE_VERSION}"). HFL never repairs or replaces an existing Docker installation." 3
	fi
	hfl_step "Installing Docker CE from console offline bundle."
	docker_script="${TMPDIR:-/tmp}/hfl-install-docker-$$"
	curl "${CURL_TLS[@]}" -fsSL "${HFL_GATEWAY_BOOTSTRAP_BASE}/gateway-install-docker-ubuntu-amd64.sh" -o "${docker_script}"
	chmod +x "${docker_script}"
	HFL_GATEWAY_BOOTSTRAP_BASE="${HFL_GATEWAY_BOOTSTRAP_BASE}" HFL_API_BASE="${HFL_API_BASE}" \
	HFL_INSECURE_TLS="${HFL_INSECURE_TLS}" HFL_DOCKER_MIN_ENGINE="${MIN_ENGINE_VERSION}" \
		HFL_COMPOSE_MIN_VERSION="${MIN_COMPOSE_VERSION}" \
		bash "${docker_script}"
	rm -f "${docker_script}"
	docker_runtime_ready "${MIN_ENGINE_VERSION}" \
		|| hfl_fail "Docker is not ready after offline install." 5
	hfl_ok "Docker CE ready (engine $(docker_engine_version), compose $(docker_compose_version))."
}

CURL_TLS=(-k)
if [[ "${HFL_INSECURE_TLS}" == "0" ]]; then
	CURL_TLS=()
fi

if ! command -v curl >/dev/null 2>&1; then
	hfl_fail "curl is required but not installed." 2
fi

RAW_ARCH="$(uname -m)"
case "${RAW_ARCH}" in
x86_64 | amd64) HFL_ARCH=amd64 ;;
aarch64 | arm64) HFL_ARCH=arm64 ;;
*)
	hfl_fail "Unsupported architecture ${RAW_ARCH} (gateway install supports amd64 only today)." 4
	;;
esac

if [[ "${HFL_ARCH}" != "amd64" ]]; then
	hfl_fail "Data Gateway full install (Docker + LensNode) requires amd64 (current: ${RAW_ARCH})." 4
fi

if [[ "$(id -u)" -ne 0 ]]; then
	hfl_fail "Administrator privileges are required. Re-run with sudo." 1
fi

HFL_GATEWAY_BOOTSTRAP_BASE="${HFL_API_BASE}/media/gateway-bootstrap"
CONSOLE_BASE="${HFL_API_BASE%/}"

hfl_step "Checking console connectivity."
curl "${CURL_TLS[@]}" -fsSL "${CONSOLE_BASE}/health" >/dev/null
hfl_ok "Console is reachable."

hfl_step "Checking SourceLens health via console proxy."
hfl_sourcelens_health_retry "${CONSOLE_BASE}/sourcelens/health" "SourceLens health" 3 5
hfl_ok "SourceLens is reachable."

ensure_docker_for_gateway

BIN="${TMPDIR:-/tmp}/hfl-enroll-$$"
cleanup() { rm -f "${BIN}"; }
trap cleanup EXIT

hfl_step "Downloading HyperFileLens enrollment helper."
curl "${CURL_TLS[@]}" -fsSL "${HFL_API_BASE}/media/enroll-bootstrap/hfl-enroll-linux-${HFL_ARCH}" -o "${BIN}"
chmod +x "${BIN}"
# Do not exec: trap EXIT must run after gateway-install so /tmp/hfl-enroll-* is removed.
hfl_build_enroll_args "$@"
"${BIN}" gateway-install "${HFL_ENROLL_ARGS[@]}"

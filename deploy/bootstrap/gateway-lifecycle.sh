#!/usr/bin/env bash
# Data Gateway lifecycle helpers (sidecar upgrade/uninstall).
# Published under /media/gateway-bootstrap/; invoked by hfl-enroll or detached agent scripts.
set -euo pipefail

ENV_FILE="${HFL_AGENT_ENV_FILE:-/var/lib/hyperfilelens-agent/agent.env}"
LENS_ENV_FILE="${HFL_LENS_ENV_FILE:-/etc/hyperfilelens/lensnode.env}"
COMPOSE_DIR="/etc/hyperfilelens/lensnode"
GATEWAY_BOOTSTRAP_BASE=""
HFL_API_BASE=""
HFL_ORG_KEY=""
HFL_NODE_TOKEN=""
HFL_NODE_ID=""
HFL_INSECURE_TLS="${HFL_INSECURE_TLS:-1}"
PURGE_ALL=0

LENSNODE_IMAGE_ARCHIVE="lensnode-image-linux-amd64.tar.gz"
SIDECAR_INSTALL_SCRIPT="gateway-install-lensnode-sidecar.sh"
COMPOSE_PROJECT="sourcelens"
DEFAULT_LENSNODE_IMAGE="sourcelens-lensnode:latest"

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_log() {
	printf '[%s] [INFO ] %s\n' "$(hfl_now)" "$*" >&2
}

hfl_fail() {
	printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$*" >&2
	exit "${2:-1}"
}

curl_tls=(-k)
if [[ "${HFL_INSECURE_TLS}" == "0" ]]; then
	curl_tls=()
fi

usage() {
	cat <<'USAGE'
Usage: gateway-lifecycle.sh <command> [options]

Commands:
  upgrade-sidecar       Reload LensNode image and restart sourcelens-lensnode-1
  uninstall-sidecar     Stop sidecar; use --purge-all to remove config, workspace, images

Options:
  --purge-all           Remove lensnode.env, compose dir, workspace, and local images
USAGE
}

read_env_value() {
	local file=$1 key=$2
	grep -E "^${key}=" "${file}" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r' | sed 's/^["'\'' ]//; s/["'\'' ]$//'
}

load_agent_credentials() {
	[[ -f "${ENV_FILE}" ]] || hfl_fail "missing ${ENV_FILE}" 2
	HFL_API_BASE="$(read_env_value "${ENV_FILE}" HFL_API_BASE)"
	HFL_ORG_KEY="$(read_env_value "${ENV_FILE}" HFL_ORG_KEY)"
	HFL_NODE_TOKEN="$(read_env_value "${ENV_FILE}" HFL_NODE_TOKEN)"
	HFL_NODE_ID="$(read_env_value "${ENV_FILE}" HFL_NODE_ID)"
	[[ -n "${HFL_API_BASE}" && -n "${HFL_ORG_KEY}" && -n "${HFL_NODE_TOKEN}" && -n "${HFL_NODE_ID}" ]] \
		|| hfl_fail "incomplete agent credentials in ${ENV_FILE}" 2
	GATEWAY_BOOTSTRAP_BASE="${HFL_API_BASE%/}/media/gateway-bootstrap"
}

report_lifecycle_status() {
	local phase=$1 status=$2 message=${3:-}
	[[ -n "${HFL_API_BASE}" ]] || return 0
	local payload
	payload="$(python3 - "${HFL_NODE_ID}" "${phase}" "${status}" "${message}" <<'PY'
import json, sys
node_id, phase, status, message = sys.argv[1:5]
body = {"node_id": node_id, "phase": phase, "status": status}
if message:
    body["error_message"] = message[:2000]
print(json.dumps(body))
PY
)"
	curl "${curl_tls[@]}" -fsS -X POST \
		-H "Content-Type: application/json" \
		-H "X-Org-Key: ${HFL_ORG_KEY}" \
		-H "X-Node-Token: ${HFL_NODE_TOKEN}" \
		-d "${payload}" \
		"${HFL_API_BASE%/}/api/v1/node/enrollment/gateway-install-status" >/dev/null \
		|| hfl_log "warning: failed to report lifecycle status (${phase}/${status})"
}

ensure_docker_ready() {
	command -v docker >/dev/null 2>&1 || hfl_fail "docker not found" 3
	docker info >/dev/null 2>&1 || hfl_fail "docker daemon not reachable" 3
}

compose_down_sidecar() {
	if [[ ! -f "${COMPOSE_DIR}/docker-compose.yml" ]]; then
		# Remove pre-normalization explicit container names during upgrades.
		docker rm -f hfl-gw-lensnode hfl-lensnode-sidecar 2>/dev/null || true
		return 0
	fi
	if docker compose version >/dev/null 2>&1; then
		(
			cd "${COMPOSE_DIR}"
			docker compose -p "${COMPOSE_PROJECT}" down || true
		)
	elif command -v docker-compose >/dev/null 2>&1; then
		(
			cd "${COMPOSE_DIR}"
			docker-compose -p "${COMPOSE_PROJECT}" down || true
		)
	fi
	# Remove pre-normalization explicit container names during upgrades.
	docker rm -f hfl-gw-lensnode hfl-lensnode-sidecar 2>/dev/null || true
}

download_bootstrap_file() {
	local name=$1 dest=$2
	hfl_log "Downloading ${name} from console."
	curl "${curl_tls[@]}" -fsSL "${GATEWAY_BOOTSTRAP_BASE}/${name}" -o "${dest}"
	chmod +x "${dest}" 2>/dev/null || true
}

lensnode_image_supports_insecure_tls() {
	local ref=$1
	docker run --rm -e LENSNODE_INSECURE_TLS=1 "${ref}" \
		python -c "from lensnode.tls import tls_insecure_enabled; raise SystemExit(0 if tls_insecure_enabled() else 1)" \
		>/dev/null 2>&1
}

load_lensnode_image() {
	local work_dir=$1 ref
	local archive="${work_dir}/${LENSNODE_IMAGE_ARCHIVE}"
	download_bootstrap_file "${LENSNODE_IMAGE_ARCHIVE}" "${archive}"
	hfl_log "Loading LensNode container image."
	docker load -i "${archive}"
	for ref in \
		"${DEFAULT_LENSNODE_IMAGE}" \
		sourcelens-lensnode:latest \
		oneprocloud/sourcelens-lensnode:latest; do
		if docker image inspect "${ref}" >/dev/null 2>&1; then
			if ! lensnode_image_supports_insecure_tls "${ref}"; then
				hfl_fail "LensNode image ${ref} is missing HFL TLS bypass support (lensnode.tls); republish gateway-bootstrap bundle from patched SourceLens LensNode on the console host" 5
			fi
			return 0
		fi
	done
	hfl_fail "LensNode image not present after docker load (expected ${DEFAULT_LENSNODE_IMAGE})" 5
}

run_sidecar_install_script() {
	local script="${1:-}"
	[[ -n "${script}" && -f "${script}" ]] || hfl_fail "sidecar install script missing" 3
	[[ -f "${LENS_ENV_FILE}" ]] || hfl_fail "missing ${LENS_ENV_FILE}" 2
	HFL_LENS_ENV_FILE="${LENS_ENV_FILE}" \
		HFL_INSECURE_TLS="${HFL_INSECURE_TLS}" \
		LENSNODE_IMAGE="${DEFAULT_LENSNODE_IMAGE}" \
		bash "${script}"
}

cmd_upgrade_sidecar() {
	local tmp script
	load_agent_credentials
	report_lifecycle_status "sidecar_upgrade" "running"
	ensure_docker_ready
	tmp="$(mktemp -d)"
	load_lensnode_image "${tmp}"
	compose_down_sidecar
	script="${tmp}/${SIDECAR_INSTALL_SCRIPT}"
	download_bootstrap_file "${SIDECAR_INSTALL_SCRIPT}" "${script}"
	run_sidecar_install_script "${script}"
	rm -rf "${tmp}"
	report_lifecycle_status "sidecar_upgrade" "success"
	hfl_log "LensNode sidecar upgrade completed."
}

remove_lensnode_images() {
	local ref
	for ref in \
		"${DEFAULT_LENSNODE_IMAGE}" \
		sourcelens-lensnode:latest \
		oneprocloud/sourcelens-lensnode:latest; do
		docker image rm -f "${ref}" 2>/dev/null || true
	done
	docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^oneprocloud/(lensnode|sourcelens-lensnode):' | while read -r ref; do
		docker image rm -f "${ref}" 2>/dev/null || true
	done
	docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^sourcelens-lensnode:' | while read -r ref; do
		docker image rm -f "${ref}" 2>/dev/null || true
	done
}

purge_sidecar_artifacts() {
	local workspace=""
	if [[ -f "${LENS_ENV_FILE}" ]]; then
		# shellcheck disable=SC1090
		set -a
		source "${LENS_ENV_FILE}"
		set +a
		workspace="${HFL_WORKSPACE_ROOT:-}"
	fi
	compose_down_sidecar
	remove_lensnode_images
	rm -f "${LENS_ENV_FILE}"
	rm -rf "${COMPOSE_DIR}"
	if [[ -n "${workspace}" && "${workspace}" == /workspace/* ]]; then
		hfl_log "Removing gateway workspace ${workspace}."
		rm -rf "${workspace}"
	fi
}

cmd_uninstall_sidecar() {
	load_agent_credentials
	report_lifecycle_status "sidecar_uninstall" "running"
	if [[ "${PURGE_ALL}" -eq 1 ]]; then
		purge_sidecar_artifacts
	else
		compose_down_sidecar
	fi
	report_lifecycle_status "sidecar_uninstall" "success"
	hfl_log "LensNode sidecar uninstall completed."
}

main() {
	local cmd=${1:-}
	shift || true
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--purge-all) PURGE_ALL=1 ;;
		*) hfl_fail "unknown option: $1" 2 ;;
		esac
		shift
	done
	case "${cmd}" in
	upgrade-sidecar) cmd_upgrade_sidecar ;;
	uninstall-sidecar) cmd_uninstall_sidecar ;;
	-h | --help | help | "") usage ;;
	*) hfl_fail "unknown command: ${cmd}" 2 ;;
	esac
}

main "$@"

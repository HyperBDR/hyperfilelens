#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# Load only the dotenv boolean parser and platform Gateway deployment functions.
# shellcheck disable=SC1090
source <(sed -n '/^read_env_value()/,/^resolve_console_host()/p' "${installer}" | sed '$d')
# shellcheck disable=SC1090
source <(sed -n '/^platform_gateway_auto_deploy_enabled()/,/^# --- Commands ---/p' "${installer}" | sed '$d')

ROOT="${tmp}/install"
mkdir -p "${ROOT}/data/media/enroll-bootstrap"
helper="${ROOT}/data/media/enroll-bootstrap/hfl-enroll-linux-amd64"
marker="${tmp}/helper-ran"
printf '%s\n' \
	'#!/usr/bin/env bash' \
	'set -euo pipefail' \
	'[[ "$HFL_ORG_KEY" == "__platform_lens__" ]]' \
	'[[ "$HFL_NODE_ROLE" == "gateway" ]]' \
	'[[ "$HFL_API_BASE" == "https://console.example:11443" ]]' \
	'[[ "$HFL_WSS_URL" == "wss://console.example:11443/ws/node/agent/" ]]' \
	'[[ "$1" == "gateway-install" && "$2" == "--yes" ]]' \
	'printf "%s" "$HFL_INSECURE_TLS" >"$TEST_PLATFORM_GATEWAY_MARKER"' \
	>"${helper}"
chmod 755 "${helper}"

AUTO_DEPLOY=false
TLS_MODE=1
read_env_value() {
	case "$1" in
	HFL_PLATFORM_GATEWAY_AUTO_DEPLOY) printf '%s' "${AUTO_DEPLOY}" ;;
	HFL_INSECURE_TLS) printf '%s' "${TLS_MODE}" ;;
	esac
}
skip() { :; }
step() { :; }
ok() { :; }
die() { printf 'FAIL: %s\n' "$1" >&2; exit "${2:-1}"; }
require_root_or_sudo() { :; }
require_docker() { :; }
read_agent_env_value() { :; }
run_as_root() { "$@"; }
compose_in_root() {
	printf '%s\n' 'HFL_LOCAL_PLATFORM_GATEWAY_ENROLLMENT={"org_key":"__platform_lens__","token":"fixture-token","api_base":"https://console.example:11443","wss_url":"wss://console.example:11443/ws/node/agent/","managed_node_ids":[]}'
}

ensure_local_platform_gateway
[[ ! -e "${marker}" ]]

AUTO_DEPLOY=true
export TEST_PLATFORM_GATEWAY_MARKER="${marker}"
ensure_local_platform_gateway
[[ "$(<"${marker}")" == "1" ]]

TLS_MODE=0
rm -f "${marker}"
ensure_local_platform_gateway
[[ "$(<"${marker}")" == "0" ]]

read_agent_env_value() {
	case "$1" in
	HFL_ORG_KEY) printf '__platform_lens__' ;;
	HFL_NODE_ROLE) printf 'gateway' ;;
	HFL_NODE_ID) printf '99' ;;
	HFL_NODE_TOKEN) printf 'manual-token' ;;
	esac
}
if (ensure_local_platform_gateway) 2>/dev/null; then
	printf 'ERROR: auto-deploy claimed a platform Gateway not managed by the installer\n' >&2
	exit 1
fi

AUTO_DEPLOY=invalid
if (platform_gateway_auto_deploy_enabled) 2>/dev/null; then
	printf 'ERROR: invalid platform Gateway auto-deploy value was accepted\n' >&2
	exit 1
fi

printf 'Platform Gateway auto-deploy contracts passed.\n'

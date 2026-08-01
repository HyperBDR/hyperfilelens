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
LOCAL_PLATFORM_AGENT_INSTALL_DIR="${tmp}/agent-install"
LOCAL_PLATFORM_AGENT_DATA_DIR="${tmp}/agent-data"
LOCAL_PLATFORM_LENSNODE_ENV_FILE="${tmp}/lensnode.env"
LOCAL_PLATFORM_LENSNODE_IMAGE="hyperfilelens-sourcelens-lensnode:latest"
mkdir -p \
	"${ROOT}/data/media/enroll-bootstrap" \
	"${ROOT}/data/media/agent-releases" \
	"${ROOT}/data/media/gateway-bootstrap" \
	"${LOCAL_PLATFORM_AGENT_INSTALL_DIR}" \
	"${LOCAL_PLATFORM_AGENT_DATA_DIR}"
helper="${ROOT}/data/media/enroll-bootstrap/hfl-enroll-linux-amd64"
marker="${tmp}/helper-ran"
cat >"${helper}" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ "$HFL_ORG_KEY" == "__platform_lens__" ]]
[[ "$HFL_NODE_ROLE" == "gateway" ]]
[[ "$HFL_API_BASE" == "https://127.0.0.1:11443" ]]
[[ "$HFL_WSS_URL" == "wss://127.0.0.1:11443/ws/node/agent/" ]]
[[ "$HFL_FORCE_SIDECAR_INSTALL" == "1" ]]
[[ "$1" == "gateway-install" && "$2" == "--yes" ]]
mkdir -p "$TEST_AGENT_INSTALL_DIR" "$TEST_AGENT_DATA_DIR"
if [[ ! -f "$TEST_AGENT_INSTALL_DIR/INSTALLED_VERSION" ]]; then
	printf '%s\n' "$TEST_DESIRED_VERSION" >"$TEST_AGENT_INSTALL_DIR/INSTALLED_VERSION"
fi
cat >"$TEST_AGENT_DATA_DIR/agent.env" <<EOF
HFL_ORG_KEY=__platform_lens__
HFL_NODE_ROLE=gateway
HFL_NODE_ID=99
HFL_NODE_TOKEN=fixture-token
EOF
printf '%s|%s|%s' "$HFL_API_BASE" "$HFL_WSS_URL" "$HFL_INSECURE_TLS" >"$TEST_PLATFORM_GATEWAY_MARKER"
SH
chmod 755 "${helper}"

cat >"${LOCAL_PLATFORM_AGENT_INSTALL_DIR}/install.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == "upgrade" && "$2" == "--from" ]]
[[ "${TEST_AGENT_UPGRADE_FAIL:-0}" != "1" ]] || exit 42
printf '%s\n' "$3" >"$TEST_AGENT_UPGRADE_MARKER"
printf '%s\n' "$TEST_DESIRED_VERSION" >"$TEST_AGENT_INSTALL_DIR/INSTALLED_VERSION"
SH
chmod 755 "${LOCAL_PLATFORM_AGENT_INSTALL_DIR}/install.sh"

export TEST_PLATFORM_GATEWAY_MARKER="${marker}"
export TEST_AGENT_UPGRADE_MARKER="${tmp}/agent-upgrade-ran"
export TEST_AGENT_INSTALL_DIR="${LOCAL_PLATFORM_AGENT_INSTALL_DIR}"
export TEST_AGENT_DATA_DIR="${LOCAL_PLATFORM_AGENT_DATA_DIR}"

AUTO_DEPLOY=false
TLS_MODE=1
read_env_value() {
	case "$1" in
	HFL_PLATFORM_GATEWAY_AUTO_DEPLOY) printf '%s' "${AUTO_DEPLOY}" ;;
	HFL_INSECURE_TLS) printf '%s' "${TLS_MODE}" ;;
	HFL_TENANT_PORT) printf '11443' ;;
	esac
}
read_version() { tr -d ' \t\r\n' <"${ROOT}/VERSION"; }
skip() { :; }
step() { :; }
ok() { :; }
die() { printf 'FAIL: %s\n' "$1" >&2; exit "${2:-1}"; }
require_root_or_sudo() { :; }
require_docker() { :; }
run_as_root() { "$@"; }
systemctl() { [[ "$*" == "is-active --quiet hyperfilelens-agent.service" ]]; }
converge_local_platform_gateway_lensnode() { :; }
wait_for_local_platform_gateway_online() { [[ "$1" == "99" ]]; }
active_api_service() { printf 'api-blue'; }
compose_in_root() {
	printf 'HFL_LOCAL_PLATFORM_GATEWAY_ENROLLMENT={"org_key":"%s","token":"fixture-token","api_base":"https://console.example:11443","wss_url":"wss://console.example:11443/ws/node/agent/","managed_node_ids":[99]}\n' "${ENROLLMENT_ORG}"
}

ENROLLMENT_ORG=__platform_lens__
export TEST_DESIRED_VERSION=main-1111111
printf '%s\n' "${TEST_DESIRED_VERSION}" >"${ROOT}/VERSION"

ensure_local_platform_gateway
[[ ! -e "${marker}" ]]

AUTO_DEPLOY=true
ensure_local_platform_gateway
[[ "$(<"${marker}")" == "https://127.0.0.1:11443|wss://127.0.0.1:11443/ws/node/agent/|1" ]]
[[ "$(local_platform_gateway_installed_agent_version)" == "main-1111111" ]]
[[ ! -e "${TEST_AGENT_UPGRADE_MARKER}" ]]

# An equal desired version must not restart or upgrade the Agent.
rm -f "${marker}"
ensure_local_platform_gateway
[[ -e "${marker}" ]]
[[ ! -e "${TEST_AGENT_UPGRADE_MARKER}" ]]

# Main builds are identities, not ordered hashes: any unequal desired identity converges.
export TEST_DESIRED_VERSION=main-2222222
printf '%s\n' "${TEST_DESIRED_VERSION}" >"${ROOT}/VERSION"
release_dir="${ROOT}/data/media/agent-releases/${TEST_DESIRED_VERSION}"
mkdir -p "${release_dir}"
archive="${release_dir}/hfl-agent-${TEST_DESIRED_VERSION}-linux-amd64.tar.gz"
printf 'fixture\n' >"${archive}"
rm -f "${TEST_AGENT_UPGRADE_MARKER}"
ensure_local_platform_gateway
[[ "$(<"${TEST_AGENT_UPGRADE_MARKER}")" == "${archive}" ]]
[[ "$(local_platform_gateway_installed_agent_version)" == "main-2222222" ]]

TLS_MODE=0
rm -f "${marker}"
ensure_local_platform_gateway
[[ "$(<"${marker}")" == "https://127.0.0.1:11443|wss://127.0.0.1:11443/ws/node/agent/|1" ]]

ENROLLMENT_ORG=tenant-org
if (ensure_local_platform_gateway) 2>/dev/null; then
	printf 'ERROR: local platform Gateway accepted another organization\n' >&2
	exit 1
fi
ENROLLMENT_ORG=__platform_lens__

sed -i 's/HFL_NODE_ID=99/HFL_NODE_ID=100/' "${LOCAL_PLATFORM_AGENT_DATA_DIR}/agent.env"
if (ensure_local_platform_gateway) 2>/dev/null; then
	printf 'ERROR: auto-deploy claimed a platform Gateway not managed by the installer\n' >&2
	exit 1
fi
sed -i 's/HFL_NODE_ID=100/HFL_NODE_ID=99/' "${LOCAL_PLATFORM_AGENT_DATA_DIR}/agent.env"

# A failed exact upgrade preserves the previous Agent and leaves a retention marker.
export TEST_DESIRED_VERSION=main-3333333
printf '%s\n' "${TEST_DESIRED_VERSION}" >"${ROOT}/VERSION"
release_dir="${ROOT}/data/media/agent-releases/${TEST_DESIRED_VERSION}"
mkdir -p "${release_dir}"
printf 'fixture\n' >"${release_dir}/hfl-agent-${TEST_DESIRED_VERSION}-linux-amd64.tar.gz"
export TEST_AGENT_UPGRADE_FAIL=1
if (ensure_local_platform_gateway) 2>/dev/null; then
	printf 'ERROR: failed local Agent upgrade was accepted\n' >&2
	exit 1
fi
unset TEST_AGENT_UPGRADE_FAIL
[[ "$(local_platform_gateway_installed_agent_version)" == "main-2222222" ]]
[[ "$(<"${ROOT}/data/.platform-gateway-agent-upgrade")" == "main-3333333" ]]

AUTO_DEPLOY=invalid
if (platform_gateway_auto_deploy_enabled) 2>/dev/null; then
	printf 'ERROR: invalid platform Gateway auto-deploy value was accepted\n' >&2
	exit 1
fi

# Exercise LensNode image convergence separately from Agent enrollment.
# shellcheck disable=SC1090
source <(sed -n '/^converge_local_platform_gateway_lensnode()/,/^wait_for_local_platform_gateway_online()/p' "${installer}" | sed '$d')
CURRENT_LENSNODE_IMAGE_ID=sha256:desired
DESIRED_LENSNODE_IMAGE_ID=sha256:desired
SIDECAR_RECREATED=0
script="${ROOT}/data/media/gateway-bootstrap/gateway-install-lensnode-sidecar.sh"
printf '#!/usr/bin/env bash\nexit 99\n' >"${script}"
chmod 755 "${script}"
docker() {
	case "$*" in
	"image inspect --format {{.Id}} hyperfilelens-sourcelens-lensnode:latest")
		printf '%s\n' "${DESIRED_LENSNODE_IMAGE_ID}"
		;;
	"ps -aq --no-trunc --filter label=com.hyperfilelens.managed=true --filter label=com.hyperfilelens.component=gateway-lensnode --filter label=com.docker.compose.project=hyperfilelens-gateway --filter label=com.docker.compose.service=lensnode")
		printf 'lensnode-container\n'
		;;
	"inspect --format {{.Image}} lensnode-container")
		printf '%s\n' "${CURRENT_LENSNODE_IMAGE_ID}"
		;;
	"inspect --format {{.State.Running}} lensnode-container")
		printf 'true\n'
		;;
	*) printf 'unexpected fake Docker invocation: %s\n' "$*" >&2; return 1 ;;
	esac
}
run_as_root() {
	if [[ "$1" == "env" ]]; then
		SIDECAR_RECREATED=$((SIDECAR_RECREATED + 1))
		CURRENT_LENSNODE_IMAGE_ID="${DESIRED_LENSNODE_IMAGE_ID}"
		return 0
	fi
	"$@"
}

converge_local_platform_gateway_lensnode
[[ "${SIDECAR_RECREATED}" == "0" ]]
CURRENT_LENSNODE_IMAGE_ID=sha256:old
converge_local_platform_gateway_lensnode
[[ "${SIDECAR_RECREATED}" == "1" ]]
[[ "${CURRENT_LENSNODE_IMAGE_ID}" == "${DESIRED_LENSNODE_IMAGE_ID}" ]]

printf 'Platform Gateway auto-deploy contracts passed.\n'

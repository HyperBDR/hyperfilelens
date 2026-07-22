#!/usr/bin/env bash
# HyperFileLens Agent enrollment bootstrap (Linux). Rendered by GET /enrollment/bootstrap.
set -euo pipefail

export HFL_ORG_KEY="__HFL_ORG_KEY__"
export HFL_NODE_ROLE="__HFL_NODE_ROLE__"
export HFL_NODE_TOKEN="__HFL_NODE_TOKEN__"
export HFL_API_BASE="__HFL_API_BASE__"
export HFL_WSS_URL="__HFL_WSS_URL__"
export HFL_INSECURE_TLS="__HFL_INSECURE_TLS__"

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
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
	hfl_fail "Unsupported architecture ${RAW_ARCH} (only amd64/arm64)." 4
	;;
esac

if [[ "$(id -u)" -ne 0 ]]; then
	hfl_fail "Administrator privileges are required. Re-run with sudo." 1
fi

if ! command -v systemctl >/dev/null 2>&1 \
	|| [[ ! -d /run/systemd/system ]] \
	|| ! systemctl show-environment >/dev/null 2>&1; then
	hfl_fail "This release requires a systemd-based Linux distribution. OpenRC, non-systemd, and container deployments are not supported." 2
fi

BIN="${TMPDIR:-/tmp}/hfl-enroll-$$"
cleanup() { rm -f "${BIN}"; }
trap cleanup EXIT

curl "${CURL_TLS[@]}" -fsSL "${HFL_API_BASE}/media/enroll-bootstrap/hfl-enroll-linux-${HFL_ARCH}" -o "${BIN}"
chmod +x "${BIN}"
# Do not exec: trap EXIT must run after install so /tmp/hfl-enroll-* is removed on success or failure.
hfl_build_enroll_args "$@"
"${BIN}" install "${HFL_ENROLL_ARGS[@]}"

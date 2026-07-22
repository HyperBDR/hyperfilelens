#!/usr/bin/env bash
# HyperFileLens Agent enrollment bootstrap (macOS). Rendered by GET /enrollment/bootstrap.
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

CURL_TLS=(-k)
if [[ "${HFL_INSECURE_TLS}" == "0" ]]; then
	CURL_TLS=()
fi

if ! command -v curl >/dev/null 2>&1; then
	hfl_fail "curl is required but not installed." 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
	hfl_fail "Administrator privileges are required. Re-run with sudo." 1
fi

if ! command -v launchctl >/dev/null 2>&1; then
	hfl_fail "launchd is required to install the agent service on macOS." 2
fi

RAW_ARCH="$(uname -m)"
case "${RAW_ARCH}" in
x86_64 | amd64) HFL_ARCH=amd64 ;;
aarch64 | arm64) HFL_ARCH=arm64 ;;
*)
	hfl_fail "Unsupported architecture ${RAW_ARCH} (only amd64/arm64)." 4
	;;
esac

BIN="${TMPDIR:-/tmp}/hfl-enroll-$$"
cleanup() { rm -f "${BIN}"; }
trap cleanup EXIT

curl "${CURL_TLS[@]}" -fsSL "${HFL_API_BASE}/media/enroll-bootstrap/hfl-enroll-darwin-${HFL_ARCH}" -o "${BIN}"
chmod +x "${BIN}"
# Do not exec: trap EXIT must run after install so /tmp/hfl-enroll-* is removed on success or failure.
"${BIN}" install "$@"

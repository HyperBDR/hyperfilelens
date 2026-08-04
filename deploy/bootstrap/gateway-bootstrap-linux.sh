#!/usr/bin/env bash
# HyperFileLens Data Gateway enrollment bootstrap (Linux only).
# Rendered by GET /enrollment/bootstrap-gateway.
#
# Stage order (matches Agent bootstrap):
#   1) minimal connectivity / platform gates
#   2) download lightweight hfl-enroll
#   3) hfl-enroll runs full preflight, then Agent package install + register
#   4) hfl-enroll installs Docker (if needed) and LensNode during AI engine setup
# Docker CE must not be installed here — that would mutate the host before preflight.
set -euo pipefail

# Avoid getcwd / job-working-directory noise when the caller cwd was removed
# (common if the user ran the one-liner from a stale /opt/hyperfilelens-agent).
cd / || cd /tmp || true

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
	printf '[%s] [....] %s\n' "$(hfl_now)" "$1"
}

hfl_ok() {
	printf '[%s] [ OK  ] %s\n' "$(hfl_now)" "$1"
}

hfl_fail() {
	printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$1" >&2
	exit "${2:-1}"
}

hfl_format_bytes() {
	awk -v bytes="$1" 'BEGIN {
		split("B KiB MiB GiB TiB", units, " ")
		value = bytes + 0
		unit = 1
		while (value >= 1024 && unit < 5) {
			value /= 1024
			unit++
		}
		if (unit == 1) printf "%.0f %s", value, units[unit]
		else printf "%.1f %s", value, units[unit]
	}'
}

hfl_download() {
	local label="$1"
	local url="$2"
	local destination="$3"
	local partial="${destination}.part"
	local started=${SECONDS} elapsed bytes rate
	rm -f "${partial}"
	hfl_step "Downloading ${label}."
	if ! curl "${CURL_TLS[@]}" \
		--fail --show-error --location --progress-bar \
		--retry 3 --retry-connrefused --retry-delay 2 \
		"${url}" -o "${partial}"; then
		rm -f "${partial}"
		hfl_fail "Failed to download ${label}." 3
	fi
	mv -f "${partial}" "${destination}"
	bytes="$(wc -c <"${destination}")"
	elapsed=$((SECONDS - started))
	((elapsed > 0)) || elapsed=1
	rate="$(hfl_format_bytes "$((bytes / elapsed))")/s"
	hfl_ok "${label} downloaded ($(hfl_format_bytes "${bytes}") in ${elapsed}s, average ${rate})."
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

CONSOLE_BASE="${HFL_API_BASE%/}"

hfl_step "Checking console connectivity."
curl "${CURL_TLS[@]}" -fsSL "${CONSOLE_BASE}/health" >/dev/null
hfl_ok "Console is reachable."

hfl_step "Checking SourceLens health via console proxy."
hfl_sourcelens_health_retry "${CONSOLE_BASE}/sourcelens/health" "SourceLens health" 3 5
hfl_ok "SourceLens is reachable."

BIN="${TMPDIR:-/tmp}/hfl-enroll-$$"
cleanup() { rm -f "${BIN}" "${BIN}.part"; }
trap cleanup EXIT

hfl_download \
	"HyperFileLens enrollment helper" \
	"${HFL_API_BASE}/media/enroll-bootstrap/hfl-enroll-linux-${HFL_ARCH}" \
	"${BIN}"
chmod +x "${BIN}"
# Do not exec: trap EXIT must run after gateway-install so /tmp/hfl-enroll-* is removed.
hfl_build_enroll_args "$@"
"${BIN}" gateway-install "${HFL_ENROLL_ARGS[@]}"

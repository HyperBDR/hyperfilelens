#!/usr/bin/env bash
# Shared logging helpers for repository orchestration scripts.

if [[ -n "${HFL_LOGGING_LOADED:-}" ]]; then
	return 0 2>/dev/null || exit 0
fi
HFL_LOGGING_LOADED=1

HFL_LOG_COMPONENT="${HFL_LOG_COMPONENT:-hfl}"
HFL_LOG_VERBOSE="${HFL_LOG_VERBOSE:-0}"
HFL_LOG_FILE="${HFL_LOG_FILE:-}"
HFL_LOG_SESSION_STARTED=0

hfl_log_timestamp() {
	date -u '+%Y-%m-%dT%H:%M:%S.000Z'
}

hfl_log_emit() {
	local level=$1
	shift
	printf '[%s] [%-5s] %s\n' "$(hfl_log_timestamp)" "${level}" "$*" >&2
}

hfl_log_info() { hfl_log_emit INFO "$@"; }
hfl_log_step() { hfl_log_emit STEP "$@"; }
hfl_log_ok() { hfl_log_emit ' OK ' "$@"; }
hfl_log_skip() { hfl_log_emit SKIP "$@"; }
hfl_log_warn() { hfl_log_emit WARN "$@"; }
hfl_log_debug() {
	[[ "${HFL_LOG_VERBOSE}" == "1" ]] || return 0
	hfl_log_emit DEBUG "$@"
}
hfl_log_fail() { hfl_log_emit FAIL "$@"; }

hfl_die() {
	local message=${1:-"operation failed"}
	local code=${2:-1}
	hfl_log_fail "${message}"
	exit "${code}"
}

hfl_require_value() {
	if [[ $# -lt 2 || -z "${2:-}" || "${2:0:1}" == "-" ]]; then
		hfl_die "${1} requires a value" 2
	fi
}

hfl_logging_configure() {
	local component=${1:-hfl}
	local log_file=${2:-${HFL_LOG_FILE:-}}
	local verbose=${3:-${HFL_LOG_VERBOSE:-0}}
	HFL_LOG_COMPONENT="${component}"
	HFL_LOG_VERBOSE="${verbose}"
	HFL_LOG_FILE="${log_file}"
	if [[ -n "${HFL_LOG_FILE}" && "${HFL_LOG_TEE_ACTIVE:-0}" != "1" ]]; then
		mkdir -p "$(dirname "${HFL_LOG_FILE}")"
		export HFL_LOG_TEE_ACTIVE=1
		exec 2> >(tee -a "${HFL_LOG_FILE}" >&2)
	fi
}

hfl_logging_start() {
	HFL_LOG_SESSION_STARTED=1
	hfl_log_info "Session started"
}

hfl_logging_finish() {
	local code=${1:-0}
	[[ "${HFL_LOG_SESSION_STARTED}" == "1" ]] || return 0
	HFL_LOG_SESSION_STARTED=0
	if [[ "${code}" -eq 0 ]]; then
		hfl_log_ok "Session completed"
	else
		hfl_log_fail "Session exited with status ${code}"
	fi
}

hfl_redact() {
	[[ -n "${1:-}" ]] && printf '<set>' || printf '<unset>'
}

#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIFECYCLE="${ROOT}/deploy/bootstrap/gateway-lifecycle.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export HFL_GATEWAY_SIDECAR_LOCK_FILE="${tmp}/sidecar.lock"

test_resume_after_interruption() (
	# shellcheck disable=SC1090
	source "${LIFECYCLE}"
	local destination="${tmp}/resumed.bin" calls="${tmp}/resume-calls"
	local expected='Aurora Glass|37 days|BLUE-ORBIT-731'
	GATEWAY_BOOTSTRAP_BASE=https://console.example/media/gateway-bootstrap
	DOWNLOAD_MAX_ATTEMPTS=3
	DOWNLOAD_RETRY_DELAY_SECONDS=0
	curl() {
		local output="" resume="" arg
		while [[ $# -gt 0 ]]; do
			arg=$1
			shift
			case "${arg}" in
			-o) output=$1; shift ;;
			--continue-at) resume=$1; shift ;;
			esac
		done
		[[ "${resume}" == "-" && -n "${output}" ]]
		if [[ ! -f "${calls}" ]]; then
			printf 1 >"${calls}"
			printf '%s' "${expected:0:17}" >"${output}"
			return 18
		fi
		[[ "$(wc -c <"${output}")" -eq 17 ]]
		printf '%s' "${expected:17}" >>"${output}"
		printf 2 >"${calls}"
	}

	download_bootstrap_file payload.bin "${destination}"
	[[ "$(<"${destination}")" == "${expected}" ]]
	[[ "$(<"${calls}")" == 2 ]]
	[[ ! -e "${destination}.part" ]]
)

test_retry_exhaustion_keeps_partial() {
	local destination="${tmp}/exhausted.bin"
	if (
		# shellcheck disable=SC1090
		source "${LIFECYCLE}"
		GATEWAY_BOOTSTRAP_BASE=https://console.example/media/gateway-bootstrap
		DOWNLOAD_MAX_ATTEMPTS=3
		DOWNLOAD_RETRY_DELAY_SECONDS=0
		curl() {
			local output="" arg
			while [[ $# -gt 0 ]]; do
				arg=$1
				shift
				if [[ "${arg}" == "-o" ]]; then
					output=$1
					shift
				fi
			done
			printf x >>"${output}"
			return 18
		}
		download_bootstrap_file payload.bin "${destination}"
	) 2>"${tmp}/exhausted.log"; then
		printf 'download unexpectedly succeeded after retry exhaustion\n' >&2
		return 1
	fi
	[[ "$(wc -c <"${destination}.part")" -eq 3 ]]
	grep -F 'failed to download payload.bin after 3 attempts' "${tmp}/exhausted.log" >/dev/null
}

test_failed_staging_reports_and_preserves_sidecar() {
	local env_file="${tmp}/agent.env"
	local status_file="${tmp}/lifecycle-status" down_marker="${tmp}/sidecar-down"
	printf '%s\n' \
		'HFL_API_BASE=https://console.example' \
		'HFL_ORG_KEY=org-test' \
		'HFL_NODE_TOKEN=node-test' \
		'HFL_NODE_ID=42' \
		>"${env_file}"
	if (
		HFL_AGENT_ENV_FILE="${env_file}"
		# shellcheck disable=SC1090
		source "${LIFECYCLE}"
		report_lifecycle_status() {
			printf '%s:%s:%s\n' "$1" "$2" "${3:-}" >>"${status_file}"
		}
		ensure_docker_ready() { :; }
		download_bootstrap_file() { hfl_fail 'simulated staging download failure' 23; }
		compose_down_sidecar() { printf down >"${down_marker}"; }
		cmd_upgrade_sidecar
	); then
		printf 'Gateway sidecar staging failure unexpectedly succeeded\n' >&2
		return 1
	fi
	[[ ! -e "${down_marker}" ]]
	grep -Fx 'sidecar_upgrade:running:' "${status_file}" >/dev/null
	grep -Fx 'sidecar_upgrade:failed:simulated staging download failure' "${status_file}" >/dev/null
}

test_resume_after_interruption
test_retry_exhaustion_keeps_partial
test_failed_staging_reports_and_preserves_sidecar

printf 'Gateway sidecar resumable upgrade contracts passed.\n'

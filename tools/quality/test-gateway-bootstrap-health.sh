#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bootstrap="${ROOT}/deploy/bootstrap/gateway-bootstrap-linux.sh"

# Load only the bootstrap logging and health-check functions, not its installer body.
# shellcheck disable=SC1090
source <(
	sed -n '/^hfl_now()/,/^MIN_ENGINE_VERSION=/p' "${bootstrap}" \
		| sed '$d'
)

CURL_TLS=()

run_health_check_with_response() {
	local mock_response="$1"
	(
		curl() {
			printf '%s' "${mock_response}"
		}
		hfl_sourcelens_health_retry "https://console.example/sourcelens/health" \
			"SourceLens health" 1 0
	)
}

run_health_check_with_response '{"health":"OK"}'

if run_health_check_with_response '<!doctype html><title>HyperFileLens</title>' 2>/dev/null; then
	printf 'ERROR: Gateway bootstrap accepted the Admin SPA as SourceLens health\n' >&2
	exit 1
fi

if run_health_check_with_response '{"health":"DOWN"}' 2>/dev/null; then
	printf 'ERROR: Gateway bootstrap accepted an unhealthy SourceLens response\n' >&2
	exit 1
fi

printf 'Gateway bootstrap SourceLens health validation passed\n'

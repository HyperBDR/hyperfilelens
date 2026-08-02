#!/usr/bin/env bash
# Validate non-blocking public endpoint checks and private-address classification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin"

cat >"${tmp}/bin/curl" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"${HFL_CURL_LOG}"
exit "${HFL_CURL_STATUS:-0}"
MOCK
chmod +x "${tmp}/bin/curl"

run_check() {
	local url=$1 status=${2:-0}
	: >"${tmp}/curl.log"
	: >"${tmp}/summary.md"
	PATH="${tmp}/bin:${PATH}" \
		APP_PUBLIC_URL="${url}" \
		GITHUB_STEP_SUMMARY="${tmp}/summary.md" \
		HFL_CURL_LOG="${tmp}/curl.log" \
		HFL_CURL_STATUS="${status}" \
		"${ROOT}/.github/scripts/check-public-endpoint.sh" \
		>"${tmp}/output.log" 2>&1
}

run_check 'https://192.168.10.244:11443'
[[ ! -s "${tmp}/curl.log" ]]
grep -F 'is private or non-global' "${tmp}/summary.md" >/dev/null

run_check 'https://127.0.0.1:11443'
[[ ! -s "${tmp}/curl.log" ]]

run_check 'https://[::1]:11443'
[[ ! -s "${tmp}/curl.log" ]]

run_check 'UNCONFIGURED'
[[ ! -s "${tmp}/curl.log" ]]
grep -F 'not a valid HTTP(S) URL' "${tmp}/summary.md" >/dev/null

run_check 'https://app.hyperfilelens.com'
grep -F 'https://app.hyperfilelens.com/health/ready' "${tmp}/curl.log" >/dev/null
grep -F 'Passed:' "${tmp}/summary.md" >/dev/null

run_check 'https://app.hyperfilelens.com' 28
grep -F 'Warning:' "${tmp}/summary.md" >/dev/null

mkdir -p "${tmp}/fail-bin"
cat >"${tmp}/fail-bin/python3" <<'MOCK'
#!/usr/bin/env bash
exit 42
MOCK
chmod +x "${tmp}/fail-bin/python3"
PATH="${tmp}/fail-bin:${PATH}" run_check 'https://app.hyperfilelens.com'
grep -F 'execution failed with status 42' "${tmp}/summary.md" >/dev/null

printf 'Public endpoint check contracts passed.\n'

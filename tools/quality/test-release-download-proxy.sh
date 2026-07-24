#!/usr/bin/env bash
# Validate target-side Release proxy isolation and direct-download fallback.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
remote_deploy="${ROOT}/.github/scripts/remote-deploy.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin"

cat >"${tmp}/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
output=""
proxy="unset"
while (($#)); do
	printf '%s\n' "$1" >>"${HFL_TEST_CURL_LOG}"
	case "$1" in
	--proxy)
		proxy=${2-}
		printf '%s\n' "${2-}" >>"${HFL_TEST_CURL_LOG}"
		shift 2
		;;
	-o)
		output=${2-}
		printf '%s\n' "${2-}" >>"${HFL_TEST_CURL_LOG}"
		shift 2
		;;
	*) shift ;;
	esac
done
printf '%s\n' '---' >>"${HFL_TEST_CURL_LOG}"
if [[ "${HFL_TEST_PROXY_FAIL:-0}" == "1" && "${proxy}" != "" ]]; then
	exit 7
fi
[[ -n "${output}" ]] || exit 2
printf 'downloaded\n' >"${output}"
SH
chmod +x "${tmp}/bin/curl"

# Load only the production download helper.
source <(sed -n '/^download_release_file()/,/^}/p' "${remote_deploy}")
PATH="${tmp}/bin:${PATH}"
export PATH HFL_TEST_CURL_LOG="${tmp}/curl.log"

DOWNLOAD_PROXY_URL="http://192.168.8.182:7890"
download_release_file https://example.invalid/release "${tmp}/proxied"
[[ "$(grep -c '^---$' "${HFL_TEST_CURL_LOG}")" -eq 1 ]]
grep -Fx -- '--proxy' "${HFL_TEST_CURL_LOG}" >/dev/null
grep -Fx -- "${DOWNLOAD_PROXY_URL}" "${HFL_TEST_CURL_LOG}" >/dev/null
grep -Fx -- '--noproxy' "${HFL_TEST_CURL_LOG}" >/dev/null
grep -Fx 'downloaded' "${tmp}/proxied" >/dev/null

: >"${HFL_TEST_CURL_LOG}"
export HFL_TEST_PROXY_FAIL=1
download_release_file https://example.invalid/release "${tmp}/fallback"
[[ "$(grep -c '^---$' "${HFL_TEST_CURL_LOG}")" -eq 2 ]]
grep -Fx -- "${DOWNLOAD_PROXY_URL}" "${HFL_TEST_CURL_LOG}" >/dev/null
grep -Fx 'downloaded' "${tmp}/fallback" >/dev/null

: >"${HFL_TEST_CURL_LOG}"
unset HFL_TEST_PROXY_FAIL
DOWNLOAD_PROXY_URL=""
download_release_file https://example.invalid/release "${tmp}/direct"
[[ "$(grep -c '^---$' "${HFL_TEST_CURL_LOG}")" -eq 1 ]]
if grep -F '192.168.8.182' "${HFL_TEST_CURL_LOG}" >/dev/null; then
	printf 'ERROR: direct Release download unexpectedly used the TEST proxy\n' >&2
	exit 1
fi
grep -Fx 'downloaded' "${tmp}/direct" >/dev/null

printf 'Target-side Release download proxy checks passed.\n'

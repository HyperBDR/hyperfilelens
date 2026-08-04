#!/usr/bin/env bash
# Validate bounded GitHub Release upload retries for draft visibility races.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
upload="${ROOT}/release/ci/gh-release-upload.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin" "${tmp}/state"
: >"${tmp}/asset.bin"

cat >"${tmp}/bin/gh" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "release" && "${2:-}" == "upload" ]] || exit 2
count_file="${HFL_GH_TEST_STATE}/count"
count=0
[[ ! -f "${count_file}" ]] || count="$(cat "${count_file}")"
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"
case "${HFL_GH_TEST_MODE}" in
flaky)
	if [[ "${count}" -eq 1 ]]; then
		printf 'release not found\n' >&2
		exit 1
	fi
	;;
missing)
	printf 'release not found\n' >&2
	exit 1
	;;
fatal)
	printf 'HTTP 403: Resource not accessible by integration\n' >&2
	exit 1
	;;
success) ;;
*) exit 2 ;;
esac
MOCK
chmod +x "${tmp}/bin/gh"
export PATH="${tmp}/bin:${PATH}"
export HFL_GH_TEST_STATE="${tmp}/state"
export HFL_RELEASE_UPLOAD_DELAY_S=0

printf '0\n' >"${tmp}/state/count"
export HFL_GH_TEST_MODE=flaky
HFL_RELEASE_UPLOAD_ATTEMPTS=3 bash "${upload}" main-deadbeef "${tmp}/asset.bin" --clobber
[[ "$(cat "${tmp}/state/count")" == "2" ]]

printf '0\n' >"${tmp}/state/count"
export HFL_GH_TEST_MODE=fatal
if HFL_RELEASE_UPLOAD_ATTEMPTS=3 bash "${upload}" main-deadbeef "${tmp}/asset.bin" --clobber; then
	printf 'ERROR: non-retryable upload failure unexpectedly succeeded\n' >&2
	exit 1
fi
[[ "$(cat "${tmp}/state/count")" == "1" ]]

printf '0\n' >"${tmp}/state/count"
export HFL_GH_TEST_MODE=missing
if HFL_RELEASE_UPLOAD_ATTEMPTS=3 bash "${upload}" main-deadbeef "${tmp}/asset.bin" --clobber; then
	printf 'ERROR: exhausted release-not-found retries unexpectedly succeeded\n' >&2
	exit 1
fi
[[ "$(cat "${tmp}/state/count")" == "3" ]]

printf 'GitHub Release upload retry checks passed.\n'

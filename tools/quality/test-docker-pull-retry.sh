#!/usr/bin/env bash
# Validate bounded Docker pull retries, terminal error handling, and shared time budgets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/docker-images.sh
source "${ROOT}/tools/lib/docker-images.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin" "${tmp}/state"

cat >"${tmp}/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "pull" ]] || exit 2
count_file="${HFL_DOCKER_TEST_STATE}/count"
count=0
[[ ! -f "${count_file}" ]] || count="$(cat "${count_file}")"
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"
case "${HFL_DOCKER_TEST_MODE}" in
flaky)
	if [[ "${count}" -eq 1 ]]; then
		printf 'net/http: request canceled while waiting for connection\n' >&2
		exit 1
	fi
	;;
fatal)
	printf 'unauthorized: authentication required\n' >&2
	exit 1
	;;
hung)
	trap '' TERM
	while :; do :; done
	;;
success) ;;
*) exit 2 ;;
esac
MOCK
chmod +x "${tmp}/bin/docker"
export PATH="${tmp}/bin:${PATH}"
export HFL_DOCKER_TEST_STATE="${tmp}/state"

export HFL_DOCKER_TEST_MODE=flaky
hfl_docker_pull_with_retry example.invalid/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
	linux/amd64 5 2 0
[[ "$(cat "${tmp}/state/count")" == "2" ]]

printf '0\n' >"${tmp}/state/count"
export HFL_DOCKER_TEST_MODE=fatal
if hfl_docker_pull_with_retry example.invalid/private:latest linux/amd64 5 3 0; then
	printf 'ERROR: terminal registry failure unexpectedly succeeded\n' >&2
	exit 1
fi
[[ "$(cat "${tmp}/state/count")" == "1" ]]
grep -F 'non-retryable registry error' <<<"${HFL_DOCKER_LAST_ERROR}" >/dev/null

printf '0\n' >"${tmp}/state/count"
export HFL_DOCKER_TEST_MODE=success
SECONDS=100
HFL_DOCKER_PULL_DEADLINE_SECONDS=99
if hfl_docker_pull_with_retry example.invalid/app:latest linux/amd64 5 2 0; then
	printf 'ERROR: exhausted Docker pull budget unexpectedly succeeded\n' >&2
	exit 1
fi
[[ "$(cat "${tmp}/state/count")" == "0" ]]
grep -F 'budget exhausted' <<<"${HFL_DOCKER_LAST_ERROR}" >/dev/null

printf '0\n' >"${tmp}/state/count"
export HFL_DOCKER_TEST_MODE=hung
export HFL_DOCKER_PULL_KILL_AFTER_SECONDS=1
SECONDS=0
if hfl_docker_pull_with_retry example.invalid/hung:latest linux/amd64 1 1 0; then
	printf 'ERROR: Docker pull that ignored TERM unexpectedly succeeded\n' >&2
	exit 1
fi
[[ "${SECONDS}" -le 5 ]] || {
	printf 'ERROR: Docker pull forced termination exceeded its bound\n' >&2
	exit 1
}
unset HFL_DOCKER_PULL_KILL_AFTER_SECONDS

printf 'Docker pull retry and budget checks passed.\n'

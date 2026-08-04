#!/usr/bin/env bash
# Upload assets to a GitHub Release with a short bound for draft visibility races.
#
# Usage:
#   gh-release-upload.sh TAG FILE [FILE...] [--clobber]
#
# Retries only when gh reports "release not found" (draft Main releases can lag
# briefly after prepare). Defaults stay small: 5 attempts, 3s delay (~15s max).
set -euo pipefail

tag=${1:-}
shift || true
if [[ -z "${tag}" || $# -lt 1 ]]; then
	printf 'usage: gh-release-upload.sh TAG FILE [FILE...] [--clobber]\n' >&2
	exit 2
fi

attempts="${HFL_RELEASE_UPLOAD_ATTEMPTS:-5}"
delay_s="${HFL_RELEASE_UPLOAD_DELAY_S:-3}"
if ! [[ "${attempts}" =~ ^[1-9][0-9]*$ ]]; then
	printf 'ERROR: HFL_RELEASE_UPLOAD_ATTEMPTS must be a positive integer\n' >&2
	exit 2
fi
if ! [[ "${delay_s}" =~ ^[0-9]+$ ]]; then
	printf 'ERROR: HFL_RELEASE_UPLOAD_DELAY_S must be a non-negative integer\n' >&2
	exit 2
fi

is_retryable() {
	local log=$1
	# Match the gh CLI message seen when a just-created draft Release is not
	# visible yet. Do not broaden this to generic HTTP 404s.
	grep -Fiq 'release not found' "${log}"
}

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

attempt=1
while ((attempt <= attempts)); do
	set +e
	gh release upload "${tag}" "$@" >"${tmp}" 2>&1
	rc=$?
	set -e
	if [[ "${rc}" -eq 0 ]]; then
		[[ ! -s "${tmp}" ]] || cat "${tmp}"
		exit 0
	fi
	cat "${tmp}" >&2
	if ! is_retryable "${tmp}" || ((attempt == attempts)); then
		exit "${rc}"
	fi
	printf 'Release %s upload not ready (attempt %s/%s); retrying in %ss.\n' \
		"${tag}" "${attempt}" "${attempts}" "${delay_s}" >&2
	sleep "${delay_s}"
	attempt=$((attempt + 1))
done

exit 1

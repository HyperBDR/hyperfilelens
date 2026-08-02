#!/usr/bin/env bash
# Report whether a stable release is the highest successfully published SemVer.
set -euo pipefail

current_tag=${1:-}
repository=${GITHUB_REPOSITORY:-}
retry_delay=${HFL_RELEASE_FRESHNESS_RETRY_DELAY_SECONDS:-2}
[[ "${current_tag}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
	printf 'ERROR: release freshness requires a stable vMAJOR.MINOR.PATCH tag\n' >&2
	exit 2
}
[[ "${repository}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
	printf 'ERROR: GITHUB_REPOSITORY must identify owner/repository\n' >&2
	exit 2
}
[[ "${retry_delay}" =~ ^[0-9]+$ ]] || {
	printf 'ERROR: release freshness retry delay must be a non-negative integer\n' >&2
	exit 2
}

published_tags=
for attempt in 1 2 3; do
	if api_tags="$(gh api "repos/${repository}/releases?per_page=100" --paginate \
		--jq '.[] | select(.draft == false and .prerelease == false) | .tag_name' \
		2>/dev/null)"; then
		published_tags="$(awk '/^v[0-9]+\.[0-9]+\.[0-9]+$/' <<<"${api_tags}")"
		if grep -Fx "${current_tag}" <<<"${published_tags}" >/dev/null; then
			break
		fi
	fi
	[[ "${attempt}" -eq 3 ]] || sleep "${retry_delay}"
done
if ! grep -Fx "${current_tag}" <<<"${published_tags}" >/dev/null; then
	printf 'ERROR: stable release is not published: %s\n' "${current_tag}" >&2
	exit 2
fi

latest_tag="$(LC_ALL=C sort -V <<<"${published_tags}" | tail -n 1)"
if [[ "${current_tag}" == "${latest_tag}" ]]; then
	printf 'current\n'
else
	printf 'superseded\n'
fi

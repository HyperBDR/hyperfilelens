#!/usr/bin/env bash
# Report whether a Main-channel workflow commit still matches the current remote main tip.
set -euo pipefail

current_commit=${1:-}
[[ "${current_commit}" =~ ^[0-9a-f]{40}$ ]] || {
	printf 'ERROR: current Main commit must be a full lowercase SHA\n' >&2
	exit 2
}
git rev-parse --is-inside-work-tree >/dev/null
git cat-file -e "${current_commit}^{commit}" 2>/dev/null || {
	printf 'ERROR: current Main commit is unavailable: %s\n' "${current_commit}" >&2
	exit 2
}
git fetch --quiet origin main --no-tags
latest_commit="$(git rev-parse --verify 'refs/remotes/origin/main^{commit}')"
[[ "${latest_commit}" =~ ^[0-9a-f]{40}$ ]] || {
	printf 'ERROR: origin/main did not resolve to a full commit SHA\n' >&2
	exit 2
}

if [[ "${current_commit}" == "${latest_commit}" ]]; then
	printf 'current\n'
else
	printf 'superseded\n'
fi

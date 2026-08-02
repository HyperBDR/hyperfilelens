#!/usr/bin/env bash
# Retain retryable Main draft assets on failure and prune superseded Main releases after success.
set -euo pipefail

: "${ARTIFACT_ID:?ARTIFACT_ID is required}"
: "${MAIN_COMMIT:?MAIN_COMMIT is required}"
: "${BUILD_REQUIRED:?BUILD_REQUIRED is required}"
: "${PUBLISH_RESULT:?PUBLISH_RESULT is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
PUBLISH_DISPOSITION=${PUBLISH_DISPOSITION:-incomplete}

[[ "${ARTIFACT_ID}" =~ ^main-[0-9a-f]{7}$ ]] || {
	printf 'ERROR: invalid Main artifact identifier: %s\n' "${ARTIFACT_ID}" >&2
	exit 2
}
[[ "${MAIN_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || {
	printf 'ERROR: invalid Main commit identity: %s\n' "${MAIN_COMMIT}" >&2
	exit 2
}
[[ "${BUILD_REQUIRED}" == "true" || "${BUILD_REQUIRED}" == "false" ]] || {
	printf 'ERROR: invalid BUILD_REQUIRED value: %s\n' "${BUILD_REQUIRED}" >&2
	exit 2
}

write_summary() {
	[[ -n "${GITHUB_STEP_SUMMARY:-}" ]] || return 0
	printf '%s\n\n%s\n' "$1" "$2" >>"${GITHUB_STEP_SUMMARY}"
}

delete_main_artifact() {
	local artifact_id=$1
	[[ "${artifact_id}" =~ ^main-[0-9a-f]{7}$ ]] || return 2
	if gh release view "${artifact_id}" --repo "${GITHUB_REPOSITORY}" \
		>/dev/null 2>&1; then
		if ! gh release delete "${artifact_id}" --repo "${GITHUB_REPOSITORY}" --yes; then
			gh release view "${artifact_id}" --repo "${GITHUB_REPOSITORY}" \
				>/dev/null 2>&1 && return 1
		fi
	fi
	if gh api "repos/${GITHUB_REPOSITORY}/git/ref/tags/${artifact_id}" \
		--silent >/dev/null 2>&1; then
		if ! gh api --method DELETE \
			"repos/${GITHUB_REPOSITORY}/git/refs/tags/${artifact_id}" --silent; then
			gh api "repos/${GITHUB_REPOSITORY}/git/ref/tags/${artifact_id}" \
				--silent >/dev/null 2>&1 && return 1
		fi
	fi
}

publish_complete=0
if [[ "${PUBLISH_RESULT}" == "success" ]] \
	|| [[ "${BUILD_REQUIRED}" == "false" && "${PUBLISH_RESULT}" == "skipped" ]]; then
	publish_complete=1
fi

if [[ "${PUBLISH_DISPOSITION}" == "superseded" ]]; then
	printf 'Preserving the authoritative newer Main release; stale artifact %s was not published.\n' \
		"${ARTIFACT_ID}"
	write_summary '### Main release cleanup' \
		"Skipped cleanup for superseded \`${ARTIFACT_ID}\`; the authoritative newer Main release remains unchanged."
	exit 0
fi

if [[ "${publish_complete}" -ne 1 ]]; then
	printf 'Retaining retryable Main draft %s because publish result is %s.\n' \
		"${ARTIFACT_ID}" "${PUBLISH_RESULT}"
	write_summary '### Main release cleanup' \
		"Retained retryable draft \`${ARTIFACT_ID}\` because publishing did not complete. GitHub's **Re-run failed jobs** can reuse its internal assets."
	exit 0
fi

if ! freshness="$("$(dirname "${BASH_SOURCE[0]}")/check-main-freshness.sh" "${MAIN_COMMIT}")"; then
	printf '%s\n' '::warning title=Main release cleanup::Unable to verify the current Main commit; destructive cleanup was skipped.'
	write_summary '### Main release cleanup' \
		"Skipped destructive cleanup because current Main freshness could not be verified. Retained \`${ARTIFACT_ID}\` and all other Main releases."
	exit 0
fi
if [[ "${freshness}" == "superseded" ]]; then
	printf 'Preserving the authoritative newer Main release; cleanup commit %s is stale.\n' \
		"${MAIN_COMMIT}"
	write_summary '### Main release cleanup' \
		"Skipped cleanup for stale commit \`${MAIN_COMMIT}\`; the authoritative newer Main release remains unchanged."
	exit 0
fi
[[ "${freshness}" == "current" ]] || {
	printf 'ERROR: unexpected Main freshness result: %s\n' "${freshness}" >&2
	exit 2
}

all_main_builds="$(mktemp)"
trap 'rm -f "${all_main_builds}"' EXIT
gh api "repos/${GITHUB_REPOSITORY}/releases?per_page=100" --paginate \
	--jq '.[] | select(.tag_name | test("^main-[0-9a-f]{7}$")) | [.tag_name, .target_commitish] | @tsv' \
	>"${all_main_builds}"

deleted=0
preserved=0
while IFS=$'\t' read -r artifact_id target_commit; do
	[[ -n "${artifact_id}" && "${artifact_id}" != "${ARTIFACT_ID}" ]] || continue
	if [[ ! "${target_commit}" =~ ^[0-9a-f]{40}$ ]]; then
		printf 'WARNING: preserving Main release %s with unresolved target %s.\n' \
			"${artifact_id}" "${target_commit:-<empty>}" >&2
		preserved=$((preserved + 1))
		continue
	fi
	if ! relation="$(gh api \
		"repos/${GITHUB_REPOSITORY}/compare/${target_commit}...${MAIN_COMMIT}" \
		--jq '.status' 2>/dev/null)"; then
		printf 'WARNING: preserving Main release %s because commit ancestry could not be verified.\n' \
			"${artifact_id}" >&2
		preserved=$((preserved + 1))
		continue
	fi
	if [[ "${relation}" == "ahead" ]]; then
		delete_main_artifact "${artifact_id}"
		deleted=$((deleted + 1))
	else
		printf 'Preserving non-ancestor Main release %s (relationship: %s).\n' \
			"${artifact_id}" "${relation}"
		preserved=$((preserved + 1))
	fi
done <"${all_main_builds}"

printf 'Retained Main release %s, removed %d ancestor release(s), and preserved %d non-ancestor or unresolved release(s).\n' \
	"${ARTIFACT_ID}" "${deleted}" "${preserved}"
write_summary '### Main release cleanup' \
	"Retained \`${ARTIFACT_ID}\`, removed ${deleted} ancestor Main release(s), and preserved ${preserved} non-ancestor or unresolved release(s)."

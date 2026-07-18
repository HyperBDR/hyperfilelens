#!/usr/bin/env bash
# Apply the minimal HyperFileLens TLS compatibility patch after git sync.
set -euo pipefail

sourcelens_lensnode_patch_matches_base() {
	local src=$1 patch_file=$2 path expected actual
	while IFS=$'\t' read -r path expected; do
		[[ -n "${path}" && -n "${expected}" ]] || continue
		if [[ "${expected}" == 0000000000000000000000000000000000000000 ]]; then
			[[ ! -e "${src}/${path}" ]] || return 1
			continue
		fi
		[[ -f "${src}/${path}" ]] || return 1
		actual="$(git -C "${src}" hash-object "${path}")"
		[[ "${actual}" == "${expected}" ]] || return 1
	done < <(
		awk '
			/^diff --git / { path = $4; sub(/^b\//, "", path) }
			/^index / { split($2, hashes, /\.\./); print path "\t" hashes[1] }
		' "${patch_file}"
	)
}

sourcelens_apply_lensnode_hfl_patches() {
	local src="${1:-}"
	local patch_file="${HFL_ROOT:-}/deploy/installer/sourcelens/lensnode-tls.patch"
	[[ -n "${src}" ]] || return 0
	[[ -f "${patch_file}" ]] || return 0
	[[ -d "${src}/.git" ]] || return 0
	if git -C "${src}" apply --unidiff-zero --reverse --check \
		"${patch_file}" >/dev/null 2>&1; then
		sourcelens_log "HFL LensNode TLS patch already applied"
		return 0
	fi
	if ! sourcelens_lensnode_patch_matches_base "${src}" "${patch_file}"; then
		sourcelens_log "HFL LensNode TLS patch target files differ from its SourceLens base revision"
		return 1
	fi
	if ! git -C "${src}" apply --unidiff-zero --check "${patch_file}"; then
		sourcelens_log "HFL LensNode TLS patch does not apply cleanly to the selected SourceLens revision"
		return 1
	fi
	git -C "${src}" apply --unidiff-zero "${patch_file}"
	sourcelens_log "Applied HFL LensNode TLS patch from ${patch_file#${HFL_ROOT:-}/}"
}

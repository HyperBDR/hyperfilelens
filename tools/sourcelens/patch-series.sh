#!/usr/bin/env bash
# Apply the ordered HyperFileLens SourceLens patch series to a disposable tree.
set -euo pipefail

sourcelens_patch_series_entries() {
	local series="${SOURCELENS_PATCH_ROOT}/series"
	[[ -f "${series}" ]] || sourcelens_die "missing SourceLens patch series: ${series}"
	awk '
		{sub(/\r$/, "")}
		/^[[:space:]]*($|#)/ {next}
		{gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print}
	' "${series}"
}

sourcelens_patch_matches_base() {
	local src=$1 patch_file=$2 path expected actual diff_count index_count
	diff_count="$(grep -c '^diff --git ' "${patch_file}" || true)"
	index_count="$(grep -c '^index ' "${patch_file}" || true)"
	[[ "${diff_count}" -gt 0 && "${diff_count}" -eq "${index_count}" ]] \
		|| return 1
	while IFS=$'\t' read -r path expected; do
		[[ -n "${path}" && -n "${expected}" ]] || continue
		[[ "${expected}" =~ ^[0-9a-f]{7,40}$ ]] || return 1
		if [[ "${expected}" =~ ^0+$ ]]; then
			[[ ! -e "${src}/${path}" ]] || return 1
			continue
		fi
		[[ -f "${src}/${path}" ]] || return 1
		actual="$(git hash-object "${src}/${path}")"
		[[ "${actual}" == "${expected}"* ]] || return 1
	done < <(
		awk '
			/^diff --git / { path = $3; sub(/^a\//, "", path) }
			/^index / { split($2, hashes, /\.\./); print path "\t" hashes[1] }
		' "${patch_file}"
	)
}

sourcelens_patchset_digest() {
	local entry patch_file
	{
		printf 'series\0'
		cat "${SOURCELENS_PATCH_ROOT}/series"
		while IFS= read -r entry; do
			patch_file="${SOURCELENS_PATCH_ROOT}/${entry}"
			[[ -f "${patch_file}" ]] \
				|| sourcelens_die "SourceLens patch listed in series is missing: ${entry}"
			printf '%s\0' "${entry}"
			sha256sum "${patch_file}"
		done < <(sourcelens_patch_series_entries)
	} | sha256sum | awk '{print $1}'
}

sourcelens_patch_manifest_json() {
	python3 - "${SOURCELENS_PATCH_ROOT}" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
entries = []
for raw in (root / "series").read_text(encoding="utf-8").splitlines():
    name = raw.strip()
    if not name or name.startswith("#"):
        continue
    path = root / name
    entries.append(
        {
            "file": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )
print(json.dumps(entries, separators=(",", ":")))
PY
}

sourcelens_apply_hfl_patch_series() {
	local src="${1:-}" entry patch_file count=0
	[[ -n "${src}" && -d "${src}" ]] \
		|| sourcelens_die "SourceLens disposable build tree is missing"
	while IFS= read -r entry; do
		case "${entry}" in
		active/*.patch) ;;
		*) sourcelens_die "invalid active SourceLens patch path: ${entry}" ;;
		esac
		patch_file="${SOURCELENS_PATCH_ROOT}/${entry}"
		[[ -f "${patch_file}" ]] \
			|| sourcelens_die "SourceLens patch listed in series is missing: ${entry}"
		if ! sourcelens_patch_matches_base "${src}" "${patch_file}"; then
			sourcelens_die "SourceLens patch base differs from ${entry}"
		fi
		if ! (cd "${src}" && git apply --unidiff-zero --check "${patch_file}"); then
			sourcelens_die "SourceLens patch does not apply cleanly: ${entry}"
		fi
		(cd "${src}" && git apply --unidiff-zero "${patch_file}")
		sourcelens_log "Applied HFL SourceLens patch ${entry}"
		count=$((count + 1))
	done < <(sourcelens_patch_series_entries)
	if [[ "${count}" -eq 0 ]]; then
		sourcelens_log "SourceLens patch series is empty; using upstream capabilities"
	fi
}

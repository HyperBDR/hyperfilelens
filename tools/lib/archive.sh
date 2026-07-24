#!/usr/bin/env bash
# Parallel gzip helpers. pigz emits a standard gzip stream and is optional.

if [[ -n "${_hfl_archive_helpers_loaded:-}" ]]; then
	return 0 2>/dev/null || exit 0
fi
_hfl_archive_helpers_loaded=1

hfl_gzip_stream() {
	if command -v pigz >/dev/null 2>&1; then
		pigz -6 -n -c
	else
		gzip -6 -n -c
	fi
}

hfl_tar_create_gz() {
	local output=$1 base_dir=$2
	shift 2
	COPYFILE_DISABLE=1 tar -C "${base_dir}" -cf - "$@" \
		| hfl_gzip_stream >"${output}"
	gzip -t "${output}"
}

hfl_docker_save_gz() {
	local output=$1
	shift
	docker save "$@" | hfl_gzip_stream >"${output}"
	gzip -t "${output}"
}

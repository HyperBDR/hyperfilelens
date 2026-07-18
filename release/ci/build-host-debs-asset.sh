#!/usr/bin/env bash
# Fetch the pinned Ubuntu 24.04 Docker CE packages and export the canonical tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

[[ $# -eq 1 ]] || {
	printf 'Usage: %s OUTPUT_TAR_GZ\n' "$0" >&2
	exit 2
}
output=$1
"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh"
source_dir="${ROOT}/build/dependencies/docker/ubuntu-24.04/amd64"
[[ -d "${source_dir}" ]] || { printf 'ERROR: Docker deb output is missing\n' >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/host/debs"
rsync -a "${source_dir}/" "${tmp}/host/debs/"
mkdir -p "$(dirname "${output}")"
tar -C "${tmp}" -czf "${output}" host

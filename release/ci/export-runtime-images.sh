#!/usr/bin/env bash
# Export third-party runtime images used by every offline HFL installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../tools/lib/archive.sh
source "${ROOT}/tools/lib/archive.sh"
# shellcheck source=../../tools/dependencies/versions/runtime-images.env
source "${ROOT}/tools/dependencies/versions/runtime-images.env"

[[ $# -eq 1 ]] || {
	printf 'Usage: %s OUTPUT_TAR\n' "$0" >&2
	exit 2
}
output=$1
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/images" "${tmp}/metadata"

export_one() {
	local image=$1 local_ref=$2 archive=$3 key=$4 source_name
	docker pull --platform linux/amd64 "${image}"
	local digest
	source_name="${image%@*}"
	source_name="${source_name%%:*}"
	digest="${source_name}@${image##*@}"
	[[ "${digest}" =~ ^[^@]+@sha256:[0-9a-f]{64}$ ]]
	docker tag "${image}" "${local_ref}"
	hfl_docker_save_gz "${tmp}/images/${archive}" "${local_ref}"
	jq -n --arg component "${key}" --arg ref "${local_ref}" --arg source_ref "${image}" --arg digest "${digest}" \
		'{component: $component, ref: $ref, source_ref: $source_ref, digest: $digest, platform: "linux/amd64"}' \
		>"${tmp}/metadata/${key}.json"
	docker image rm "${image}" >/dev/null 2>&1 || true
}

export_one "${POSTGRES_IMAGE}" hyperfilelens-postgres:17 01-postgres-17.tar.gz postgres
export_one "${REDIS_IMAGE}" hyperfilelens-redis:alpine 02-redis-alpine.tar.gz redis
mkdir -p "$(dirname "${output}")"
tar -C "${tmp}" -cf "${output}" images metadata

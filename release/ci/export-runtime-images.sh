#!/usr/bin/env bash
# Export third-party runtime images used by every offline HFL installation.
set -euo pipefail

[[ $# -eq 1 ]] || {
	printf 'Usage: %s OUTPUT_TAR_GZ\n' "$0" >&2
	exit 2
}
output=$1
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/images" "${tmp}/metadata"

export_one() {
	local image=$1 local_ref=$2 archive=$3 key=$4
	docker pull --platform linux/amd64 "${image}"
	local digest
	digest="$(docker image inspect "${image}" --format '{{index .RepoDigests 0}}')"
	docker tag "${image}" "${local_ref}"
	docker save "${local_ref}" | gzip -c >"${tmp}/images/${archive}"
	gzip -t "${tmp}/images/${archive}"
	jq -n --arg component "${key}" --arg ref "${local_ref}" --arg source_ref "${image}" --arg digest "${digest}" \
		'{component: $component, ref: $ref, source_ref: $source_ref, digest: $digest, platform: "linux/amd64"}' \
		>"${tmp}/metadata/${key}.json"
	docker image rm "${image}" >/dev/null 2>&1 || true
}

export_one postgres:17 hyperfilelens-postgres:17 01-postgres-17.tar.gz postgres
export_one redis:alpine hyperfilelens-redis:alpine 02-redis-alpine.tar.gz redis
mkdir -p "$(dirname "${output}")"
tar -C "${tmp}" -czf "${output}" images metadata

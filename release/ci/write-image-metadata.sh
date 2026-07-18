#!/usr/bin/env bash
# Write normalized metadata for one registry image built by GitHub Actions.
set -euo pipefail

[[ $# -eq 4 ]] || {
	printf 'Usage: %s COMPONENT IMAGE_REF DIGEST OUTPUT\n' "$0" >&2
	exit 2
}

component=$1
image_ref=$2
digest=$3
output=$4

[[ "${component}" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
	printf 'ERROR: invalid component: %s\n' "${component}" >&2
	exit 2
}
[[ "${image_ref}" == */*:* ]] || {
	printf 'ERROR: image ref must include registry namespace and tag: %s\n' "${image_ref}" >&2
	exit 2
}
[[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || {
	printf 'ERROR: invalid image digest: %s\n' "${digest}" >&2
	exit 2
}

mkdir -p "$(dirname "${output}")"
jq -n \
	--arg component "${component}" \
	--arg ref "${image_ref}" \
	--arg digest "${digest}" \
	--arg platform linux/amd64 \
	'{component: $component, ref: $ref, digest: $digest, platform: $platform}' \
	>"${output}"

#!/usr/bin/env bash
# Build one HFL-bundled SourceLens component and push it to the HFL registry namespace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../tools/sourcelens/common.sh
source "${ROOT}/tools/sourcelens/common.sh"

usage() {
	printf 'Usage: %s COMPONENT REGISTRY HFL_VERSION OUTPUT_JSON\n' "$0" >&2
}

[[ $# -eq 4 ]] || { usage; exit 2; }
component=$1
registry=${2%/}
hfl_version=${3#v}
output=$4

case "${component}" in
backend) service=backend-api ;;
frontend) service=frontend ;;
lensnode) service=lensnode ;;
*) printf 'ERROR: unsupported SourceLens component: %s\n' "${component}" >&2; exit 2 ;;
esac
[[ "${registry}" =~ ^[a-z0-9][a-z0-9._-]*$ ]] || {
	printf 'ERROR: Docker Hub registry namespace is invalid: %s\n' "${registry}" >&2
	exit 2
}
[[ "${hfl_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
	printf 'ERROR: invalid HFL version: %s\n' "${hfl_version}" >&2
	exit 2
}

sourcelens_load_config
sourcelens_resolve_version
hfl_logging_configure "ci-sourcelens-${component}"
hfl_logging_start
trap 'hfl_logging_finish "$?"' EXIT

sourcelens_sync_source
SOURCELENS_BUILD_SERVICES="${service}" sourcelens_build_app_images 1 0

local_ref="$(sourcelens_upstream_image_ref "${component}")"
target_ref="${registry}/hyperfilelens-sourcelens-${component}:${hfl_version}-sl${SOURCELENS_VERSION}"
docker image inspect "${local_ref}" >/dev/null
docker tag "${local_ref}" "${target_ref}"
docker push "${target_ref}"

manifest_json="$(docker buildx imagetools inspect "${target_ref}" --format '{{json .Manifest}}')"
digest="$(jq -r '.digest // empty' <<<"${manifest_json}")"
[[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || {
	printf 'ERROR: unable to resolve pushed digest for %s\n' "${target_ref}" >&2
	exit 1
}

mkdir -p "$(dirname "${output}")"
jq -n \
	--arg component "sourcelens-${component}" \
	--arg ref "${target_ref}" \
	--arg digest "${digest}" \
	--arg platform linux/amd64 \
	--arg sourcelens_version "${SOURCELENS_VERSION}" \
	--arg sourcelens_git_ref "${SOURCELENS_GIT_REF}" \
	'{
	  component: $component,
	  ref: $ref,
	  digest: $digest,
	  platform: $platform,
	  sourcelens_version: $sourcelens_version,
	  sourcelens_git_ref: $sourcelens_git_ref
	}' >"${output}"

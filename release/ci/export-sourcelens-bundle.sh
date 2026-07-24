#!/usr/bin/env bash
# Convert registry-built HFL SourceLens images into the bundled offline runtime tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../../tools/dependencies/versions/runtime-images.env
source "${ROOT}/tools/dependencies/versions/runtime-images.env"
export SOURCELENS_NGINX_SOURCE_IMAGE="${NGINX_IMAGE}"

[[ $# -eq 3 ]] || {
	printf 'Usage: %s METADATA_DIR HFL_VERSION OUTPUT_TAR\n' "$0" >&2
	exit 2
}
metadata_dir=$1
hfl_version=${2#v}
output=$3

# shellcheck source=../../tools/lib/version.sh
source "${ROOT}/tools/lib/version.sh"
hfl_version="$(normalize_artifact_id "${hfl_version}")"

# shellcheck source=../../tools/sourcelens/common.sh
source "${ROOT}/tools/sourcelens/common.sh"
export SOURCELENS_HFL_VERSION="${hfl_version}"
sourcelens_load_config
sourcelens_resolve_version

pkg_root="${ROOT}/build/release/staging/hyperfilelens-${hfl_version}"
images_dir="${pkg_root}/images"
rm -rf "${pkg_root}"
mkdir -p "${images_dir}"

for component in backend frontend lensnode; do
	metadata="${metadata_dir}/sourcelens-${component}.json"
	[[ -s "${metadata}" ]] || { printf 'ERROR: missing metadata: %s\n' "${metadata}" >&2; exit 1; }
	ref="$(jq -r '.ref' "${metadata}")"
	digest="$(jq -r '.digest' "${metadata}")"
	docker pull --platform linux/amd64 "${ref%@*}@${digest}"
	docker tag "${ref%@*}@${digest}" "$(sourcelens_distribution_image_ref "${component}")"
	docker tag "${ref%@*}@${digest}" "$(sourcelens_distribution_image_ref "${component}" latest)"
done

BUILD_SOURCELENS=1 "${ROOT}/release/build-sourcelens.sh" \
	--pkg-root "${pkg_root}" \
	--images-dir "${images_dir}" \
	--prebuilt

# Record the actual HFL registry sources rather than the independent SourceLens
# repositories. The normalized local refs and runtime image IDs remain intact.
build_info="${pkg_root}/sourcelens/BUILD_INFO.json"
tmp_info="${build_info}.tmp"
jq \
	--arg backend_ref "$(jq -r '.ref' "${metadata_dir}/sourcelens-backend.json")" \
	--arg frontend_ref "$(jq -r '.ref' "${metadata_dir}/sourcelens-frontend.json")" \
	--arg lensnode_ref "$(jq -r '.ref' "${metadata_dir}/sourcelens-lensnode.json")" \
	'.images.backend.upstream_ref = $backend_ref
	 | .images.frontend.upstream_ref = $frontend_ref
	 | .images.lensnode.upstream_ref = $lensnode_ref' \
	"${build_info}" >"${tmp_info}"
mv "${tmp_info}" "${build_info}"

mkdir -p "$(dirname "${output}")"
tar -C "${pkg_root}" -cf "${output}" images sourcelens payload

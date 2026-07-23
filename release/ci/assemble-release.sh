#!/usr/bin/env bash
# Assemble matrix outputs into the canonical HFL offline release package.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# Source packaging helpers without executing release/build.sh's local build.
# shellcheck source=../build.sh
source "${ROOT}/release/build.sh"

if [[ -n "${HFL_CI_RELEASE_BUILD_DIR:-}" ]]; then
	RELEASE_BUILD_DIR="${HFL_CI_RELEASE_BUILD_DIR}"
	STAGING_BASE="${RELEASE_BUILD_DIR}/staging"
	DIST_DIR="${RELEASE_BUILD_DIR}/dist"
fi

usage() {
	cat <<'USAGE'
Usage: assemble-release.sh --input-dir DIR --version X.Y.Z|main-SHA7 --commit SHA
USAGE
}

input_dir=""
version=""
commit=""
while [[ $# -gt 0 ]]; do
	case "$1" in
	--input-dir) input_dir=${2:-}; shift 2 ;;
	--version) version=${2#v}; shift 2 ;;
	--commit) commit=${2:-}; shift 2 ;;
	-h | --help) usage; exit 0 ;;
	*) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
	esac
done

[[ -d "${input_dir}" ]] || { printf 'ERROR: input directory is missing\n' >&2; exit 2; }
version="$(normalize_artifact_id "${version}")"
[[ "${commit}" =~ ^[0-9a-f]{40}$ ]] || { printf 'ERROR: invalid commit\n' >&2; exit 2; }
if [[ "${version}" == main-* && "${version#main-}" != "${commit:0:7}" ]]; then
	printf 'ERROR: main build identifier does not match commit\n' >&2
	exit 2
fi

hfl_logging_configure ci-assemble
hfl_logging_start
trap 'hfl_logging_finish "$?"' EXIT

commit7=${commit:0:7}
pkg_name="hyperfilelens-${version}"
pkg_root="${STAGING_BASE}/${pkg_name}"
images_dir="${pkg_root}/images"
tar_basename="$(release_package_basename_for_version "${version}" "${commit7}")"
safe_assert_package_basename "${tar_basename}"
safe_assert_staging_pkg_root "${pkg_root}" "${STAGING_BASE}"
safe_rm_dir "${pkg_root}"
mkdir -p "${pkg_root}" "${images_dir}" "${pkg_root}/payload/media" "${pkg_root}/metadata"

required_bundles=(
	_internal-hfl-images.tar.gz
	_internal-runtime-images.tar.gz
	_internal-sourcelens-bundle.tar.gz
	_internal-host-debs-ubuntu2004.tar.gz
	_internal-host-debs-ubuntu2404.tar.gz
)
for bundle in "${required_bundles[@]}"; do
	[[ -s "${input_dir}/${bundle}" ]] || die "missing CI bundle: ${bundle}"
	log "Extracting ${bundle}"
	tar -xzf "${input_dir}/${bundle}" -C "${pkg_root}"
done

required_agent_bundles=(
	_internal-agent-linux-amd64.tar.gz
	_internal-agent-linux-arm64.tar.gz
	_internal-agent-darwin-amd64.tar.gz
	_internal-agent-darwin-arm64.tar.gz
	_internal-agent-windows-amd64.tar.gz
)
for bundle_name in "${required_agent_bundles[@]}"; do
	bundle="${input_dir}/${bundle_name}"
	[[ -s "${bundle}" ]] || die "missing Agent matrix bundle: ${bundle_name}"
	log "Merging $(basename "${bundle}")"
	tar -xzf "${bundle}" -C "${pkg_root}"
done

for required in \
	images/00-hyperfilelens.tar.gz \
	images/01-postgres-17.tar.gz \
	images/02-redis-alpine.tar.gz \
	images/10-sourcelens-app.tar.gz \
	images/11-sourcelens-lensnode.tar.gz \
	images/12-nginx-stable-alpine.tar.gz \
	sourcelens/BUILD_INFO.json; do
	[[ -s "${pkg_root}/${required}" ]] || die "assembled package is missing ${required}"
done

# The control-plane installer and Data Gateways consume the same OS-specific
# Docker archives under payload/media; do not duplicate their debs elsewhere.
gateway_dir="${pkg_root}/payload/media/gateway-bootstrap"
mkdir -p "${gateway_dir}"
for script in \
	gateway-bootstrap-linux.sh \
	gateway-install-lensnode-sidecar.sh \
	gateway-lifecycle.sh \
	gateway-install-docker-ubuntu-amd64.sh; do
	cp "${ROOT}/deploy/bootstrap/${script}" "${gateway_dir}/${script}"
	chmod 755 "${gateway_dir}/${script}"
done

log "Staging release runtime files"
printf '%s\n' "${version}" >"${pkg_root}/VERSION"
cp "${ROOT}/deploy/docker-compose.yml" "${pkg_root}/docker-compose.yml"
cp "${ROOT}/.env.example" "${pkg_root}/.env.example"
cp "${ROOT}/LICENSE" "${pkg_root}/LICENSE"
mkdir -p "${pkg_root}/deploy/nginx/certs" "${pkg_root}/deploy/nginx/snippets" "${pkg_root}/deploy/logrotate"
stage_default_tls_bundle "${pkg_root}"
cp "${ROOT}/deploy/nginx/default.conf" "${pkg_root}/deploy/nginx/default.conf"
rsync -a "${ROOT}/deploy/nginx/snippets/" "${pkg_root}/deploy/nginx/snippets/"
cp "${ROOT}/deploy/logrotate/hyperfilelens.conf" "${pkg_root}/deploy/logrotate/hyperfilelens.conf"
cp "${ROOT}/deploy/installer/install.sh" "${pkg_root}/install.sh"
cp "${ROOT}/deploy/installer/apply-runtime-config.py" "${pkg_root}/apply-runtime-config.py"
cp "${ROOT}/tools/config/sync_env.py" "${pkg_root}/sync-env.py"
chmod 755 "${pkg_root}/install.sh" "${pkg_root}/apply-runtime-config.py" "${pkg_root}/sync-env.py"

normalize_release_permissions "${pkg_root}"
payload_sha="$(tree_sha256 "${pkg_root}/payload")"

image_digest() {
	local metadata=$1 ref digest
	ref="$(jq -r '.ref' "${metadata}")"
	digest="$(jq -r '.digest' "${metadata}")"
	printf '%s@%s' "${ref%@*}" "${digest}"
}
backend_digest="$(image_digest "${pkg_root}/metadata/hfl-backend.json")"
frontend_digest="$(image_digest "${pkg_root}/metadata/hfl-frontend.json")"
postgres_digest="$(jq -r '.digest' "${pkg_root}/metadata/postgres.json")"
redis_digest="$(jq -r '.digest' "${pkg_root}/metadata/redis.json")"

write_manifest "${pkg_root}" "${version}" "${commit}" "${payload_sha}" \
	"${backend_digest}" "${frontend_digest}" "${postgres_digest}" "${redis_digest}"
rm -rf "${pkg_root}/metadata"
validate_release_publish_artifacts "${pkg_root}"
write_package_readme "${pkg_root}" "${version}"
validate_release_security "${pkg_root}"

python3 - "${pkg_root}" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
by_digest = {}
for path in root.rglob("*"):
    if not path.is_file() or path.stat().st_size < 10 * 1024 * 1024:
        continue
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    by_digest.setdefault(digest.hexdigest(), []).append(path)

for paths in by_digest.values():
    if len(paths) < 2:
        continue
    inodes = {(path.stat().st_dev, path.stat().st_ino) for path in paths}
    if len(inodes) > 1:
        names = ", ".join(path.relative_to(root).as_posix() for path in paths)
        raise SystemExit(f"duplicate large release content is not hard-linked: {names}")
PY

mkdir -p "${DIST_DIR}"
find "${DIST_DIR}" -maxdepth 1 -type f -delete
tar_path="${DIST_DIR}/${tar_basename}"
tar_tmp="${tar_path}.part"
log "Creating ${tar_path}"
tar_create_gz "${tar_tmp}" "${STAGING_BASE}" "${pkg_name}"
mv "${tar_tmp}" "${tar_path}"
chmod 644 "${tar_path}"

cp "${pkg_root}/MANIFEST.json" "${DIST_DIR}/MANIFEST.json"
python3 "${SCRIPT_DIR}/write-sbom.py" \
	--manifest "${pkg_root}/MANIFEST.json" \
	--output "${DIST_DIR}/SBOM.spdx.json"

warn_single_bytes="${HFL_RELEASE_WARN_SINGLE_BYTES:-1750000000}"
max_single_bytes="${HFL_RELEASE_MAX_SINGLE_BYTES:-1900000000}"
part_bytes="${HFL_RELEASE_PART_BYTES:-$((1024 * 1024 * 1024))}"
[[ "${max_single_bytes}" =~ ^[1-9][0-9]*$ ]] || die "invalid HFL_RELEASE_MAX_SINGLE_BYTES"
[[ "${warn_single_bytes}" =~ ^[1-9][0-9]*$ ]] || die "invalid HFL_RELEASE_WARN_SINGLE_BYTES"
[[ "${part_bytes}" =~ ^[1-9][0-9]*$ ]] || die "invalid HFL_RELEASE_PART_BYTES"
tar_bytes="$(stat -c '%s' "${tar_path}")"
if ((tar_bytes >= warn_single_bytes)); then
	hfl_log_warn "Release package size ${tar_bytes} bytes exceeds the 1.75 GB warning budget"
	find "${pkg_root}" -type f -printf '%s %P\n' | sort -nr | sed -n '1,20p' >&2
fi
if ((tar_bytes >= max_single_bytes)); then
	log "Release exceeds the single-asset limit; creating split parts"
	split -b "${part_bytes}" -d -a 3 "${tar_path}" "${tar_path}.part-"
	rm -f "${tar_path}"
	cp "${SCRIPT_DIR}/assemble-release.sh.txt" "${DIST_DIR}/assemble-release.sh"
	cp "${SCRIPT_DIR}/assemble-release.ps1.txt" "${DIST_DIR}/assemble-release.ps1"
	chmod 755 "${DIST_DIR}/assemble-release.sh"
fi

cp "${ROOT}/deploy/nginx/certs/root-ca.crt" "${DIST_DIR}/hyperfilelens-root-ca.crt"
chmod 644 "${DIST_DIR}/hyperfilelens-root-ca.crt"

(
	cd "${DIST_DIR}"
	checksums_tmp="${RELEASE_BUILD_DIR}/SHA256SUMS.tmp"
	find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%f\0' \
		| sort -z \
		| xargs -0 sha256sum >"${checksums_tmp}"
	mv "${checksums_tmp}" SHA256SUMS
	find . -maxdepth 1 -type f -printf '%f\n' | sort >"${RELEASE_BUILD_DIR}/release-assets.txt"
)

du -sh "${pkg_root}" "${DIST_DIR}"/*
log "Release assembly complete"

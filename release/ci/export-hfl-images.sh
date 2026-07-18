#!/usr/bin/env bash
# Export registry-built HFL backend/frontend images into the offline release archive.
set -euo pipefail

[[ $# -eq 3 ]] || {
	printf 'Usage: %s METADATA_DIR VERSION OUTPUT_TAR_GZ\n' "$0" >&2
	exit 2
}

metadata_dir=$1
version=${2#v}
output=$3
backend_meta="${metadata_dir}/hfl-backend.json"
frontend_meta="${metadata_dir}/hfl-frontend.json"

for file in "${backend_meta}" "${frontend_meta}"; do
	[[ -s "${file}" ]] || { printf 'ERROR: missing metadata: %s\n' "${file}" >&2; exit 1; }
done

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/images" "${tmp}/metadata"

pull_and_tag() {
	local metadata=$1 local_repo=$2
	local ref digest
	ref="$(jq -r '.ref' "${metadata}")"
	digest="$(jq -r '.digest' "${metadata}")"
	[[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || return 2
	docker pull --platform linux/amd64 "${ref%@*}@${digest}"
	docker tag "${ref%@*}@${digest}" "${local_repo}:${version}"
	docker tag "${ref%@*}@${digest}" "${local_repo}:latest"
}

pull_and_tag "${backend_meta}" hyperfilelens-backend
pull_and_tag "${frontend_meta}" hyperfilelens-frontend
docker save \
	"hyperfilelens-backend:${version}" hyperfilelens-backend:latest \
	"hyperfilelens-frontend:${version}" hyperfilelens-frontend:latest \
	| gzip -c >"${tmp}/images/00-hyperfilelens.tar.gz"
gzip -t "${tmp}/images/00-hyperfilelens.tar.gz"
cp "${backend_meta}" "${tmp}/metadata/hfl-backend.json"
cp "${frontend_meta}" "${tmp}/metadata/hfl-frontend.json"
mkdir -p "$(dirname "${output}")"
tar -C "${tmp}" -czf "${output}" images metadata

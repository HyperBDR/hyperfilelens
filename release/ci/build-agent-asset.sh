#!/usr/bin/env bash
# Build one Agent matrix entry and package its release payload for CI assembly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

[[ $# -eq 4 ]] || {
	printf 'Usage: %s GOOS:GOARCH VERSION COMMIT OUTPUT_TAR_GZ\n' "$0" >&2
	exit 2
}
matrix=$1
version=${2#v}
commit=$3
output=$4

case "${matrix}" in
linux:amd64) bundle=all ;;
linux:arm64 | darwin:amd64 | darwin:arm64 | windows:amd64) bundle=standard ;;
*) printf 'ERROR: unsupported Agent matrix entry: %s\n' "${matrix}" >&2; exit 2 ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
releases="${tmp}/payload/media/agent-releases"
args=(
	--bundle "${bundle}"
	--version "${version}"
	--commit "${commit}"
	--matrix "${matrix}"
	--releases-dir "${releases}"
)
if [[ "${matrix}" == "linux:amd64" ]]; then
	args+=(--ubuntu2404-arch amd64)
fi
"${ROOT}/tools/agent/publish.sh" "${args[@]}"

mkdir -p "$(dirname "${output}")"
tar -C "${tmp}" -czf "${output}" payload

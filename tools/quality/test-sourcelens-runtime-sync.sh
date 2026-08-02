#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp=$(mktemp -d)
trap 'rm -rf "${tmp}"' EXIT

ROOT="${tmp}/installed"
SOURCELENS_INSTALL_DIR="${ROOT}/sourcelens"
source_root="${tmp}/release"

step() { :; }
log() { :; }
sync_default_tls_bundle() { :; }
read_version_from_dir() { printf 'main-0123456'; }

source <(
	sed -n '/^repair_sourcelens_runtime_bindings()/,/^prepare_upgrade_source()/p' \
		"${installer}" | sed '$d'
)

mkdir -p \
	"${ROOT}/data/sourcelens/config" \
	"${ROOT}/data/sourcelens/workspace" \
	"${ROOT}/sourcelens" \
	"${source_root}/payload" \
	"${source_root}/images" \
	"${source_root}/sourcelens/data" \
	"${source_root}/deploy/nginx/snippets" \
	"${source_root}/deploy/blue-green"

printf 'persisted=true\n' >"${ROOT}/data/sourcelens/config/.env"
printf 'protected repository data\n' >"${ROOT}/data/sourcelens/workspace/keep.txt"
ln -s "${ROOT}/data/sourcelens/config/.env" "${ROOT}/sourcelens/.env"
ln -s "${ROOT}/data/sourcelens" "${ROOT}/sourcelens/data"
printf 'remove me\n' >"${ROOT}/sourcelens/stale-app-file"

printf 'packaged=true\n' >"${source_root}/sourcelens/.env"
printf 'do not materialize\n' >"${source_root}/sourcelens/data/package-data"
printf 'services: {}\n' >"${source_root}/sourcelens/docker-compose.yml"
printf 'new application file\n' >"${source_root}/sourcelens/new-app-file"
printf 'services: {}\n' >"${source_root}/docker-compose.yml"
printf 'server {}\n' >"${source_root}/deploy/nginx/default.conf"
printf 'server {}\n' >"${source_root}/deploy/nginx/web.conf"
printf 'upstream api {}\n' >"${source_root}/deploy/nginx/snippets/hfl-active-upstreams.conf"
printf 'blue\n' >"${source_root}/deploy/blue-green/active-color"
printf '{}\n' >"${source_root}/MANIFEST.json"

apply_upgrade_files "${source_root}" 0 1

[[ -L "${ROOT}/sourcelens/.env" ]]
[[ "$(readlink "${ROOT}/sourcelens/.env")" == "${ROOT}/data/sourcelens/config/.env" ]]
[[ -L "${ROOT}/sourcelens/data" ]]
[[ "$(readlink "${ROOT}/sourcelens/data")" == "${ROOT}/data/sourcelens" ]]
grep -F 'persisted=true' "${ROOT}/sourcelens/.env" >/dev/null
grep -F 'protected repository data' "${ROOT}/sourcelens/data/workspace/keep.txt" >/dev/null
[[ ! -e "${ROOT}/sourcelens/data/package-data" ]]
[[ ! -e "${ROOT}/sourcelens/stale-app-file" ]]
grep -F 'new application file' "${ROOT}/sourcelens/new-app-file" >/dev/null

# Repair the exact partial-upgrade state observed on TEST: persistent state is
# present, but a previous application sync removed both runtime links.
rm "${ROOT}/sourcelens/.env" "${ROOT}/sourcelens/data"
apply_upgrade_files "${source_root}" 0 1
[[ -L "${ROOT}/sourcelens/.env" ]]
[[ -L "${ROOT}/sourcelens/data" ]]
grep -F 'persisted=true' "${ROOT}/sourcelens/.env" >/dev/null
grep -F 'protected repository data' "${ROOT}/sourcelens/data/workspace/keep.txt" >/dev/null

python3 - "${installer}" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
upgrade = text[text.index("cmd_upgrade() {") : text.index("\nmain() {")]
assert upgrade.index("repair_sourcelens_runtime_bindings") < upgrade.index(
    "create_managed_backup"
)
assert upgrade.index("repair_sourcelens_runtime_bindings") < upgrade.index(
    'if sourcelens_installed && sourcelens_compose ps -q'
)
PY

printf 'SourceLens runtime sync checks passed.\n'

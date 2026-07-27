#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

ROOT="${tmp}/install"
mkdir -p "${ROOT}/backup/upgrade-20260727-010000" "${tmp}/bin"
cat >"${ROOT}/MANIFEST.json" <<'JSON'
{"images":[{"refs":["hyperfilelens-backend:0.1.8","hyperfilelens-backend:latest"]}]}
JSON
cat >"${ROOT}/backup/upgrade-20260727-010000/MANIFEST.json" <<'JSON'
{"images":[{"refs":["hyperfilelens-backend:0.1.7"]}]}
JSON

cat >"${tmp}/bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "$*" in
"info") ;;
"ps -aq --no-trunc") printf 'foreign-container\n' ;;
"inspect --format {{.Config.Image}} foreign-container") printf 'hyperfilelens-backend:0.1.6\n' ;;
"image ls --format {{.Repository}}:{{.Tag}}")
	printf '%s\n' \
		hyperfilelens-backend:latest \
		hyperfilelens-backend:0.1.8 \
		hyperfilelens-backend:0.1.7 \
		hyperfilelens-backend:0.1.6 \
		hyperfilelens-backend:0.1.5 \
		customer-backend:0.1.5
	;;
"image rm hyperfilelens-backend:0.1.5")
	printf '%s\n' 'hyperfilelens-backend:0.1.5' >>"${HFL_TEST_REMOVED_IMAGES}"
	;;
*) printf 'unexpected fake Docker invocation: %s\n' "$*" >&2; exit 1 ;;
esac
SH
chmod +x "${tmp}/bin/docker"
export PATH="${tmp}/bin:${PATH}"
export HFL_TEST_REMOVED_IMAGES="${tmp}/removed-images"

warn() { printf 'WARN: %s\n' "$*"; }
log() { printf 'INFO: %s\n' "$*"; }
source <(sed -n '/^prune_old_managed_image_refs()/,/^apply_upgrade_files()/p' "${installer}" | sed '$d')

prune_old_managed_image_refs
[[ "$(<"${HFL_TEST_REMOVED_IMAGES}")" == "hyperfilelens-backend:0.1.5" ]]
printf 'Managed image retention checks passed.\n'

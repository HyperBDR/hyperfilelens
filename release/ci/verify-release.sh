#!/usr/bin/env bash
# Validate a final release asset and optionally perform a full ephemeral install.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

install=0
archive=""
while [[ $# -gt 0 ]]; do
	case "$1" in
	--archive) archive=${2:-}; shift 2 ;;
	--install) install=1; shift ;;
	*) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
	esac
done
[[ -s "${archive}" ]] || { printf 'ERROR: release archive is missing\n' >&2; exit 2; }
gzip -t "${archive}"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
tar -xzf "${archive}" -C "${tmp}"
pkg_root="$(find "${tmp}" -mindepth 1 -maxdepth 1 -type d -name 'hyperfilelens-*' -print -quit)"
[[ -n "${pkg_root}" && -s "${pkg_root}/MANIFEST.json" ]] || {
	printf 'ERROR: invalid release package layout\n' >&2
	exit 1
}

python3 - "${pkg_root}" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
for image in manifest.get("images", []):
    path = root / image["file"]
    if not path.is_file():
        raise SystemExit(f"missing image archive: {image['file']}")
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    digest = checksum.hexdigest()
    if digest != image.get("sha256"):
        raise SystemExit(f"image checksum mismatch: {image['file']}")
tls_artifacts = (manifest.get("artifacts") or {}).get("default_tls") or {}
for artifact in tls_artifacts.values():
    path = root / artifact["file"]
    if not path.is_file():
        raise SystemExit(f"missing default TLS artifact: {artifact['file']}")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if checksum != artifact.get("sha256"):
        raise SystemExit(f"default TLS checksum mismatch: {artifact['file']}")
if len(tls_artifacts) != 3:
    raise SystemExit("release manifest must describe three default TLS artifacts")
print(
    f"verified {len(manifest.get('images', []))} image archives "
    f"and {len(tls_artifacts)} default TLS artifacts"
)
PY

(
	cd "${pkg_root}/deploy/nginx/certs"
	sha256sum --strict --check SHA256SUMS
)
openssl verify -CAfile "${pkg_root}/deploy/nginx/certs/root-ca.crt" \
	"${pkg_root}/deploy/nginx/certs/tls.crt" >/dev/null

while IFS= read -r image_archive; do
	gzip -t "${image_archive}"
done < <(find "${pkg_root}/images" -maxdepth 1 -type f -name '*.tar.gz' | sort)
"${ROOT}/tools/quality/check-release-contracts.sh"

if [[ "${install}" -ne 1 ]]; then
	printf 'Release structure verification passed: %s\n' "${archive}"
	exit 0
fi

available_kib="$(df -Pk / | awk 'NR == 2 {print $4}')"
((available_kib >= 8 * 1024 * 1024)) || {
	printf 'ERROR: full install verification requires at least 8 GiB free\n' >&2
	exit 1
}

smoke_host="${SMOKE_HOST:-host.docker.internal}"
wait_for_release_services() {
	local deadline=$((SECONDS + 600))
	while ((SECONDS < deadline)); do
		if curl -kfsS https://127.0.0.1:11443/health/ready >/dev/null \
			&& curl -kfsS https://127.0.0.1:11444/ >/dev/null \
			&& curl -kfsS https://127.0.0.1:11445/ >/dev/null; then
			return 0
		fi
		sleep 5
	done
	docker compose -f /opt/hyperfilelens/docker-compose.yml --env-file /opt/hyperfilelens/.env ps || true
	printf 'ERROR: release services did not become ready\n' >&2
	return 1
}

sudo env HFL_PUBLIC_HOST="${smoke_host}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
	bash "${pkg_root}/install.sh" install
wait_for_release_services

printf 'Running same-version in-place upgrade verification\n'
sudo env HFL_PUBLIC_HOST="${smoke_host}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
	bash "${pkg_root}/install.sh" upgrade --from "${pkg_root}" --yes
wait_for_release_services

export HFL_TENANT_PORT=11443
export HFL_ADMIN_PORT=11444
export SOURCELENS_CONSOLE_PORT=11445
export SMOKE_HOST="${smoke_host}"
export SEED_ADMIN_EMAIL
export SEED_ADMIN_PASSWORD
SEED_ADMIN_EMAIL="$(sudo sed -n 's/^SEED_ADMIN_EMAIL=//p' /opt/hyperfilelens/.env | head -1)"
SEED_ADMIN_PASSWORD="$(sudo sed -n 's/^SEED_ADMIN_PASSWORD=//p' /opt/hyperfilelens/.env | head -1)"
export SMOKE_REQUIRE_HMR=0
export SMOKE_SOURCELENS_ENV_FILE=/opt/hyperfilelens/data/sourcelens/config/.env
sudo env \
	HFL_TENANT_PORT="${HFL_TENANT_PORT}" \
	HFL_ADMIN_PORT="${HFL_ADMIN_PORT}" \
	SOURCELENS_CONSOLE_PORT="${SOURCELENS_CONSOLE_PORT}" \
	SMOKE_HOST="${SMOKE_HOST}" \
	SEED_ADMIN_EMAIL="${SEED_ADMIN_EMAIL}" \
	SEED_ADMIN_PASSWORD="${SEED_ADMIN_PASSWORD}" \
	SMOKE_REQUIRE_HMR="${SMOKE_REQUIRE_HMR}" \
	SMOKE_SOURCELENS_ENV_FILE="${SMOKE_SOURCELENS_ENV_FILE}" \
	"${ROOT}/tools/dev/browser-smoke.sh"
printf 'Full release install, upgrade, and login verification passed\n'

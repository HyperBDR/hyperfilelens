#!/usr/bin/env bash
# Download one published HFL release on the target host and install or upgrade it.
set -euo pipefail

REPOSITORY="HyperBDR/hyperfilelens"
TAG=""
INSTALL_DIR="/opt/hyperfilelens"
PUBLIC_HOST=""
RUNTIME_ENV_FILE=""

usage() {
	cat <<'USAGE'
Usage: remote-deploy.sh --tag vX.Y.Z --public-host HOST [options]

  --repository OWNER/REPO  Public GitHub repository (default: HyperBDR/hyperfilelens)
  --install-dir DIR        HFL install directory (default: /opt/hyperfilelens)
  --runtime-env-file PATH  Root-only staged runtime configuration under /var/tmp
USAGE
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--tag) TAG=${2:-}; shift 2 ;;
	--public-host) PUBLIC_HOST=${2:-}; shift 2 ;;
	--repository) REPOSITORY=${2:-}; shift 2 ;;
	--install-dir) INSTALL_DIR=${2:-}; shift 2 ;;
	--runtime-env-file) RUNTIME_ENV_FILE=${2:-}; shift 2 ;;
	-h | --help) usage; exit 0 ;;
	*) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
	esac
done

[[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'ERROR: invalid release tag\n' >&2; exit 2; }
[[ "${REPOSITORY}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { printf 'ERROR: invalid repository\n' >&2; exit 2; }
[[ "${INSTALL_DIR}" == /opt/hyperfilelens ]] || {
	printf 'ERROR: current HFL installer supports /opt/hyperfilelens only\n' >&2
	exit 2
}
[[ -n "${PUBLIC_HOST}" && "${PUBLIC_HOST}" != *[[:space:]]* ]] || {
	printf 'ERROR: --public-host is required\n' >&2
	exit 2
}
if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
	[[ "${RUNTIME_ENV_FILE}" =~ ^/var/tmp/hyperfilelens-runtime-[0-9]+\.env$ ]] || {
		printf 'ERROR: invalid --runtime-env-file path\n' >&2
		exit 2
	}
	[[ -f "${RUNTIME_ENV_FILE}" && ! -L "${RUNTIME_ENV_FILE}" ]] || {
		printf 'ERROR: staged runtime configuration is missing or unsafe\n' >&2
		exit 2
	}
	chmod 0600 "${RUNTIME_ENV_FILE}"
fi
command -v curl >/dev/null || { printf 'ERROR: curl is required\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'ERROR: python3 is required\n' >&2; exit 1; }
command -v flock >/dev/null || { printf 'ERROR: flock is required\n' >&2; exit 1; }

exec 9>/var/lock/hyperfilelens-deploy.lock
if ! flock -n 9; then
	printf 'ERROR: another HFL deployment is running\n' >&2
	exit 1
fi

work="$(mktemp -d /var/tmp/hyperfilelens-deploy.XXXXXX)"
cleanup() {
	rm -rf "${work}"
	if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
		rm -f -- "${RUNTIME_ENV_FILE}"
	fi
}
trap cleanup EXIT INT TERM
api="https://api.github.com/repos/${REPOSITORY}/releases/tags/${TAG}"
printf '[deploy] Resolving published release %s\n' "${TAG}"
curl -fsSL --retry 5 --retry-all-errors --connect-timeout 20 "${api}" -o "${work}/release.json"

python3 - "${work}/release.json" "${work}/assets.tsv" "${TAG}" <<'PY'
import json
import pathlib
import re
import sys

release = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
tag = sys.argv[3]
if release.get("draft"):
    raise SystemExit("release is still a draft")
if release.get("tag_name") != tag:
    raise SystemExit("release tag does not match the requested tag")
assets = {item["name"]: item["browser_download_url"] for item in release.get("assets", [])}
selected = {}
if "SHA256SUMS" not in assets:
    raise SystemExit("release has no SHA256SUMS")
selected["SHA256SUMS"] = assets["SHA256SUMS"]
prefix = re.escape(f"hyperfilelens-{tag.removeprefix('v')}-")
full = sorted(name for name in assets if re.fullmatch(prefix + r"[0-9a-f]{7}\.tar\.gz", name))
if len(full) == 1:
    selected[full[0]] = assets[full[0]]
else:
    parts = sorted(
        name
        for name in assets
        if re.fullmatch(prefix + r"[0-9a-f]{7}\.tar\.gz\.part-[0-9]{3}", name)
    )
    if not parts:
        raise SystemExit("release has neither one full package nor package parts")
    for name in parts:
        selected[name] = assets[name]
pathlib.Path(sys.argv[2]).write_text(
    "".join(f"{name}\t{url}\n" for name, url in selected.items()),
    encoding="utf-8",
)
PY

total_bytes="$(python3 - "${work}/release.json" "${work}/assets.tsv" <<'PY'
import json, pathlib, sys
release = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
selected = {line.split("\t", 1)[0] for line in pathlib.Path(sys.argv[2]).read_text().splitlines()}
print(sum(int(asset.get("size", 0)) for asset in release.get("assets", []) if asset.get("name") in selected))
PY
)"
available_bytes="$(df -PB1 /opt | awk 'NR == 2 {print $4}')"
required_bytes=$((total_bytes * 4 + 4 * 1024 * 1024 * 1024))
if ((available_bytes < required_bytes)); then
	printf 'ERROR: insufficient disk: available=%s required=%s\n' "${available_bytes}" "${required_bytes}" >&2
	exit 1
fi

while IFS=$'\t' read -r name url; do
	[[ "${name}" =~ ^[A-Za-z0-9._-]+$ ]] || { printf 'ERROR: unsafe asset name\n' >&2; exit 1; }
	printf '[deploy] Downloading %s\n' "${name}"
	curl -fL --retry 5 --retry-all-errors --connect-timeout 20 "${url}" -o "${work}/${name}"
done <"${work}/assets.tsv"

package="$(find "${work}" -maxdepth 1 -type f -name 'hyperfilelens-*.tar.gz' -print -quit)"
if [[ -z "${package}" ]]; then
	first_part="$(find "${work}" -maxdepth 1 -type f -name 'hyperfilelens-*.tar.gz.part-000' -print -quit)"
	[[ -n "${first_part}" ]] || { printf 'ERROR: package parts are missing\n' >&2; exit 1; }
	package="${first_part%.part-000}"
	cat "${package}.part-"* >"${package}"
fi
package_name="$(basename "${package}")"
expected="$(awk -v file="${package_name}" '$2 == file || $2 == "*" file {print $1; exit}' "${work}/SHA256SUMS")"
if [[ -n "${expected}" ]]; then
	printf '%s  %s\n' "${expected}" "${package}" | sha256sum -c -
else
	# Split releases checksum every part; validate all downloaded parts before use.
	while IFS= read -r part; do
		name="$(basename "${part}")"
		expected="$(awk -v file="${name}" '$2 == file || $2 == "*" file {print $1; exit}' "${work}/SHA256SUMS")"
		[[ -n "${expected}" ]] || { printf 'ERROR: no checksum for %s\n' "${name}" >&2; exit 1; }
		printf '%s  %s\n' "${expected}" "${part}" | sha256sum -c -
	done < <(find "${work}" -maxdepth 1 -type f -name '*.part-*' | sort)
fi

mkdir -p "${work}/extract"
tar -xzf "${package}" -C "${work}/extract"
package_root="$(find "${work}/extract" -mindepth 1 -maxdepth 1 -type d -name 'hyperfilelens-*' -print -quit)"
[[ -n "${package_root}" && -x "${package_root}/install.sh" ]] || {
	printf 'ERROR: invalid HFL package layout\n' >&2
	exit 1
}

if [[ -f "${INSTALL_DIR}/.env" && -f "${INSTALL_DIR}/VERSION" ]]; then
	printf '[deploy] Upgrading installed HFL to %s\n' "${TAG}"
	HFL_PUBLIC_HOST="${PUBLIC_HOST}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
		bash "${INSTALL_DIR}/install.sh" upgrade --from "${package_root}" --yes
else
	printf '[deploy] Installing HFL %s\n' "${TAG}"
	HFL_PUBLIC_HOST="${PUBLIC_HOST}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
		bash "${package_root}/install.sh" install
fi

if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
	printf '[deploy] Applying staged runtime configuration\n'
	python3 - "${INSTALL_DIR}/.env" "${RUNTIME_ENV_FILE}" <<'PY'
import os
import pathlib
import re
import sys

env_path = pathlib.Path(sys.argv[1])
staged_path = pathlib.Path(sys.argv[2])
allowed = {"CAPTCHA_PROVIDER", "TURNSTILE_SITE_KEY", "TURNSTILE_SECRET_KEY"}
values = {}
for raw_line in staged_path.read_text(encoding="utf-8").splitlines():
    if not raw_line or raw_line.startswith("#"):
        continue
    key, separator, value = raw_line.partition("=")
    if not separator or key not in allowed or not value or re.search(r"[\r\n]", value):
        raise SystemExit("invalid staged runtime configuration")
    values[key] = value
if set(values) != allowed or values["CAPTCHA_PROVIDER"] != "turnstile":
    raise SystemExit("incomplete staged Turnstile configuration")

lines = env_path.read_text(encoding="utf-8").splitlines()
updated = []
seen = set()
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in values:
        updated.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        updated.append(line)
for key in ("CAPTCHA_PROVIDER", "TURNSTILE_SITE_KEY", "TURNSTILE_SECRET_KEY"):
    if key not in seen:
        updated.append(f"{key}={values[key]}")

temporary = env_path.with_name(f"{env_path.name}.turnstile.tmp")
temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
os.chmod(temporary, 0o600)
os.replace(temporary, env_path)
PY
	rm -f -- "${RUNTIME_ENV_FILE}"
	RUNTIME_ENV_FILE=""
	printf '[deploy] Recreating HFL API with updated runtime configuration\n'
	(
		cd "${INSTALL_DIR}"
		docker compose --env-file .env -f docker-compose.yml up -d --force-recreate api
	)
fi

mkdir -p "${INSTALL_DIR}/packages"
install -m 0644 "${package}" "${INSTALL_DIR}/packages/${package_name}"
mapfile -t old_packages < <(find "${INSTALL_DIR}/packages" -maxdepth 1 -type f -name 'hyperfilelens-*.tar.gz' -printf '%T@ %p\n' | sort -nr | tail -n +3 | cut -d' ' -f2-)
if ((${#old_packages[@]})); then
	rm -f -- "${old_packages[@]}"
fi
printf '[deploy] HFL %s deployment completed\n' "${TAG}"

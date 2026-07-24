#!/usr/bin/env bash
# Download one published HFL release on the target host and install or upgrade it.
set -euo pipefail

REPOSITORY="HyperBDR/hyperfilelens"
TAG=""
CHANNEL="release"
INSTALL_DIR="/opt/hyperfilelens"
PUBLIC_URL=""
DIRECT_HOST=""
RUNTIME_ENV_FILE=""
DOWNLOAD_PROXY_URL=""

usage() {
	cat <<'USAGE'
Usage: remote-deploy.sh --tag vX.Y.Z|main-SHA7 --channel release|main --direct-host HOST [options]

  --repository OWNER/REPO  Public GitHub repository (default: HyperBDR/hyperfilelens)
	--channel CHANNEL       Artifact channel: release or main (default: release)
  --install-dir DIR        HFL install directory (default: /opt/hyperfilelens)
  --direct-host HOST       SSH-reachable host used for direct listener URLs
  --public-url URL         Optional canonical browser URL; external checks are non-blocking
  --runtime-env-file PATH  Root-only staged runtime configuration under /var/tmp
  --download-proxy-url URL Optional HTTP(S) proxy used only for GitHub Release downloads
USAGE
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--tag) TAG=${2:-}; shift 2 ;;
	--channel) CHANNEL=${2:-}; shift 2 ;;
	--public-url) PUBLIC_URL=${2:-}; shift 2 ;;
	--direct-host) DIRECT_HOST=${2:-}; shift 2 ;;
	--repository) REPOSITORY=${2:-}; shift 2 ;;
	--install-dir) INSTALL_DIR=${2:-}; shift 2 ;;
	--runtime-env-file) RUNTIME_ENV_FILE=${2:-}; shift 2 ;;
	--download-proxy-url) DOWNLOAD_PROXY_URL=${2:-}; shift 2 ;;
	-h | --help) usage; exit 0 ;;
	*) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
	esac
done

if [[ "${DOWNLOAD_PROXY_URL}" == "UNCONFIGURED" ]]; then
	DOWNLOAD_PROXY_URL=""
fi

case "${CHANNEL}" in
release) [[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'ERROR: invalid release tag\n' >&2; exit 2; } ;;
main) [[ "${TAG}" =~ ^main-[0-9a-f]{7}$ ]] || { printf 'ERROR: invalid main build identifier\n' >&2; exit 2; } ;;
*) printf 'ERROR: invalid artifact channel\n' >&2; exit 2 ;;
esac
[[ "${REPOSITORY}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { printf 'ERROR: invalid repository\n' >&2; exit 2; }
[[ "${INSTALL_DIR}" == /opt/hyperfilelens ]] || {
	printf 'ERROR: current HFL installer supports /opt/hyperfilelens only\n' >&2
	exit 2
}
[[ -n "${DIRECT_HOST}" && "${DIRECT_HOST}" != *[[:space:]]* ]] || {
	printf 'ERROR: --direct-host is required\n' >&2
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
if [[ -n "${DOWNLOAD_PROXY_URL}" ]]; then
	[[ "${DOWNLOAD_PROXY_URL}" =~ ^https?://[A-Za-z0-9.-]+:[0-9]{1,5}$ ]] || {
		printf 'ERROR: download proxy must use http://host:port or https://host:port without credentials\n' >&2
		exit 2
	}
	proxy_address="${DOWNLOAD_PROXY_URL#*://}"
	proxy_port="${proxy_address##*:}"
	((proxy_port >= 1 && proxy_port <= 65535)) || {
		printf 'ERROR: download proxy port is out of range\n' >&2
		exit 2
	}
fi
command -v curl >/dev/null || { printf 'ERROR: curl is required\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'ERROR: python3 is required\n' >&2; exit 1; }
command -v flock >/dev/null || { printf 'ERROR: flock is required\n' >&2; exit 1; }
docker_preexisting=0
if command -v docker >/dev/null 2>&1; then
	docker info >/dev/null 2>&1 || { printf 'ERROR: existing Docker daemon is not reachable\n' >&2; exit 1; }
	docker compose version >/dev/null 2>&1 || { printf 'ERROR: Docker Compose v2 is required\n' >&2; exit 1; }
	docker_preexisting=1
else
	printf '[deploy] Existing Docker not found; the verified offline release bundle will install Docker CE\n'
fi

# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID:-}" == "ubuntu" && ( "${VERSION_ID:-}" == "20.04" || "${VERSION_ID:-}" == "24.04" ) ]] || {
	printf 'ERROR: automated deployment supports Ubuntu 20.04 or 24.04 only\n' >&2
	exit 1
}
[[ "$(uname -m)" == "x86_64" ]] || { printf 'ERROR: automated deployment requires amd64\n' >&2; exit 1; }

exec 9>/var/lock/hyperfilelens-deploy.lock
if ! flock -n 9; then
	printf 'ERROR: another HFL deployment is running\n' >&2
	exit 1
fi

work="$(mktemp -d /var/tmp/hyperfilelens-deploy.XXXXXX)"

capture_unrelated_state() {
	local output=$1 raw_dir
	raw_dir="${output}.raw"
	local -a ids=()
	mkdir -p "${raw_dir}"
	mapfile -t ids < <(docker ps -aq --no-trunc)
	if ((${#ids[@]})); then
		docker inspect "${ids[@]}" >"${raw_dir}/containers.json"
	else
		printf '[]\n' >"${raw_dir}/containers.json"
	fi
	mapfile -t ids < <(docker network ls -q --no-trunc)
	if ((${#ids[@]})); then
		docker network inspect "${ids[@]}" >"${raw_dir}/networks.json"
	else
		printf '[]\n' >"${raw_dir}/networks.json"
	fi
	mapfile -t ids < <(docker volume ls -q)
	if ((${#ids[@]})); then
		docker volume inspect "${ids[@]}" >"${raw_dir}/volumes.json"
	else
		printf '[]\n' >"${raw_dir}/volumes.json"
	fi
	python3 - "${raw_dir}" "${output}" "${INSTALL_DIR}" <<'PY'
import json
import os
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
install_dir = os.path.realpath(sys.argv[3])
sl_dir = os.path.join(install_dir, "sourcelens")


def read(name):
    return json.loads((source / name).read_text(encoding="utf-8"))


def under(value, root):
    if not value:
        return False
    value = os.path.realpath(value)
    return value == root or value.startswith(root + os.sep)


def owned_container(labels):
    project = labels.get("com.docker.compose.project", "")
    working_dir = labels.get("com.docker.compose.project.working_dir", "")
    config_files = labels.get("com.docker.compose.project.config_files", "")
    paths = [working_dir]
    paths.extend(part.strip() for part in config_files.split(",") if part.strip())
    if project == "hyperfilelens":
        return any(under(path, install_dir) for path in paths)
    if project in {"hyperfilelens-sourcelens", "sourcelens"}:
        return any(under(path, sl_dir) for path in paths)
    if project == "hyperfilelens-gateway":
        return (
            labels.get("com.hyperfilelens.managed") == "true"
            and labels.get("com.hyperfilelens.component") == "gateway-lensnode"
        )
    return False


state = {"containers": {}, "networks": {}, "volumes": {}}
owned_container_ids = set()
owned_volume_names = set()
for container in read("containers.json"):
    labels = (container.get("Config") or {}).get("Labels") or {}
    if owned_container(labels):
        owned_container_ids.add(container.get("Id", ""))
        for mount in container.get("Mounts") or []:
            if mount.get("Type") == "volume" and mount.get("Name"):
                owned_volume_names.add(mount["Name"])
        continue
    name = str(container.get("Name", "")).lstrip("/")
    runtime = container.get("State") or {}
    state["containers"][name] = {
        "id": container.get("Id", ""),
        "status": runtime.get("Status", ""),
        "started_at": runtime.get("StartedAt", ""),
    }

owned_networks = {
    "hyperfilelens-bridge",
    "hyperfilelens_default",
    "hyperfilelens-sourcelens_default",
    "hyperfilelens-sourcelens_sourcelens_network",
}
for network in read("networks.json"):
    name = str(network.get("Name", ""))
    labels = network.get("Labels") or {}
    project = labels.get("com.docker.compose.project", "")
    attached = network.get("Containers") or {}
    ownership_marker = name in owned_networks or labels.get("com.hyperfilelens.managed") == "true" or project in {
        "hyperfilelens",
        "hyperfilelens-sourcelens",
        "hyperfilelens-gateway",
    }
    if ownership_marker and attached and set(attached).issubset(owned_container_ids):
        continue
    state["networks"][name] = {
        "id": network.get("Id", ""),
        "driver": network.get("Driver", ""),
        "scope": network.get("Scope", ""),
        "internal": network.get("Internal", False),
        "attachable": network.get("Attachable", False),
        "ingress": network.get("Ingress", False),
        "ipam": network.get("IPAM") or {},
        "options": network.get("Options") or {},
        "labels": labels,
        "containers": attached,
    }

for volume in read("volumes.json"):
    name = str(volume.get("Name", ""))
    labels = volume.get("Labels") or {}
    project = labels.get("com.docker.compose.project", "")
    if project in {"hyperfilelens", "hyperfilelens-sourcelens"} and name in owned_volume_names:
        continue
    state["volumes"][name] = {
        "driver": volume.get("Driver", ""),
        "mountpoint": volume.get("Mountpoint", ""),
        "options": volume.get("Options") or {},
        "labels": labels,
        "scope": volume.get("Scope", ""),
    }
target.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
	rm -rf "${raw_dir}"
}

verify_unrelated_state() {
	local before=$1 after=$2
	capture_unrelated_state "${after}"
	if ! cmp -s "${before}" "${after}"; then
		printf 'ERROR: unrelated Docker containers, networks, or volumes changed during HFL deployment\n' >&2
		diff -u "${before}" "${after}" >&2 || true
		return 1
	fi
	printf '[deploy] Verified that unrelated Docker containers, networks, and volumes are unchanged\n'
}

shared_host_guard_verified=0
if [[ "${docker_preexisting}" == "1" ]]; then
	capture_unrelated_state "${work}/unrelated-before.json"
else
	shared_host_guard_verified=1
fi
cleanup() {
	local status=$?
	trap - EXIT INT TERM
	if [[ "${docker_preexisting}" == "1" && "${shared_host_guard_verified}" != "1" ]]; then
		if ! verify_unrelated_state "${work}/unrelated-before.json" "${work}/unrelated-after.json"; then
			status=90
		fi
	fi
	rm -rf "${work}"
	if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
		rm -f -- "${RUNTIME_ENV_FILE}"
	fi
	exit "${status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
check_disk_capacity() {
	local total_bytes=$1 available_bytes required_bytes
	available_bytes="$(df -PB1 /opt | awk 'NR == 2 {print $4}')"
	required_bytes=$((total_bytes * 4 + 4 * 1024 * 1024 * 1024))
	if ((available_bytes < required_bytes)); then
		printf 'ERROR: insufficient disk: available=%s required=%s\n' "${available_bytes}" "${required_bytes}" >&2
		exit 1
	fi
}

download_release_file() {
	local url=$1 output=$2
	local -a curl_args=(
		-fL
		--retry 5
		--retry-connrefused
		--retry-delay 2
		--connect-timeout 20
	)
	if [[ -n "${DOWNLOAD_PROXY_URL}" ]]; then
		if curl "${curl_args[@]}" --proxy "${DOWNLOAD_PROXY_URL}" --noproxy '' \
			"${url}" -o "${output}"; then
			return 0
		fi
		printf 'WARNING: release download through the configured proxy failed; retrying directly\n' >&2
		rm -f -- "${output}"
	fi
	curl "${curl_args[@]}" --proxy '' "${url}" -o "${output}"
}

if [[ -n "${DOWNLOAD_PROXY_URL}" ]]; then
	printf '[deploy] Target-side Release download proxy is enabled\n'
fi
api="https://api.github.com/repos/${REPOSITORY}/releases/tags/${TAG}"
printf '[deploy] Resolving published release %s\n' "${TAG}"
download_release_file "${api}" "${work}/release.json"

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
if tag.startswith("main-"):
    package_pattern = re.escape(f"hyperfilelens-{tag}.tar.gz")
else:
    prefix = re.escape(f"hyperfilelens-{tag[1:]}-")
    package_pattern = prefix + r"[0-9a-f]{7}\.tar\.gz"
full = sorted(name for name in assets if re.fullmatch(package_pattern, name))
if len(full) == 1:
    selected[full[0]] = assets[full[0]]
else:
    parts = sorted(
        name
        for name in assets
        if re.fullmatch(package_pattern + r"\.part-[0-9]{3}", name)
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
check_disk_capacity "${total_bytes}"

while IFS=$'\t' read -r name url; do
	[[ "${name}" =~ ^[A-Za-z0-9._-]+$ ]] || { printf 'ERROR: unsafe asset name\n' >&2; exit 1; }
	printf '[deploy] Downloading %s\n' "${name}"
	download_release_file "${url}" "${work}/${name}"
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
python3 - "${package_root}/MANIFEST.json" "${CHANNEL}" "${TAG}" <<'PY'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_channel = sys.argv[2]
expected_id = sys.argv[3]
channel = str(manifest.get("channel") or "release")
if channel != expected_channel:
    raise SystemExit(f"package channel mismatch: {channel} != {expected_channel}")
artifact_id = str(manifest.get("artifact_id") or "")
if expected_channel == "release" and not artifact_id:
    artifact_id = "v" + str(manifest.get("version") or "")
if artifact_id != expected_id:
    raise SystemExit(f"package identity mismatch: {artifact_id} != {expected_id}")
PY

if [[ -f "${INSTALL_DIR}/.env" && -f "${INSTALL_DIR}/VERSION" ]]; then
	printf '[deploy] Upgrading installed HFL to %s\n' "${TAG}"
	install_args=(
		upgrade
		--from "${package_root}"
		--yes
		--direct-host "${DIRECT_HOST}"
		--public-url "${PUBLIC_URL}"
	)
	[[ "${CHANNEL}" == "main" ]] && install_args+=(--allow-main-build)
	if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
		install_args+=(--runtime-env-file "${RUNTIME_ENV_FILE}")
	fi
	HFL_PUBLIC_HOST="${DIRECT_HOST}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
		bash "${package_root}/install.sh" "${install_args[@]}"
else
	printf '[deploy] Installing HFL %s\n' "${TAG}"
	install_args=(
		install
		--direct-host "${DIRECT_HOST}"
		--public-url "${PUBLIC_URL}"
	)
	[[ "${CHANNEL}" == "main" ]] && install_args+=(--allow-main-build)
	if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
		install_args+=(--runtime-env-file "${RUNTIME_ENV_FILE}")
	fi
	HFL_PUBLIC_HOST="${DIRECT_HOST}" HFL_SHOW_GENERATED_CREDENTIALS=0 \
		bash "${package_root}/install.sh" "${install_args[@]}"
fi
if [[ -n "${RUNTIME_ENV_FILE}" ]]; then
	rm -f -- "${RUNTIME_ENV_FILE}"
	RUNTIME_ENV_FILE=""
fi

if [[ "${docker_preexisting}" == "1" ]]; then
	if verify_unrelated_state "${work}/unrelated-before.json" "${work}/unrelated-after.json"; then
		shared_host_guard_verified=1
	else
		shared_host_guard_verified=1
		exit 90
	fi
fi

mkdir -p "${INSTALL_DIR}/packages"
install -m 0644 "${package}" "${INSTALL_DIR}/packages/${package_name}"
mapfile -t old_packages < <(find "${INSTALL_DIR}/packages" -maxdepth 1 -type f -name 'hyperfilelens-*.tar.gz' -printf '%T@ %p\n' | sort -nr | tail -n +4 | cut -d' ' -f2-)
if ((${#old_packages[@]})); then
	rm -f -- "${old_packages[@]}"
fi
printf '[deploy] HFL %s deployment completed\n' "${TAG}"

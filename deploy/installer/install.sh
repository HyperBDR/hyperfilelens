#!/usr/bin/env bash
# HyperFileLens release package control (install / lifecycle / upgrade).
# Layout: <package-root>/install.sh  →  runtime install dir: /opt/hyperfilelens
set -euo pipefail

INSTALL_DIR="/opt/hyperfilelens"
SOURCELENS_INSTALL_DIR="${SOURCELENS_INSTALL_DIR:-${INSTALL_DIR}/sourcelens}"
HFL_BRIDGE_NETWORK="hyperfilelens-bridge"
UPGRADE_TMP="${INSTALL_DIR}/upgrade_tmp"
UPGRADE_YES=0
LANG_PACK_COMPOSE_FILE="docker-compose.yml"
LOG_FILE="${HFL_LOG_FILE:-}"
VERBOSE="${HFL_LOG_VERBOSE:-0}"
PRINT_CONFIG=0
SESSION_STARTED=0
PUBLIC_HOST="${HFL_PUBLIC_HOST:-}"
SHOW_GENERATED_CREDENTIALS="${HFL_SHOW_GENERATED_CREDENTIALS:-auto}"

usage() {
	cat <<'USAGE'
Usage: install.sh [command] [options]

When no command is given, equivalent to: install.sh install

Commands:
  install       Fresh install from this package and start services (install dir /opt/hyperfilelens)
  start         docker compose up -d --no-build
  stop          docker compose down
  restart       stop then start
  status        Show version and compose service status
  upgrade       In-place upgrade from another release package directory or .tar.gz
  uninstall     Stop and remove Docker containers and app images (does not remove the install dir; see uninstall options)
  lang-pack     Install, list, or remove optional runtime language packs

Options:
  global:
    --log-file FILE        Append runtime logs to FILE
    --verbose              Enable detailed logs
    --print-config         Print effective non-secret configuration and exit

  install:
    --with-sourcelens       Install bundled SourceLens (default when sourcelens/ is present)
    --hfl-only              Skip bundled SourceLens even when sourcelens/ is present

  upgrade:
    --from PATH             Path to new package directory or hyperfilelens-*.tar.gz (required)
                            Backs up .env and data/ to a timestamped tar.gz under backup/ before upgrade
                            Extracts the new package to upgrade_tmp, merges keys from its .env.example into .env,
                            overwrites app files, loads images, and restarts; removes upgrade_tmp on success
    --with-sourcelens       Upgrade bundled SourceLens when sourcelens/ is present (default when present)
    --hfl-only              Skip SourceLens upgrade even when sourcelens/ is present
    --remove-sourcelens     Stop and remove installed SourceLens under the HFL install root
    --purge-sourcelens-data Remove SourceLens data/ (with --remove-sourcelens or uninstall --with-sourcelens)
    --yes                   Non-interactive: continue when target version equals installed version

  uninstall:
    --with-sourcelens       Stop SourceLens stack and remove its application images
    --purge-sourcelens-data Remove SourceLens data under data/sourcelens/
    --purge-media           Remove published bootstrap and agent artifacts under data/media/
    --purge-config          Remove .env
    --purge-data            Remove data/
    --purge-all             Remove both data/ and .env

  lang-pack:
    install --file PATH     Validate and atomically install a language-pack .tar.gz
    list                    List installed language packs
    remove PACK_ID          Remove an installed language pack

    Uninstall never removes the install directory itself (${INSTALL_DIR} by default).
    Application files (install.sh, docker-compose.yml, images/, payload/, backup/, etc.)
    remain on disk. To remove them after uninstall, run manually, for example:
      sudo rm -rf ${INSTALL_DIR}
    Host Docker CE installed from the bundled OS-specific archive is not removed.

Examples:
  sudo ./install.sh
  sudo ./install.sh install
  sudo ./install.sh upgrade --from /path/to/hyperfilelens-0.1.0-<commit7>.tar.gz
  sudo ./install.sh uninstall
  sudo ./install.sh uninstall --purge-all
  sudo ./install.sh lang-pack install --file /path/to/hyperfilelens-lang-fr-0.1.0.tar.gz
  sudo ./install.sh lang-pack list
  sudo ./install.sh lang-pack remove fr
  sudo rm -rf ${INSTALL_DIR}   # optional: remove install dir after uninstall (not done by install.sh)
USAGE
}

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_finish_sentence() {
	local msg="$*"
	msg="${msg%"${msg##*[![:space:]]}"}"
	case "${msg}" in
	*.|*.?|*!) printf '%s' "${msg}" ;;
	*) printf '%s.' "${msg}" ;;
	esac
}

log() { printf '[%s] [INFO ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2; }
step() { printf '[%s] [STEP ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2; }
ok() { printf '[%s] [ OK  ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2; }
skip() { printf '[%s] [SKIP ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2; }
warn() { printf '[%s] [WARN ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2; }
debug() { [[ "${VERBOSE}" == "1" ]] && printf '[%s] [DEBUG] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "$*")" >&2 || true; }
die() { local message=$1 code=${2:-1}; printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$(hfl_finish_sentence "${message}")" >&2; exit "${code}"; }

configure_logging() {
	if [[ -n "${LOG_FILE}" ]]; then
		mkdir -p "$(dirname "${LOG_FILE}")"
		exec 2> >(tee -a "${LOG_FILE}" >&2)
	fi
}

finish_session() {
	local rc=${1:-$?}
	trap - EXIT
	if [[ "${SESSION_STARTED}" -eq 1 ]]; then
		SESSION_STARTED=0
		if [[ "${rc}" -eq 0 ]]; then
			ok "Installer session completed"
		else
			printf '[%s] [FAIL ] Installer session exited with status %s.\n' "$(hfl_now)" "${rc}" >&2
		fi
	fi
	exit "${rc}"
}

cleanup_upgrade_and_finish() {
	local rc=$?
	cleanup_upgrade_tmp
	finish_session "${rc}"
}

print_config() {
	local source_dir
	source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	cat <<EOF
package_root=${source_dir}
install_dir=${INSTALL_DIR}
sourcelens_install_dir=${SOURCELENS_INSTALL_DIR}
upgrade_tmp=${UPGRADE_TMP}
bridge_network=${HFL_BRIDGE_NETWORK}
public_host=${PUBLIC_HOST:-<auto>}
show_generated_credentials=${SHOW_GENERATED_CREDENTIALS}
log_file=${LOG_FILE:-<none>}
verbose=${VERBOSE}
EOF
}

# --- Safe path guards ---

safe_normalize_dir() {
	local path=$1
	path="${path%/}"
	[[ -n "${path}" ]] || die "empty path"
	printf '%s' "${path}"
}

safe_assert_absolute() {
	local path=$1 label=${2:-path}
	[[ "${path}" == /* ]] || die "${label} must be an absolute path: ${path}"
	[[ "${path}" != *$'\n'* && "${path}" != *$'\r'* ]] || die "${label} contains invalid characters"
	[[ "${path}" != *".."* ]] || die "${label} must not contain '..': ${path}"
}

safe_assert_path_under_dir() {
	local path=$1 root=$2 label=$3
	safe_assert_absolute "${path}" "${label}"
	root="$(safe_normalize_dir "${root}")"
	path="$(safe_normalize_dir "${path}")"
	[[ "${path}" == "${root}" || "${path}" == "${root}/"* ]] \
		|| die "${label} must stay under ${root}: ${path}"
}

safe_assert_removable_data_dir() {
	local path=$1 root=$2
	safe_assert_path_under_dir "${path}" "${root}" "data path"
	[[ "$(safe_normalize_dir "${path}")" == "$(safe_normalize_dir "${root}")/data" ]] \
		|| die "refusing to remove unexpected data path: ${path}"
}

safe_assert_env_file() {
	local path=$1 root=$2
	root="$(safe_normalize_dir "${root}")"
	[[ "${path}" == "${root}/.env" ]] || die "refusing to remove unexpected env file: ${path}"
}

safe_assert_package_basename() {
	local name=$1
	[[ "${name}" =~ ^hyperfilelens-[0-9][0-9A-Za-z._-]*-[0-9a-fA-F]{7}\.tar\.gz$ ]] \
		|| die "invalid release package basename: ${name}"
	[[ "${name}" != */* ]] || die "package basename must not contain slashes: ${name}"
}

safe_assert_upgrade_package_file() {
	local path=$1
	safe_assert_absolute "${path}" "upgrade package file"
	safe_assert_package_basename "$(basename "${path}")"
	[[ -f "${path}" ]] || die "upgrade package not found: ${path}"
}

safe_assert_package_root() {
	local root=$1
	safe_assert_absolute "${root}" "package root"
	[[ -f "${root}/docker-compose.yml" && -f "${root}/MANIFEST.json" ]] \
		|| die "path does not look like a HyperFileLens package root: ${root}"
}

safe_rm_file() {
	local file=$1
	[[ -n "${file}" && "${file}" != "/" ]] || die "refusing to remove unsafe file path"
	rm -f "${file}"
}

safe_rm_dir() {
	local dir=$1
	[[ -n "${dir}" && "${dir}" != "/" ]] || die "refusing to remove unsafe directory path"
	rm -rf "${dir}"
}

# --- Host / Docker ---

require_root_or_sudo() {
	if [[ "${EUID}" -eq 0 ]]; then
		return 0
	fi
	if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
		return 0
	fi
	die "this operation requires root or passwordless sudo"
}

run_as_root() {
	if [[ "${EUID}" -eq 0 ]]; then
		"$@"
	else
		sudo "$@"
	fi
}

assert_host_os() {
	local id version_id arch
	[[ -f /etc/os-release ]] || die "missing /etc/os-release (Ubuntu 20.04/24.04 amd64 only)"
	# shellcheck disable=SC1091
	source /etc/os-release
	id="${ID:-}"
	version_id="${VERSION_ID:-}"
	arch="$(uname -m)"
	[[ "${id}" == "ubuntu" && ( "${version_id}" == "20.04" || "${version_id}" == "24.04" ) ]] \
		|| die "host must be Ubuntu 20.04 or 24.04 (current: ${id:-unknown} ${version_id:-unknown})"
	[[ "${arch}" == "x86_64" ]] || die "host must be amd64/x86_64 (current: ${arch})"
}

docker_engine_version() {
	docker version --format '{{.Server.Version}}' 2>/dev/null || true
}

docker_compose_version() {
	if docker compose version >/dev/null 2>&1; then
		docker compose version --short 2>/dev/null || docker compose version 2>/dev/null | awk '{print $NF}'
		return 0
	fi
	printf ''
}

docker_version_ge() {
	python3 - "$1" "$2" <<'PY'
import sys

def parse(v):
    parts = []
    for chunk in v.lstrip("vV").replace("-", ".").split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num or 0))
    return tuple(parts)

try:
    sys.exit(0 if parse(sys.argv[1]) >= parse(sys.argv[2]) else 1)
except Exception:
    sys.exit(1)
PY
}

docker_runtime_ready() {
	local min_version="${1:-24.0.0}"
	command -v docker >/dev/null 2>&1 || return 1
	docker info >/dev/null 2>&1 || return 1
	local engine compose
	engine="$(docker_engine_version)"
	[[ -n "${engine}" ]] || return 1
	docker_version_ge "${engine}" "${min_version}" || return 1
	compose="$(docker_compose_version)"
	[[ -n "${compose}" ]] || return 1
	docker_version_ge "${compose}" "2.20.0" || return 1
	return 0
}

manifest_min_engine_version() {
	python3 - "${ROOT}/MANIFEST.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.is_file():
    print("24.0.0")
    raise SystemExit(0)
data = json.loads(path.read_text(encoding="utf-8"))
host = data.get("host_runtime") or {}
docker = host.get("docker") or {}
print(docker.get("min_engine_version") or "24.0.0")
PY
}

ensure_host_docker() {
	local root=$1
	local min_version installer
	assert_host_os
	require_root_or_sudo
	min_version="$(manifest_min_engine_version)"
	installer="${root}/payload/media/gateway-bootstrap/gateway-install-docker-ubuntu-amd64.sh"
	[[ -x "${installer}" ]] || die "release package is missing the offline Docker installer"
	run_as_root env \
		HFL_GATEWAY_BOOTSTRAP_BASE="file://${root}/payload/media/gateway-bootstrap" \
		HFL_INSECURE_TLS=0 HFL_DOCKER_MIN_ENGINE="${min_version}" \
		bash "${installer}"
	docker_runtime_ready "${min_version}" || die "Docker post-install self-check failed"
}

upgrade_host_docker_from_source() {
	local source_root=$2
	ensure_host_docker "${source_root}"
}

# --- Package layout ---

resolve_source_root() {
	local dir
	dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	[[ -f "${dir}/docker-compose.yml" ]] || die "release package root not found (missing docker-compose.yml)"
	printf '%s' "${dir}"
}

materialize_to_install_dir() {
	local source=$1
	source="$(safe_normalize_dir "${source}")"
	INSTALL_DIR="$(safe_normalize_dir "${INSTALL_DIR}")"
	if [[ "${source}" == "${INSTALL_DIR}" ]]; then
		log "already in install directory ${INSTALL_DIR}"
		return 0
	fi
	step "Copying release package ${source} -> ${INSTALL_DIR} ..."
	require_root_or_sudo
	run_as_root mkdir -p "${INSTALL_DIR}"
	if command -v rsync >/dev/null 2>&1; then
		run_as_root rsync -a \
			--exclude '.env' --exclude 'data/' --exclude 'backup/' --exclude 'upgrade_tmp/' \
			"${source}/" "${INSTALL_DIR}/"
	else
		die "rsync is required to copy the release package to ${INSTALL_DIR}"
	fi
	log "Copy complete"
}

init_install_root() {
	local source
	source="$(resolve_source_root)"
	materialize_to_install_dir "${source}"
	ROOT="${INSTALL_DIR}"
	safe_assert_package_root "${ROOT}"
}

require_docker() {
	command -v docker >/dev/null 2>&1 || die "docker command not found"
	docker info >/dev/null 2>&1 || die "cannot connect to Docker daemon"
	docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"
	COMPOSE=(docker compose)
}

compose_in_root() {
	(
		cd "${ROOT}"
		"${COMPOSE[@]}" --env-file "${ROOT}/.env" -f "${ROOT}/docker-compose.yml" "$@"
	)
}

container_owned_by_installation() {
	local container_id=$1 project working_dir config_files expected_dir
	project="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "${container_id}" 2>/dev/null || true)"
	working_dir="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "${container_id}" 2>/dev/null || true)"
	config_files="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "${container_id}" 2>/dev/null || true)"
	case "${project}" in
	hyperfilelens) expected_dir="${ROOT}" ;;
	hyperfilelens-sourcelens | sourcelens) expected_dir="${ROOT}/sourcelens" ;;
	*) return 1 ;;
	esac
	[[ "${working_dir}" == "${expected_dir}" \
		|| ",${config_files}," == *",${expected_dir}/docker-compose.yml,"* ]]
}

ensure_bridge_network() {
	if docker network inspect "${HFL_BRIDGE_NETWORK}" >/dev/null 2>&1; then
		local container_id project
		while IFS= read -r container_id; do
			[[ -n "${container_id}" ]] || continue
			project="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "${container_id}" 2>/dev/null || true)"
			container_owned_by_installation "${container_id}" \
				|| die "network ${HFL_BRIDGE_NETWORK} is attached to non-HFL container ${container_id} (project ${project:-unknown})"
		done < <(docker network inspect --format '{{range $id, $_ := .Containers}}{{println $id}}{{end}}' "${HFL_BRIDGE_NETWORK}")
		return 0
	fi
	log "Creating shared bridge network ${HFL_BRIDGE_NETWORK}"
	docker network create --label com.hyperfilelens.managed=true "${HFL_BRIDGE_NETWORK}" >/dev/null
}

preflight_install_capacity() {
	local cpu_count mem_total_kib mem_available_kib disk_available_bytes
	local tenant_bind tenant_port admin_bind admin_port sourcelens_bind sourcelens_port
	cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 0)"
	[[ "${cpu_count}" =~ ^[0-9]+$ && "${cpu_count}" -ge 2 ]] \
		|| die "at least 2 CPU cores are required (detected ${cpu_count:-unknown})"
	mem_total_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)"
	mem_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)"
	[[ "${mem_total_kib:-0}" -ge $((3500 * 1024)) ]] \
		|| die "at least 4 GB RAM is required"
	[[ "${mem_available_kib:-0}" -ge $((2500 * 1024)) ]] \
		|| die "at least 2.5 GiB available memory is required before installation"
	disk_available_bytes="$(df -PB1 "$(dirname "${INSTALL_DIR}")" | awk 'NR == 2 {print $4}')"
	[[ "${disk_available_bytes:-0}" -ge $((20 * 1024 * 1024 * 1024)) ]] \
		|| die "at least 20 GiB free disk space is required under $(dirname "${INSTALL_DIR}")"
	tenant_bind="$(read_env_value HFL_TENANT_BIND_ADDRESS)"
	tenant_port="$(read_env_value HFL_TENANT_PORT)"
	admin_bind="$(read_env_value HFL_ADMIN_BIND_ADDRESS)"
	admin_port="$(read_env_value HFL_ADMIN_PORT)"
	sourcelens_bind="$(read_env_value SOURCELENS_CONSOLE_BIND_ADDRESS)"
	sourcelens_port="$(read_env_value SOURCELENS_CONSOLE_PORT)"
	python3 - \
		"${tenant_bind:-0.0.0.0}" "${tenant_port:-11443}" \
		"${admin_bind:-0.0.0.0}" "${admin_port:-11444}" \
		"${sourcelens_bind:-0.0.0.0}" "${sourcelens_port:-11445}" <<'PY'
import socket
import sys

arguments = iter(sys.argv[1:])
for bind_address, raw_port in zip(arguments, arguments):
    port = int(raw_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.bind((bind_address, port))
    except OSError as exc:
        raise SystemExit(f"host endpoint {bind_address}:{port} is unavailable: {exc}") from exc
    finally:
        sock.close()
PY
	ok "Host capacity and ports satisfy the 2 CPU / 4 GB installation profile"
}

read_version_from_dir() {
	local dir=$1
	if [[ -f "${dir}/VERSION" ]]; then
		tr -d ' \t\r\n' < "${dir}/VERSION"
	elif [[ -f "${dir}/MANIFEST.json" ]]; then
		python3 -c "import json; print(json.load(open('${dir}/MANIFEST.json'))['version'])"
	else
		die "cannot read version from ${dir} (missing VERSION and MANIFEST.json)"
	fi
}

read_version() {
	read_version_from_dir "${ROOT}"
}

random_hex() {
	if command -v openssl >/dev/null 2>&1; then
		openssl rand -hex 32
	else
		python3 -c "import secrets; print(secrets.token_hex(32))"
	fi
}

ensure_data_dirs() {
	mkdir -p \
		"${ROOT}/data/postgresql" \
		"${ROOT}/data/redis" \
		"${ROOT}/data/logs" \
		"${ROOT}/data/lang-packs" \
		"${ROOT}/data/media/agent-releases" \
		"${ROOT}/data/media/enroll-bootstrap" \
		"${ROOT}/data/media/gateway-bootstrap" \
		"${ROOT}/data/media/snapshot-downloads" \
		"${ROOT}/data/staticfiles" \
		"${ROOT}/data/sourcelens/config"
}

sync_runtime_media() {
	local packaged_media="${ROOT}/payload/media"
	[[ -d "${packaged_media}" ]] || return 0
	mkdir -p "${ROOT}/data/media"
	rsync -a "${packaged_media}/" "${ROOT}/data/media/"
	local dir
	for dir in agent-releases enroll-bootstrap gateway-bootstrap; do
		[[ -d "${ROOT}/data/media/${dir}" ]] || continue
		find "${ROOT}/data/media/${dir}" -type d -exec chmod 755 {} +
		find "${ROOT}/data/media/${dir}" -type f -exec chmod 644 {} +
	done
	find "${ROOT}/data/media/agent-releases" -type f -name '*.sh' \
		-exec chmod 755 {} + 2>/dev/null || true
	if [[ -d "${ROOT}/data/media/enroll-bootstrap" ]]; then
		find "${ROOT}/data/media/enroll-bootstrap" -type f -exec chmod 755 {} +
	fi
	find "${ROOT}/data/media/gateway-bootstrap" -type f -name '*.sh' \
		-exec chmod 755 {} + 2>/dev/null || true
}

ensure_tls_certs() {
	local cert="${ROOT}/deploy/nginx/certs/tls.crt"
	local key="${ROOT}/deploy/nginx/certs/tls.key"
	mkdir -p "${ROOT}/deploy/nginx/certs"
	if [[ -s "${cert}" && -s "${key}" ]]; then
		log "TLS certificates already exist"
		return 0
	fi
	command -v openssl >/dev/null 2>&1 || die "openssl is required to generate self-signed TLS certificates"
	step "Generating self-signed TLS certificates (deploy/nginx/certs/)..."
	local san_dns="DNS:localhost"
	local san_ip="IP:127.0.0.1,IP:::1"
	if [[ -f "${ROOT}/.env" ]]; then
		local env_ip env_dns
		env_ip="$(grep -E '^HFL_TLS_SAN_IP=' "${ROOT}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' \"')"
		env_dns="$(grep -E '^HFL_TLS_SAN_DNS=' "${ROOT}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' \"')"
		if [[ -n "${env_ip}" ]]; then
			san_ip="IP:127.0.0.1,IP:::1,IP:${env_ip}"
		fi
		if [[ -n "${env_dns}" ]]; then
			san_dns="DNS:localhost,${env_dns}"
		fi
	fi
	openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
		-keyout "${key}" \
		-out "${cert}" \
		-subj "/CN=localhost" \
		-addext "subjectAltName=${san_dns},${san_ip}" 2>/dev/null
	chmod 600 "${key}"
	log "TLS certificates generated"
}

ensure_env_file() {
	local env_file="${ROOT}/.env"
	local example="${ROOT}/.env.example"
	[[ -f "${example}" ]] || die "missing .env.example"

	if [[ -f "${env_file}" ]]; then
		log ".env already exists; synchronizing missing keys"
		sync_env_from_example "${example}"
		return 0
	fi

	local version secret db_pass admin_pass host
	version="$(read_version)"
	secret="$(random_hex)"
	db_pass="$(random_hex | cut -c1-32)"
	admin_pass="Hfl-0$(random_hex | cut -c1-14)!"
	host="${PUBLIC_HOST}"
	if [[ -z "${host}" ]]; then
		host="$(hostname -I 2>/dev/null | awk '{ for (i = 1; i <= NF; i++) if (!found && $i ~ /^[0-9]+\./) { print $i; found = 1 } }' || true)"
	fi
	[[ -n "${host}" ]] || host="127.0.0.1"

	step "Creating .env from .env.example ..."
	cp "${example}" "${env_file}"
	python3 - "${env_file}" "${version}" "${secret}" "${db_pass}" "${admin_pass}" "${host}" <<'PY'
import ipaddress
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
version, secret, db_pass, admin_pass, host = sys.argv[2:7]
text = path.read_text(encoding="utf-8")

def sub_key(name, value):
    global text
    pattern = rf"^({re.escape(name)}=).*$"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, lambda m, v=value: f"{m.group(1)}{v}", text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\n{name}={value}\n"

sub_key("AGENT_VERSION", version)
sub_key("APP_VERSION", version)
sub_key("SECRET_KEY", secret)
sub_key("POSTGRES_PASSWORD", db_pass)
sub_key("SEED_ADMIN_PASSWORD", admin_pass)
sub_key("DJANGO_DEBUG", "false")
sub_key("SENTRY_ENVIRONMENT", "production")
sub_key("HFL_EMAIL_SIGNUP_ENABLED", "false")
sub_key("HFL_GOOGLE_OAUTH_ENABLED", "false")
sub_key("HFL_PLATFORM_OPS_ENABLED", "true")
tenant_port = "11443"
frontend_url = f"https://{host}:{tenant_port}"
sub_key("FRONTEND_URL", frontend_url)
sub_key("DJANGO_ALLOWED_HOSTS", f"localhost,127.0.0.1,{host}")
sub_key(
    "CSRF_TRUSTED_ORIGINS",
    f"https://localhost:{tenant_port},https://127.0.0.1:{tenant_port},{frontend_url}",
)
sub_key(
    "CORS_ALLOWED_ORIGINS",
    f"https://localhost:{tenant_port},https://127.0.0.1:{tenant_port},{frontend_url}",
)
try:
    ipaddress.ip_address(host)
except ValueError:
    sub_key("HFL_TLS_SAN_DNS", host)
else:
    sub_key("HFL_TLS_SAN_IP", host)
path.write_text(text, encoding="utf-8")
PY
	log ".env created (generated secrets, host configuration, DJANGO_DEBUG=false)"
}

preflight_package_layout() {
	step "Checking release package layout..."
	[[ -f "${ROOT}/MANIFEST.json" ]] || die "missing MANIFEST.json"
	[[ -f "${ROOT}/docker-compose.yml" ]] || die "missing docker-compose.yml"
	[[ -f "${ROOT}/images/00-hyperfilelens.tar.gz" ]] || die "missing HFL image archive"
	[[ -f "${ROOT}/images/01-postgres-17.tar.gz" ]] || die "missing PostgreSQL image archive"
	[[ -f "${ROOT}/images/02-redis-alpine.tar.gz" ]] || die "missing Redis image archive"
	log "Release package check passed"
}

stack_containers_present() {
	require_docker
	local count
	count="$(compose_in_root ps -q 2>/dev/null | wc -l | tr -d ' ')"
	[[ "${count}" -gt 0 ]]
}

wait_for_hfl_health() {
	local timeout_seconds="${HFL_HEALTH_TIMEOUT_SECONDS:-600}"
	[[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ ]] || die "HFL_HEALTH_TIMEOUT_SECONDS must be positive"
	local tenant_port
	tenant_port="$(read_env_value HFL_TENANT_PORT)"
	[[ -n "${tenant_port}" ]] || tenant_port=11443
	local deadline=$((SECONDS + timeout_seconds))
	local -a services=(postgres redis worker scheduler api nginx)
	step "Waiting for HyperFileLens health checks (timeout ${timeout_seconds}s) ..."
	while ((SECONDS < deadline)); do
		local ready=1 service cid status
		for service in "${services[@]}"; do
			cid="$(compose_in_root ps -q "${service}" 2>/dev/null | head -1)"
			if [[ -z "${cid}" ]]; then
				ready=0
				break
			fi
			status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${cid}" 2>/dev/null || true)"
			if [[ "${status}" != "healthy" && "${status}" != "running" ]]; then
				ready=0
				break
			fi
		done
		if [[ "${ready}" -eq 1 ]] \
			&& curl -kfsS "https://127.0.0.1:${tenant_port}/health/ready" >/dev/null 2>&1; then
			ok "HyperFileLens health gate passed"
			return 0
		fi
		sleep 5
	done
	warn "HyperFileLens health gate timed out"
	compose_in_root ps || true
	return 1
}

wait_for_sourcelens_health() {
	[[ "$(configured_sourcelens_mode)" == "bundled" ]] || return 0
	sourcelens_installed || return 0
	local nginx_cid
	nginx_cid="$(sourcelens_compose ps -q nginx 2>/dev/null | head -1)"
	if [[ -z "${nginx_cid}" ]]; then
		log "Bundled SourceLens is not running; skipping its health gate"
		return 0
	fi
	local timeout_seconds="${SOURCELENS_HEALTH_TIMEOUT_SECONDS:-600}"
	local port
	port="$(read_env_value SOURCELENS_CONSOLE_PORT)"
	[[ -n "${port}" ]] || port=11445
	step "Waiting for bundled SourceLens HTTPS health (timeout ${timeout_seconds}s) ..."
	local deadline=$((SECONDS + timeout_seconds))
	while ((SECONDS < deadline)); do
		if curl -kfsS "https://127.0.0.1:${port}/" >/dev/null 2>&1; then
			ok "Bundled SourceLens health gate passed"
			return 0
		fi
		sleep 5
	done
	warn "Bundled SourceLens health gate timed out"
	sourcelens_compose ps || true
	return 1
}

load_images_from_manifest() {
	local skip_sourcelens=${1:-0}
	local package_root=${2:-${ROOT}}
	local sourcelens_mode
	sourcelens_mode="$(configured_sourcelens_mode)"
	if [[ "${sourcelens_mode}" == "external" ]]; then
		skip_sourcelens=1
	fi
	python3 - "${package_root}" "${skip_sourcelens}" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
skip_sourcelens = sys.argv[2] == "1"
with (root / "MANIFEST.json").open(encoding="utf-8") as fh:
    manifest = json.load(fh)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_present(ref: str) -> bool:
    tag = ref.split("@", 1)[0]
    return subprocess.run(
        ["docker", "image", "inspect", tag],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0

for entry in manifest.get("images", []):
    if skip_sourcelens and str(entry.get("role", "")).startswith("sourcelens"):
        continue
    rel = entry.get("file", "")
    path = root / rel
    refs = entry.get("refs", [])
    if not path.is_file():
        print(f"[install.sh] ERROR: missing image archive {path}", file=sys.stderr)
        sys.exit(1)
    expected = str(entry.get("sha256", ""))
    if expected and sha256_file(path) != expected:
        print(f"[install.sh] ERROR: sha256 mismatch for {rel}", file=sys.stderr)
        sys.exit(1)
    if refs and all(image_present(ref) for ref in refs):
        print(f"[install.sh] skipping {rel} (image already loaded)")
        continue
    print(f"[install.sh] loading image {rel} ...")
    subprocess.run(["docker", "load", "-i", str(path)], check=True)
PY
}

sync_env_from_example() {
	local example=$1
	local env_file="${ROOT}/.env"
	local sync_script="$(dirname "${example}")/sync-env.py"
	[[ -f "${example}" ]] || return 0
	[[ -f "${sync_script}" ]] || die "missing environment sync script: ${sync_script}"
	step "Merging missing keys from .env.example into .env ..."
	python3 "${sync_script}" --env-file "${env_file}" --example "${example}"
}

update_env_versions() {
	local version=$1
	python3 - "${ROOT}" "${version}" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
version = sys.argv[2]
env = root / ".env"
if not env.exists():
    raise SystemExit(0)
text = env.read_text(encoding="utf-8")
for key in ("AGENT_VERSION", "APP_VERSION"):
    pattern = rf"^({re.escape(key)}=).*$"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, lambda m, v=version: f"{m.group(1)}{v}", text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\n{key}={version}\n"
env.write_text(text, encoding="utf-8")
PY
}

backup_env_and_data() {
	local stamp archive rc
	stamp="$(date +%Y%m%d-%H%M%S)"
	mkdir -p "${ROOT}/backup"
	archive="${ROOT}/backup/hyperfilelens-backup-${stamp}.tar.gz"
	step "Backing up .env and data/ -> ${archive} ..."
	local -a items=()
	[[ -f "${ROOT}/.env" ]] && items+=(".env")
	[[ -d "${ROOT}/data" ]] && items+=("data")
	if ((${#items[@]} == 0)); then
		warn "nothing to back up (.env and data/ missing); skipping"
		return 0
	fi
	set +e
	tar -czf "${archive}" -C "${ROOT}" "${items[@]}"
	rc=$?
	set -e
	if [[ "${rc}" -gt 1 ]]; then
		die "backup failed (tar exit ${rc})"
	fi
	if [[ "${rc}" -eq 1 ]]; then
		warn "backup completed with warnings (live files such as nginx logs changed during archive)"
	fi
	log "Backup complete: ${archive}"
}

backup_postgresql_dump() {
	[[ -f "${ROOT}/.env" ]] || return 0
	local cid
	cid="$(compose_in_root ps -q postgres 2>/dev/null | head -1)"
	[[ -n "${cid}" ]] || { warn "PostgreSQL is not running; skipping logical database dump"; return 0; }
	local stamp dump globals
	stamp="$(date +%Y%m%d-%H%M%S)"
	mkdir -p "${ROOT}/backup"
	dump="${ROOT}/backup/hyperfilelens-postgresql-${stamp}.dump"
	globals="${ROOT}/backup/hyperfilelens-postgresql-globals-${stamp}.sql"
	step "Creating consistent PostgreSQL logical backup ..."
	compose_in_root exec -T postgres sh -ec \
		'exec pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-hyperfilelens}" -Fc' \
		>"${dump}.part"
	compose_in_root exec -T postgres sh -ec \
		'exec pg_dumpall -U "${POSTGRES_USER:-postgres}" --globals-only' \
		>"${globals}.part"
	mv "${dump}.part" "${dump}"
	mv "${globals}.part" "${globals}"
	chmod 600 "${dump}" "${globals}"
	ok "PostgreSQL logical backup created under ${ROOT}/backup"

	if sourcelens_installed; then
		local sl_cid sl_dump sl_globals
		sl_cid="$(sourcelens_compose ps -q postgresql 2>/dev/null | head -1)"
		if [[ -n "${sl_cid}" ]]; then
			sl_dump="${ROOT}/backup/sourcelens-postgresql-${stamp}.dump"
			sl_globals="${ROOT}/backup/sourcelens-postgresql-globals-${stamp}.sql"
			step "Creating consistent bundled SourceLens PostgreSQL backup ..."
			sourcelens_compose exec -T postgresql sh -ec \
				'exec pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-backend}" -Fc' \
				>"${sl_dump}.part"
			sourcelens_compose exec -T postgresql sh -ec \
				'exec pg_dumpall -U "${POSTGRES_USER:-postgres}" --globals-only' \
				>"${sl_globals}.part"
			mv "${sl_dump}.part" "${sl_dump}"
			mv "${sl_globals}.part" "${sl_globals}"
			chmod 600 "${sl_dump}" "${sl_globals}"
			ok "Bundled SourceLens PostgreSQL logical backup created"
		fi
	fi
}

apply_upgrade_files() {
	local from_root=$1
	local remove_sourcelens=${2:-0}
	step "Overwriting application files and release payload ..."
	mkdir -p "${ROOT}/deploy/nginx" "${ROOT}/images" "${ROOT}/host" "${ROOT}/payload"
	rsync -a --delete "${from_root}/payload/" "${ROOT}/payload/"
	rsync -a --delete "${from_root}/images/" "${ROOT}/images/"
	if [[ -d "${ROOT}/src" ]]; then
		safe_assert_path_under_dir "${ROOT}/src" "${ROOT}" "legacy runtime source path"
		safe_rm_dir "${ROOT}/src"
		log "Removed legacy host source tree; application code now ships only in images"
	fi
	if [[ "${remove_sourcelens}" -eq 1 && -d "${ROOT}/sourcelens" ]]; then
		safe_assert_path_under_dir "${ROOT}/sourcelens" "${ROOT}" "SourceLens runtime path"
		safe_rm_dir "${ROOT}/sourcelens"
	elif [[ -d "${from_root}/sourcelens" ]]; then
		rsync -a --delete "${from_root}/sourcelens/" "${ROOT}/sourcelens/"
	fi
	cp "${from_root}/docker-compose.yml" "${ROOT}/docker-compose.yml"
	mkdir -p "${ROOT}/deploy/nginx/snippets"
	if [[ -d "${from_root}/deploy/nginx/snippets" ]]; then
		rsync -a "${from_root}/deploy/nginx/snippets/" "${ROOT}/deploy/nginx/snippets/"
	fi
	cp "${from_root}/deploy/nginx/default.conf" "${ROOT}/deploy/nginx/default.conf"
	if [[ -f "${from_root}/deploy/logrotate/hyperfilelens.conf" ]]; then
		mkdir -p "${ROOT}/deploy/logrotate"
		cp "${from_root}/deploy/logrotate/hyperfilelens.conf" "${ROOT}/deploy/logrotate/hyperfilelens.conf"
	fi
	read_version_from_dir "${from_root}" > "${ROOT}/VERSION"
	cp "${from_root}/MANIFEST.json" "${ROOT}/MANIFEST.json"
	[[ -f "${from_root}/.env.example" ]] && cp "${from_root}/.env.example" "${ROOT}/.env.example"
	[[ -f "${from_root}/sync-env.py" ]] && cp "${from_root}/sync-env.py" "${ROOT}/sync-env.py" && chmod +x "${ROOT}/sync-env.py"
	[[ -f "${from_root}/LICENSE" ]] && cp "${from_root}/LICENSE" "${ROOT}/LICENSE"
	[[ -f "${from_root}/install.sh" ]] && cp "${from_root}/install.sh" "${ROOT}/install.sh" && chmod +x "${ROOT}/install.sh"
	if [[ -d "${from_root}/host" ]]; then
		rsync -a "${from_root}/host/" "${ROOT}/host/"
	fi
	log "File overwrite complete"
}

prepare_upgrade_source() {
	local from=$1
	if [[ -d "${from}" ]]; then
		local resolved
		resolved="$(cd "${from}" && pwd)"
		safe_assert_package_root "${resolved}"
		printf '%s' "${resolved}"
		return 0
	fi
	if [[ -f "${from}" && "${from}" == *.tar.gz ]]; then
		safe_assert_upgrade_package_file "${from}"
		safe_rm_dir "${UPGRADE_TMP}"
		mkdir -p "${UPGRADE_TMP}"
		step "Extracting ${from} -> ${UPGRADE_TMP} ..."
		tar -xzf "${from}" -C "${UPGRADE_TMP}"
		local inner
		inner="$(find "${UPGRADE_TMP}" -mindepth 1 -maxdepth 1 -type d | head -1)"
		[[ -n "${inner}" && -f "${inner}/MANIFEST.json" ]] || die "invalid tar.gz package layout"
		printf '%s' "${inner}"
		return 0
	fi
	die "upgrade --from must be a directory or hyperfilelens-*.tar.gz: ${from}"
}

cleanup_upgrade_tmp() {
	if [[ -d "${UPGRADE_TMP}" ]]; then
		step "Cleaning up ${UPGRADE_TMP} ..."
		safe_rm_dir "${UPGRADE_TMP}"
	fi
}

remove_manifest_images() {
	[[ -f "${ROOT}/MANIFEST.json" ]] || return 0
	step "Removing application Docker images..."
	python3 - "${ROOT}" <<'PY'
import json, subprocess, sys
with open(f"{sys.argv[1]}/MANIFEST.json", encoding="utf-8") as fh:
    manifest = json.load(fh)
seen = set()
for entry in manifest.get("images", []):
    if str(entry.get("role", "")).startswith("sourcelens"):
        continue
    for ref in entry.get("refs", []):
        tag = ref.split("@", 1)[0]
        if tag in seen:
            continue
        seen.add(tag)
        print(f"[install.sh] removing image {tag}")
        subprocess.run(["docker", "image", "rm", "-f", tag], check=False)
PY
}

version_lt() {
	python3 - "$1" "$2" <<'PY'
import sys
def parse(v):
    return tuple(int(x) for x in v.split("."))
try:
    sys.exit(0 if parse(sys.argv[1]) < parse(sys.argv[2]) else 1)
except Exception:
    sys.exit(1)
PY
}

confirm_same_version_upgrade() {
	local version=$1
	if [[ "${UPGRADE_YES}" -eq 1 ]]; then
		warn "new package version matches current (${version}); continuing upgrade (--yes)"
		return 0
	fi
	if [[ -t 0 ]]; then
		local ans
		printf 'Package version is already %s. Continue upgrade? [y/N] ' "${version}" >&2
		read -r ans
		case "${ans}" in
		y | Y | yes | YES) return 0 ;;
		esac
		die "upgrade aborted (same version)"
	fi
	die "same version upgrade requires a TTY or --yes"
}

read_env_value() {
	local key=$1
	local env_file="${ROOT}/.env"
	[[ -f "${env_file}" ]] || return 0
	grep -E "^${key}=" "${env_file}" 2>/dev/null \
		| head -1 | cut -d= -f2- | tr -d ' "' || true
}

resolve_console_host() {
	local san_dns san_ip host
	san_dns="$(read_env_value HFL_TLS_SAN_DNS)"
	san_ip="$(read_env_value HFL_TLS_SAN_IP)"
	if [[ -n "${san_dns}" && "${san_dns}" != "localhost" ]]; then
		printf '%s' "${san_dns}"
		return 0
	fi
	if [[ -n "${san_ip}" ]]; then
		printf '%s' "${san_ip}"
		return 0
	fi
	host="$(hostname -I 2>/dev/null | awk '{print $1}')"
	if [[ -n "${host}" ]]; then
		printf '%s' "${host}"
		return 0
	fi
	printf '%s' "<host>"
}

print_console_access_summary() {
	local env_file="${ROOT}/.env"
	[[ -f "${env_file}" ]] || return 0

	local host seed seed_email seed_pass seed_org sourcelens_mode sourcelens_console_port
	local tenant_bind tenant_port admin_bind admin_port sourcelens_console_bind
	host="$(resolve_console_host)"
	seed="$(read_env_value SEED_INITIAL_DATA)"
	seed_email="$(read_env_value SEED_ADMIN_EMAIL)"
	seed_pass="$(read_env_value SEED_ADMIN_PASSWORD)"
	seed_org="$(read_env_value SEED_ORG_NAME)"
	sourcelens_mode="$(read_env_value SOURCELENS_MODE | tr 'A-Z' 'a-z')"
	[[ -n "${sourcelens_mode}" ]] || sourcelens_mode="bundled"
	tenant_bind="$(read_env_value HFL_TENANT_BIND_ADDRESS)"
	[[ -n "${tenant_bind}" ]] || tenant_bind="0.0.0.0"
	tenant_port="$(read_env_value HFL_TENANT_PORT)"
	[[ -n "${tenant_port}" ]] || tenant_port="11443"
	admin_bind="$(read_env_value HFL_ADMIN_BIND_ADDRESS)"
	[[ -n "${admin_bind}" ]] || admin_bind="0.0.0.0"
	admin_port="$(read_env_value HFL_ADMIN_PORT)"
	[[ -n "${admin_port}" ]] || admin_port="11444"
	sourcelens_console_bind="$(read_env_value SOURCELENS_CONSOLE_BIND_ADDRESS)"
	[[ -n "${sourcelens_console_bind}" ]] || sourcelens_console_bind="0.0.0.0"
	sourcelens_console_port="$(read_env_value SOURCELENS_CONSOLE_PORT)"
	[[ -n "${sourcelens_console_port}" ]] || sourcelens_console_port="11445"

	log "Tenant URL: https://${host}:${tenant_port}/ (bind ${tenant_bind})"
	log "Platform Operations URL: https://${host}:${admin_port}/ (bind ${admin_bind})"
	log "Django Admin URL: https://${host}:${admin_port}/admin/"
	if [[ "${sourcelens_mode}" == "bundled" ]] && { package_has_sourcelens || sourcelens_installed; }; then
		log "SourceLens Console: https://${host}:${sourcelens_console_port}/ (bind ${sourcelens_console_bind})"
		log "SourceLens Gateway API: https://${host}:${tenant_port}/sourcelens/api/"
		log "SourceLens network: ${HFL_BRIDGE_NETWORK} (private)"
	elif [[ "${sourcelens_mode}" == "external" ]]; then
		log "SourceLens mode: external (not managed by HyperFileLens)"
		log "SourceLens base URL: $(read_env_value LENS_BASE_URL)"
	fi
	log "Configuration file: ${env_file}."

	if [[ "${seed}" == "1" ]]; then
		[[ -n "${seed_email}" ]] || seed_email="admin@hyperfilelens.com"
		[[ -n "${seed_pass}" ]] || seed_pass="Admin@123"
		[[ -n "${seed_org}" ]] || seed_org="HyperFileLens"
		local show_credentials=0
		case "${SHOW_GENERATED_CREDENTIALS}" in
		1 | true | yes | on) show_credentials=1 ;;
		0 | false | no | off) show_credentials=0 ;;
		auto) [[ -t 2 ]] && show_credentials=1 || true ;;
		*) die "invalid HFL_SHOW_GENERATED_CREDENTIALS=${SHOW_GENERATED_CREDENTIALS}" ;;
		esac
		if [[ "${show_credentials}" -eq 1 ]]; then
			log "Default admin email: ${seed_email} (environment variable SEED_ADMIN_EMAIL)."
			log "Default admin password: ${seed_pass} (environment variable SEED_ADMIN_PASSWORD)."
		else
			log "Initial admin credentials are stored in ${env_file}; values are hidden in non-interactive logs."
		fi
		log "Default organization: ${seed_org} (environment variable SEED_ORG_NAME)."
		log "Initial seeding is enabled (SEED_INITIAL_DATA=1); the worker service creates this account on first startup."
		log "Change the default password after your first login."
	else
		warn "Initial seeding is disabled (SEED_INITIAL_DATA=${seed:-0}); no default admin account will be created automatically."
		log "To create a seeded admin, set SEED_INITIAL_DATA=1, SEED_ADMIN_EMAIL, and SEED_ADMIN_PASSWORD in ${env_file}, then restart the worker service."
	fi
}

package_has_sourcelens() {
	[[ -f "${ROOT}/sourcelens/install.sh" && -f "${ROOT}/sourcelens/docker-compose.yml" ]]
}

package_has_sourcelens_dir() {
	local dir=$1
	[[ -f "${dir}/sourcelens/install.sh" && -f "${dir}/sourcelens/docker-compose.yml" ]]
}

sourcelens_installed() {
	[[ -f "${SOURCELENS_INSTALL_DIR}/docker-compose.yml" ]]
}

sourcelens_compose() {
	if ! sourcelens_installed; then
		return 0
	fi
	require_docker
	(
		cd "${SOURCELENS_INSTALL_DIR}"
		docker compose "$@"
	)
}

stop_bundled_sourcelens() {
	if ! sourcelens_installed; then
		return 0
	fi
	step "Stopping SourceLens stack ..."
	sourcelens_compose down || true
}

remove_sourcelens_images() {
	local manifest="${ROOT}/MANIFEST.json"
	[[ -f "${manifest}" ]] || return 0
	step "Removing SourceLens Docker images ..."
	python3 - "${manifest}" <<'PY'
import json
import subprocess
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    manifest = json.load(fh)
seen = set()
for entry in manifest.get("images", []):
    role = entry.get("role", "")
    if not role.startswith("sourcelens"):
        continue
    for ref in entry.get("refs", []):
        tag = ref.split("@", 1)[0]
        if tag in seen:
            continue
        seen.add(tag)
        print(f"[install.sh] removing SourceLens image {tag}")
        subprocess.run(["docker", "image", "rm", "-f", tag], check=False)
PY
}

purge_sourcelens_data_dir() {
	local data_dir="${ROOT}/data/sourcelens"
	[[ -d "${data_dir}" ]] || return 0
	safe_assert_path_under_dir "${data_dir}" "${ROOT}/data" "SourceLens data path"
	step "Removing SourceLens data/ ..."
	safe_rm_dir "${data_dir}"
	log "Removed SourceLens data/"
}

uninstall_bundled_sourcelens() {
	local purge_data=${1:-0}
	if ! sourcelens_installed; then
		log "SourceLens not installed at ${SOURCELENS_INSTALL_DIR}; skipping"
		return 0
	fi
	step "Uninstalling SourceLens ..."
	sourcelens_compose down || true
	remove_sourcelens_images
	if [[ "${purge_data}" -eq 1 ]]; then
		purge_sourcelens_data_dir
	fi
	log "SourceLens uninstall complete (install dir kept: ${SOURCELENS_INSTALL_DIR})"
}

tree_sha256() {
	local dir=$1
	(
		cd "${dir}"
		find . -type f ! -path './__pycache__/*' ! -name '*.pyc' -print0 \
			| sort -z \
			| xargs -0 sha256sum \
			| sha256sum \
			| awk '{print $1}'
	)
}

validate_publish_artifacts() {
	local src_root=$1
	local releases="${src_root}/payload/media/agent-releases"
	local gb="${src_root}/payload/media/gateway-bootstrap"
	local enroll="${src_root}/payload/media/enroll-bootstrap"
	local expected_payload_sha actual_payload_sha
	step "Checking publish artifacts in release package ..."
	[[ -d "${releases}" && -n "$(ls -A "${releases}" 2>/dev/null)" ]] \
		|| die "release package missing agent-releases artifacts"
	[[ -d "${enroll}" && -n "$(ls -A "${enroll}" 2>/dev/null)" ]] \
		|| die "release package missing enroll-bootstrap artifacts"
	expected_payload_sha="$(python3 - "${src_root}/MANIFEST.json" <<'PY'
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print((manifest.get("artifacts") or {}).get("payload_tree_sha256", ""))
PY
)"
	if [[ -n "${expected_payload_sha}" ]]; then
		actual_payload_sha="$(tree_sha256 "${src_root}/payload")"
		[[ "${actual_payload_sha}" == "${expected_payload_sha}" ]] \
			|| die "release package payload sha256 mismatch"
	fi
	if package_has_sourcelens_dir "${src_root}"; then
		local -a required=(
			gateway-bootstrap-linux.sh
			gateway-install-lensnode-sidecar.sh
			gateway-lifecycle.sh
			gateway-install-docker-ubuntu-amd64.sh
			docker-debs-ubuntu2004-amd64.tar.gz
			docker-debs-ubuntu2404-amd64.tar.gz
			lensnode-image-linux-amd64.tar.gz
		)
		local name
		for name in "${required[@]}"; do
			[[ -f "${gb}/${name}" ]] || die "release package missing gateway-bootstrap/${name}"
		done
	fi
	log "Publish artifact check passed"
}

preflight_sourcelens_bundle() {
	local src_root=$1
	step "Checking SourceLens bundle in upgrade package ..."
	[[ -f "${src_root}/sourcelens/BUILD_INFO.json" ]] || die "missing sourcelens/BUILD_INFO.json"
	local -a images=(
		images/10-sourcelens-app.tar.gz
		images/11-sourcelens-lensnode.tar.gz
		images/12-nginx-stable-alpine.tar.gz
	)
	local rel
	for rel in "${images[@]}"; do
		[[ -f "${src_root}/${rel}" ]] || die "missing SourceLens image archive ${rel}"
	done
	log "SourceLens bundle check passed"
}

should_upgrade_sourcelens() {
	local mode=$1 src_root=$2
	case "${mode}" in
	0) return 1 ;;
	1)
		if package_has_sourcelens_dir "${src_root}"; then
			return 0
		fi
		warn "SourceLens upgrade requested but upgrade package has no sourcelens/; skipping"
		return 1
		;;
	esac
	[[ "$(configured_sourcelens_mode)" == "bundled" ]] \
		&& package_has_sourcelens_dir "${src_root}" \
		&& sourcelens_bundle_changed "${src_root}"
}

sourcelens_bundle_fingerprint() {
	local root=$1
	python3 - "${root}" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
paths = [
    "docker-compose.yml",
    ".env.example",
    "install.sh",
    "patch-env-runtime.py",
]
deploy = root / "deploy"
if deploy.is_dir():
    paths.extend(
        path.relative_to(root).as_posix()
        for path in sorted(deploy.rglob("*"))
        if path.is_file() and "certs" not in path.parts
    )
digest = hashlib.sha256()

# Registry transit references and rebuilt image IDs can change for every HFL
# tag even while the bundled SourceLens release remains pinned. Only semantic
# SourceLens identity belongs in the bundle fingerprint; runtime files below
# capture HFL-owned integration changes.
build_info_path = root / "BUILD_INFO.json"
if build_info_path.is_file():
    info = json.loads(build_info_path.read_text(encoding="utf-8"))
    identity = {
        "git_url": info.get("git_url", ""),
        "git_ref": info.get("git_ref", ""),
        "git_commit": info.get("git_commit", ""),
        "version": info.get("version", ""),
        "patch_sha256": info.get("patch_sha256", ""),
        "embed_local_lensnode": info.get("embed_local_lensnode", False),
    }
    digest.update(b"BUILD_INFO.identity\0")
    digest.update(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    )
else:
    digest.update(b"missing:BUILD_INFO.json\0")

for rel in sorted(set(paths)):
    path = root / rel
    if not path.is_file():
        digest.update(f"missing:{rel}\0".encode())
        continue
    digest.update(rel.encode() + b"\0")
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
print(digest.hexdigest())
PY
}

sourcelens_bundle_changed() {
	local src_root=$1
	if ! sourcelens_installed || [[ ! -f "${ROOT}/sourcelens/BUILD_INFO.json" ]]; then
		return 0
	fi
	local current target
	current="$(sourcelens_bundle_fingerprint "${ROOT}/sourcelens")"
	target="$(sourcelens_bundle_fingerprint "${src_root}/sourcelens")"
	if [[ "${current}" == "${target}" ]]; then
		log "Bundled SourceLens is unchanged (${current:0:12}); keeping 11445 online"
		return 1
	fi
	log "Bundled SourceLens changed (${current:0:12} -> ${target:0:12})"
	return 0
}

should_remove_sourcelens() {
	local flag=$1
	[[ "${flag}" -eq 1 ]] || return 1
	sourcelens_installed
}

configure_lens_bridge_env() {
	local host tenant_port
	host="$(resolve_console_host)"
	tenant_port="$(read_env_value HFL_TENANT_PORT)"
	[[ -n "${tenant_port}" ]] || tenant_port="11443"
	python3 - "${ROOT}/.env" "${host}" "${tenant_port}" <<'PY'
import pathlib
import re
import sys

env_path = pathlib.Path(sys.argv[1])
host = sys.argv[2]
tenant_port = sys.argv[3]
if not env_path.exists():
    raise SystemExit(0)
text = env_path.read_text(encoding="utf-8")

def read_key(name: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(name)}=(.*)$", text, flags=re.M)
    if not match:
        return default
    return match.group(1).strip().strip('"').strip("'")

frontend = read_key("FRONTEND_URL", "").rstrip("/")
if not frontend:
    frontend = f"https://{host}:{tenant_port}"
no_proxy = [item.strip() for item in read_key("NO_PROXY").split(",") if item.strip()]
if "sourcelens-nginx" not in no_proxy:
    no_proxy.append("sourcelens-nginx")

updates = {
    "LENS_BASE_URL": "http://sourcelens-nginx",
    "LENS_GATEWAY_BASE_URL": f"{frontend}/sourcelens",
    "NO_PROXY": ",".join(no_proxy),
}

def set_key(name: str, value: str) -> None:
    global text
    pattern = rf"^{re.escape(name)}=.*$"
    replacement = f"{name}={value}"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, replacement, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\n{replacement}\n"

for key, value in updates.items():
    set_key(key, value)
env_path.write_text(text, encoding="utf-8")
print(f"[install.sh] configured {', '.join(updates.keys())} for bundled SourceLens")
PY
}

install_bundled_sourcelens() {
	local script="${ROOT}/sourcelens/install.sh"
	local console_bind console_port
	[[ -f "${script}" ]] || return 0
	console_bind="$(read_env_value SOURCELENS_CONSOLE_BIND_ADDRESS)"
	[[ -n "${console_bind}" ]] || console_bind="0.0.0.0"
	console_port="$(read_env_value SOURCELENS_CONSOLE_PORT)"
	[[ -n "${console_port}" ]] || console_port="11445"
	stop_bundled_sourcelens
	step "Installing bundled SourceLens ..."
	SOURCELENS_INSTALL_DIR="${ROOT}/sourcelens" \
		SOURCELENS_DATA_DIR="${ROOT}/data/sourcelens" \
		SOURCELENS_CONFIG_DIR="${ROOT}/data/sourcelens/config" \
		SOURCELENS_TLS_CERT_DIR="${ROOT}/deploy/nginx/certs" \
		SOURCELENS_CONSOLE_BIND_ADDRESS="${console_bind}" \
		SOURCELENS_CONSOLE_PORT="${console_port}" \
		SOURCELENS_NGINX_HTTPS_PORT="${console_port}" \
		bash "${script}" install --skip-image-load
}

should_install_sourcelens() {
	local mode=$1
	case "${mode}" in
	0) return 1 ;;
	1) return 0 ;;
	esac
	[[ "$(configured_sourcelens_mode)" == "bundled" ]] && package_has_sourcelens
}

configured_sourcelens_mode() {
	local mode
	mode="$(read_env_value SOURCELENS_MODE | tr 'A-Z' 'a-z')"
	[[ -n "${mode}" ]] || mode="bundled"
	case "${mode}" in
	bundled | external) printf '%s' "${mode}" ;;
	*) die "invalid SOURCELENS_MODE=${mode} (use bundled or external)" ;;
	esac
}

# --- Commands ---

cmd_install() {
	local sourcelens_mode=-1
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--with-sourcelens) sourcelens_mode=1 ;;
		--hfl-only) sourcelens_mode=0 ;;
		*) die "unknown install option: $1" 2 ;;
		esac
		shift
	done

	init_install_root
	local version
	version="$(read_version)"
	log "======== HyperFileLens install ${version} ========"
	log "Install dir: ${ROOT}"

	preflight_package_layout
	validate_publish_artifacts "${ROOT}"
	if package_has_sourcelens; then
		preflight_sourcelens_bundle "${ROOT}"
	fi

	if [[ -f "${ROOT}/.env" ]] && stack_containers_present; then
		log "app containers already running under ${ROOT}; skipping duplicate install"
		log "To upgrade run: sudo ${ROOT}/install.sh upgrade --from <package.tar.gz>"
		print_console_access_summary
		return 0
	fi

	step "[1/6] Checking host capacity, ports, and Docker ..."
	preflight_install_capacity
	ensure_host_docker "${ROOT}"

	step "[2/6] Preparing config and directories ..."
	require_docker
	ensure_bridge_network
	ensure_env_file
	ensure_tls_certs
	ensure_data_dirs
	sync_runtime_media

	step "[3/6] Loading container images ..."
	load_images_from_manifest "$([[ "${sourcelens_mode}" -eq 0 ]] && echo 1 || echo 0)"

	step "[4/6] Post-install checks ..."
	log "Version: $(read_version)"
	log "Docker: $(docker_engine_version) / compose $(docker_compose_version)"

	if should_install_sourcelens "${sourcelens_mode}"; then
		install_bundled_sourcelens
	fi

	if [[ "$(configured_sourcelens_mode)" == "bundled" ]] && sourcelens_installed; then
		configure_lens_bridge_env
	fi

	step "[5/6] Starting services ..."
	log "Log rotation: built into nginx container (hourly; daily or 500M; keep 30)"
	compose_in_root up -d --no-build --remove-orphans
	wait_for_hfl_health || die "HyperFileLens failed its post-install health gate"
	wait_for_sourcelens_health || die "bundled SourceLens failed its post-install health gate"

	step "[6/6] Done"
	log "Install and startup complete"
	compose_in_root ps
	print_console_access_summary
}

cmd_start() {
	init_install_root
	require_docker
	[[ -f "${ROOT}/.env" ]] || die "missing .env; run install first"
	ensure_bridge_network
	ensure_data_dirs
	sync_runtime_media
	if [[ "$(configured_sourcelens_mode)" == "bundled" ]] && sourcelens_installed; then
		step "Starting bundled SourceLens ..."
		sourcelens_compose up -d --no-build --pull never --remove-orphans
	fi
	step "Starting services (docker compose up -d --no-build) ..."
	compose_in_root up -d --no-build --remove-orphans
	wait_for_hfl_health || die "HyperFileLens failed its startup health gate"
	wait_for_sourcelens_health || die "bundled SourceLens failed its startup health gate"
	log "Services started"
	compose_in_root ps
}

cmd_stop() {
	init_install_root
	require_docker
	step "Stopping services (docker compose down) ..."
	compose_in_root down
	if [[ "$(configured_sourcelens_mode)" == "bundled" ]] && sourcelens_installed; then
		stop_bundled_sourcelens
	fi
	log "Services stopped"
}

cmd_restart() {
	cmd_stop
	cmd_start
}

cmd_status() {
	init_install_root
	local version
	version="$(read_version)"
	printf 'Version: %s\n' "${version}"
	printf 'Install dir: %s\n' "${ROOT}"
	if sourcelens_installed; then
		printf 'SourceLens: installed at %s (network %s)\n' \
			"${SOURCELENS_INSTALL_DIR}" "${HFL_BRIDGE_NETWORK}"
	else
		printf 'SourceLens: not installed\n'
	fi
	if [[ -f "${ROOT}/data/media/gateway-bootstrap/lensnode-image-linux-amd64.tar.gz" ]]; then
		printf 'gateway-bootstrap: lensnode image bundle present\n'
	else
		printf 'gateway-bootstrap: lensnode image bundle missing\n'
	fi
	if [[ -d "${ROOT}/data/media/agent-releases" ]]; then
		local versions
		versions="$(find "${ROOT}/data/media/agent-releases" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -V | tr '\n' ' ')"
		printf 'agent-releases: %s\n' "${versions:-none}"
	fi
	if [[ -f "${ROOT}/.env" ]]; then
		require_docker
		compose_in_root ps
		print_console_access_summary
	else
		warn "missing .env; install has not been run"
	fi
}

init_language_pack_root() {
	local script_dir repository_root
	script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	repository_root="$(cd "${script_dir}/../.." 2>/dev/null && pwd || true)"

	if [[ -f "${script_dir}/docker-compose.yml" ]]; then
		ROOT="${script_dir}"
		LANG_PACK_COMPOSE_FILE="docker-compose.yml"
	elif [[ -n "${repository_root}" && -f "${repository_root}/docker-compose.yml" ]]; then
		ROOT="${repository_root}"
		LANG_PACK_COMPOSE_FILE="docker-compose.yml"
	elif [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
		ROOT="${INSTALL_DIR}"
		LANG_PACK_COMPOSE_FILE="docker-compose.yml"
	else
		die "cannot find a HyperFileLens root for language-pack management"
	fi
}

read_language_pack_app_version() {
	python3 - "${ROOT}" <<'PY'
from __future__ import annotations

import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
version_path = root / "VERSION"
manifest_path = root / "MANIFEST.json"
pyproject_path = root / "pyproject.toml"

if version_path.is_file():
    print(version_path.read_text(encoding="utf-8").strip())
elif manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(str(manifest["version"]).strip())
elif pyproject_path.is_file():
    text = pyproject_path.read_text(encoding="utf-8")
    project_match = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    if project_match is None:
        raise SystemExit("pyproject.toml has no [project] table")
    version_match = re.search(
        r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']\s*$',
        project_match.group(1),
    )
    if version_match is None:
        raise SystemExit("pyproject.toml [project] has no static version")
    print(version_match.group(1).strip())
else:
    raise SystemExit("cannot determine the HyperFileLens application version")
PY
}

validate_and_extract_language_pack() {
	local archive=$1 destination=$2 app_version=$3
	python3 - "${archive}" "${destination}" "${app_version}" <<'PY'
from __future__ import annotations

import json
import pathlib
import re
import sys
import tarfile
from typing import Any

archive = pathlib.Path(sys.argv[1]).resolve()
destination = pathlib.Path(sys.argv[2]).resolve()
app_version = sys.argv[3]
pack_id_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
language_code_pattern = re.compile(
    r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$",
    re.IGNORECASE,
)
semver_pattern = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")


def fail(message: str) -> None:
    """Stop validation with a concise package error."""
    raise SystemExit(f"invalid language pack: {message}")


def required_string(manifest: dict[str, Any], field: str) -> str:
    """Read a required, non-empty manifest string."""
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        fail(f"{field!r} must be a non-empty string")
    return value.strip()


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse the supported semantic-version core."""
    match = semver_pattern.fullmatch(value)
    if match is None:
        fail(f"unsupported semantic version {value!r}")
    return tuple(int(part) for part in match.groups())


def check_compatibility(specifier: str, current_version: str) -> None:
    """Check a comma-separated set of simple semantic-version constraints."""
    current = parse_version(current_version)
    operators = {
        ">=": lambda left, right: left >= right,
        "<=": lambda left, right: left <= right,
        ">": lambda left, right: left > right,
        "<": lambda left, right: left < right,
        "==": lambda left, right: left == right,
    }
    clauses = [clause.strip() for clause in specifier.split(",") if clause.strip()]
    if not clauses:
        fail("'compatible_app' must contain at least one version constraint")
    for clause in clauses:
        match = re.fullmatch(r"(>=|<=|==|>|<)\s*(.+)", clause)
        if match is None:
            fail(f"unsupported compatible_app constraint {clause!r}")
        operator, expected_text = match.groups()
        expected = parse_version(expected_text)
        if not operators[operator](current, expected):
            fail(
                f"application {current_version} does not satisfy "
                f"compatible_app {specifier!r}"
            )


def django_locale_name(language_code: str) -> str:
    """Convert a Django language code to its gettext locale directory name."""
    language, separator, territory = language_code.lower().partition("-")
    if not separator:
        return language
    normalized_territory = territory.title() if len(territory) > 2 else territory.upper()
    return f"{language}_{normalized_territory}"


if not archive.is_file():
    fail(f"archive not found: {archive}")
destination.mkdir(parents=True, exist_ok=True)

with tarfile.open(archive, mode="r:*") as package:
    members = package.getmembers()
    if not members:
        fail("archive is empty")
    if len(members) > 10_000:
        fail("archive contains too many entries")
    total_size = 0
    for member in members:
        member_path = pathlib.PurePosixPath(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            fail(f"unsafe archive path: {member.name!r}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            fail(f"unsupported archive entry: {member.name!r}")
        total_size += member.size
    if total_size > 100 * 1024 * 1024:
        fail("archive expands beyond the 100 MiB limit")
    for member in members:
        package.extract(member, destination)

manifest_candidates = sorted(destination.glob("manifest.json"))
manifest_candidates.extend(sorted(destination.glob("*/manifest.json")))
if len(manifest_candidates) != 1:
    fail("archive must contain exactly one manifest.json at its root or first level")

manifest_path = manifest_candidates[0]
pack_root = manifest_path.parent.resolve()
if destination not in pack_root.parents and pack_root != destination:
    fail("manifest escaped the extraction directory")

try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    fail(f"cannot read manifest.json: {exc}")
if not isinstance(manifest, dict):
    fail("manifest.json must contain an object")
if manifest.get("schema") != 1:
    fail("'schema' must be 1")

pack_id = required_string(manifest, "id")
if pack_id_pattern.fullmatch(pack_id) is None:
    fail("'id' must use lowercase letters, digits, and hyphens")
required_string(manifest, "display_name")
parse_version(required_string(manifest, "version"))
compatible_app = required_string(manifest, "compatible_app")
frontend_code = required_string(manifest, "frontend_code")
backend_code = required_string(manifest, "backend_code")
if language_code_pattern.fullmatch(frontend_code) is None:
    fail("'frontend_code' is invalid")
if language_code_pattern.fullmatch(backend_code) is None:
    fail("'backend_code' is invalid")
if frontend_code == "en" or backend_code == "en":
    fail("optional packs cannot replace the built-in English locale")

aliases = manifest.get("aliases", [])
if not isinstance(aliases, list) or not all(
    isinstance(alias, str)
    and alias == alias.lower()
    and language_code_pattern.fullmatch(alias)
    for alias in aliases
):
    fail("'aliases' must be an array of valid language codes")

element_plus_locale = manifest.get("element_plus_locale")
if element_plus_locale is not None and (
    not isinstance(element_plus_locale, str)
    or re.fullmatch(r"[A-Za-z0-9_-]+", element_plus_locale) is None
):
    fail("'element_plus_locale' is invalid")

frontend_messages = pack_root / "frontend" / "messages.json"
backend_messages = (
    pack_root
    / "backend"
    / "locale"
    / django_locale_name(backend_code)
    / "LC_MESSAGES"
    / "django.mo"
)
if not frontend_messages.is_file():
    fail("frontend/messages.json is required")
try:
    message_catalog = json.loads(frontend_messages.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    fail(f"cannot read frontend/messages.json: {exc}")
if not isinstance(message_catalog, dict):
    fail("frontend/messages.json must contain an object")
if not backend_messages.is_file() or backend_messages.stat().st_size == 0:
    fail(f"compiled backend catalog is required: {backend_messages.relative_to(pack_root)}")

allowed_files = {
    pathlib.Path("manifest.json"),
    pathlib.Path("frontend/messages.json"),
    backend_messages.relative_to(pack_root),
}
installed_files = {
    path.relative_to(pack_root) for path in pack_root.rglob("*") if path.is_file()
}
unexpected_files = sorted(installed_files - allowed_files)
if unexpected_files:
    fail(
        "unsupported files in runtime package: "
        + ", ".join(str(path) for path in unexpected_files)
    )

check_compatibility(compatible_app, app_version)
print(pack_id)
print(pack_root)
PY
}

refresh_language_pack_index() {
	local language_root=$1
	python3 - "${language_root}" <<'PY'
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import sys
from typing import Any

root = pathlib.Path(sys.argv[1])
packs: list[dict[str, Any]] = []
for pack_dir in sorted(root.iterdir()):
    if not pack_dir.is_dir() or pack_dir.name.startswith("."):
        continue
    manifest_path = pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = {
        "id": manifest["id"],
        "display_name": manifest["display_name"],
        "version": manifest["version"],
        "frontend_code": manifest["frontend_code"],
        "backend_code": manifest["backend_code"],
    }
    if manifest.get("element_plus_locale"):
        entry["element_plus_locale"] = manifest["element_plus_locale"]
    packs.append(entry)

payload = {"schema": 1, "packs": packs}
with tempfile.NamedTemporaryFile(
    mode="w",
    encoding="utf-8",
    dir=root,
    prefix=".installed-",
    suffix=".json",
    delete=False,
) as index_file:
    json.dump(payload, index_file, ensure_ascii=True, indent=2)
    index_file.write("\n")
    temporary_path = pathlib.Path(index_file.name)
os.replace(temporary_path, root / "installed.json")
PY
}

restart_language_pack_services() {
	if [[ ! -f "${ROOT}/.env" ]] || ! command -v docker >/dev/null 2>&1 \
		|| ! docker info >/dev/null 2>&1; then
		warn "language pack updated; restart HyperFileLens services before using it"
		return 0
	fi
	require_docker
	step "Restarting services to load language-pack changes ..."
	if ! (
		cd "${ROOT}"
		"${COMPOSE[@]}" --env-file "${ROOT}/.env" \
			-f "${ROOT}/${LANG_PACK_COMPOSE_FILE}" \
			restart api worker scheduler nginx
	); then
		warn "language pack updated, but automatic service restart failed"
	fi
}

cmd_language_pack_install() {
	local archive="" temp_dir language_root app_version pack_id pack_source
	local validation_output
	local incoming target backup
	local -a validation_result=()
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--file)
			shift
			archive="${1:-}"
			[[ -n "${archive}" ]] || die "--file requires a package path"
			;;
		*) die "unknown lang-pack install option: $1" 2 ;;
		esac
		shift
	done
	[[ -n "${archive}" ]] || die "lang-pack install requires --file <package.tar.gz>"
	archive="$(realpath "${archive}")"
	[[ -f "${archive}" ]] || die "language-pack archive not found: ${archive}"

	init_language_pack_root
	language_root="${ROOT}/data/lang-packs"
	mkdir -p "${language_root}"
	temp_dir="$(mktemp -d "${language_root}/.extract-XXXXXX")"
	app_version="$(read_language_pack_app_version)"
	if ! validation_output="$(
		validate_and_extract_language_pack "${archive}" "${temp_dir}" "${app_version}"
	)"; then
		safe_rm_dir "${temp_dir}"
		die "language-pack validation failed"
	fi
	mapfile -t validation_result <<< "${validation_output}"
	[[ "${#validation_result[@]}" -eq 2 ]] \
		|| die "language-pack validator returned an unexpected result"
	pack_id="${validation_result[0]}"
	pack_source="${validation_result[1]}"
	incoming="${language_root}/.incoming-${pack_id}-$$"
	target="${language_root}/${pack_id}"
	backup="${language_root}/.backup-${pack_id}-$$"

	safe_rm_dir "${incoming}"
	mkdir -p "${incoming}"
	cp -a "${pack_source}/." "${incoming}/"
	if [[ -e "${target}" ]]; then
		mv "${target}" "${backup}"
	fi
	if ! mv "${incoming}" "${target}"; then
		[[ -e "${backup}" ]] && mv "${backup}" "${target}"
		safe_rm_dir "${temp_dir}"
		die "failed to activate language pack ${pack_id}"
	fi
	safe_rm_dir "${backup}"
	safe_rm_dir "${temp_dir}"
	refresh_language_pack_index "${language_root}"
	log "Installed language pack ${pack_id} for HyperFileLens ${app_version}"
	restart_language_pack_services
}

cmd_language_pack_list() {
	local language_root
	init_language_pack_root
	language_root="${ROOT}/data/lang-packs"
	mkdir -p "${language_root}"
	refresh_language_pack_index "${language_root}"
	python3 - "${language_root}/installed.json" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys

index = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
packs = index.get("packs", [])
if not packs:
    print("No optional language packs installed.")
else:
    for pack in packs:
        print(
            f"{pack['id']}\t{pack['version']}\t{pack['display_name']}\t"
            f"frontend={pack['frontend_code']}\tbackend={pack['backend_code']}"
        )
PY
}

cmd_language_pack_remove() {
	local pack_id=${1:-} language_root target
	[[ $# -eq 1 ]] || die "usage: install.sh lang-pack remove <pack-id>"
	[[ "${pack_id}" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] \
		|| die "invalid language-pack id: ${pack_id}"
	init_language_pack_root
	language_root="${ROOT}/data/lang-packs"
	target="${language_root}/${pack_id}"
	[[ -d "${target}" ]] || die "language pack is not installed: ${pack_id}"
	safe_assert_path_under_dir "${target}" "${language_root}" "language-pack path"
	safe_rm_dir "${target}"
	refresh_language_pack_index "${language_root}"
	log "Removed language pack ${pack_id}"
	restart_language_pack_services
}

cmd_language_pack() {
	local action=${1:-}
	case "${action}" in
	install)
		shift
		cmd_language_pack_install "$@"
		;;
	list)
		shift
		[[ $# -eq 0 ]] || die "usage: install.sh lang-pack list"
		cmd_language_pack_list
		;;
	remove)
		shift
		cmd_language_pack_remove "$@"
		;;
	*) die "usage: install.sh lang-pack {install --file PATH|list|remove PACK_ID}" ;;
	esac
}

cmd_uninstall() {
	local purge_config=0 purge_data=0 purge_all=0
	local with_sourcelens=0 purge_sourcelens_data=0 purge_media=0
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--purge-config) purge_config=1 ;;
		--purge-data) purge_data=1 ;;
		--purge-all) purge_all=1 ;;
		--with-sourcelens) with_sourcelens=1 ;;
		--purge-sourcelens-data) purge_sourcelens_data=1 ;;
		--purge-media) purge_media=1 ;;
		*) die "unknown uninstall option: $1" 2 ;;
		esac
		shift
	done
	[[ "${purge_all}" -eq 1 ]] && purge_config=1 && purge_data=1

	init_install_root
	log "======== HyperFileLens uninstall ========"

	if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
		require_docker
		if [[ -f "${ROOT}/.env" ]]; then
			step "Stopping and removing HyperFileLens containers ..."
			compose_in_root down || true
		fi
		if [[ "${with_sourcelens}" -eq 1 ]]; then
			uninstall_bundled_sourcelens "${purge_sourcelens_data}"
		fi
		remove_manifest_images
	else
		warn "Docker unavailable; skipping container/image cleanup"
	fi

	if [[ "${purge_media}" -eq 1 ]]; then
		step "Removing media publish artifacts ..."
		safe_rm_dir "${ROOT}/data/media/agent-releases"
		safe_rm_dir "${ROOT}/data/media/enroll-bootstrap"
		safe_rm_dir "${ROOT}/data/media/gateway-bootstrap"
		log "Removed agent-releases, enroll-bootstrap, and gateway-bootstrap"
	fi

	if [[ "${purge_data}" -eq 1 ]]; then
		step "Removing data/ ..."
		safe_assert_removable_data_dir "${ROOT}/data" "${ROOT}"
		safe_rm_dir "${ROOT}/data"
		log "Removed data/"
	fi

	if [[ "${purge_config}" -eq 1 ]]; then
		step "Removing .env ..."
		safe_assert_env_file "${ROOT}/.env" "${ROOT}"
		safe_rm_file "${ROOT}/.env"
		log "Removed .env"
	fi

	log "Uninstall complete (services and images removed)"
	log "Install directory kept: ${ROOT}"
	log "  Remaining: install.sh, docker-compose.yml, deploy/, images/, payload/, backup/, and other package files"
	if [[ "${with_sourcelens}" -eq 0 ]] && sourcelens_installed; then
		log "  SourceLens still installed at ${SOURCELENS_INSTALL_DIR} (use --with-sourcelens to remove)"
	fi
	if [[ "${purge_data}" -eq 0 ]]; then
		log "  data/ was preserved (use --purge-data or --purge-all to remove)"
	fi
	if [[ "${purge_config}" -eq 0 ]]; then
		log "  .env was preserved (use --purge-config or --purge-all to remove)"
	fi
	if [[ "${purge_media}" -eq 0 ]]; then
		log "  media publish artifacts were preserved (use --purge-media to remove)"
	fi
	log "To remove the install directory manually after you no longer need this copy:"
	log "  sudo rm -rf ${ROOT}"
	log "Host Docker CE (if installed from the bundled archive) is not removed by uninstall."
}

cmd_upgrade() {
	local from=""
	local sourcelens_mode=-1 remove_sourcelens=0 purge_sourcelens_data=0
	local src_root new_version cur_version upgrade_sourcelens=0
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--from)
			shift
			from="${1:-}"
			[[ -n "${from}" ]] || die "--from requires a path"
			;;
		--with-sourcelens) sourcelens_mode=1 ;;
		--hfl-only) sourcelens_mode=0 ;;
		--remove-sourcelens) remove_sourcelens=1 ;;
		--purge-sourcelens-data) purge_sourcelens_data=1 ;;
		--yes) UPGRADE_YES=1 ;;
		*) die "unknown upgrade option: $1" 2 ;;
		esac
		shift
	done
	[[ -n "${from}" ]] || die "upgrade requires --from <directory-or.tar.gz>"

	init_install_root
	preflight_package_layout
	cur_version="$(read_version)"
	log "======== HyperFileLens upgrade ${cur_version} ========"

	trap cleanup_upgrade_and_finish EXIT
	src_root="$(prepare_upgrade_source "${from}")"
	new_version="$(read_version_from_dir "${src_root}")"

	if [[ "${new_version}" == "${cur_version}" ]]; then
		confirm_same_version_upgrade "${cur_version}"
	elif version_lt "${new_version}" "${cur_version}"; then
		die "downgrade not supported (${new_version} < ${cur_version})"
	fi

	log "Upgrading: ${cur_version} -> ${new_version}"

	step "[1/7] Backing up current config and data ..."
	backup_postgresql_dump
	backup_env_and_data

	step "[2/7] Validating upgrade package ..."
	validate_publish_artifacts "${src_root}"
	if package_has_sourcelens_dir "${src_root}"; then
		preflight_sourcelens_bundle "${src_root}"
	fi
	if should_upgrade_sourcelens "${sourcelens_mode}" "${src_root}"; then
		upgrade_sourcelens=1
	fi
	if [[ "${remove_sourcelens}" -eq 1 ]]; then
		upgrade_sourcelens=0
	fi

	step "[3/7] Checking/upgrading Docker ..."
	upgrade_host_docker_from_source "${ROOT}" "${src_root}"
	require_docker
	ensure_bridge_network

	step "Preloading verified target images before the maintenance window ..."
	load_images_from_manifest "$([[ "${upgrade_sourcelens}" -eq 0 ]] && echo 1 || echo 0)" "${src_root}"

	step "[4/7] Stopping current services ..."
	if [[ -f "${ROOT}/.env" ]]; then
		compose_in_root down || true
	fi
	if should_remove_sourcelens "${remove_sourcelens}" || [[ "${upgrade_sourcelens}" -eq 1 ]]; then
		stop_bundled_sourcelens
	fi
	if should_remove_sourcelens "${remove_sourcelens}"; then
		remove_sourcelens_images
	fi

	step "[5/7] Merging .env and overwriting app files ..."
	sync_env_from_example "${src_root}/.env.example"
	apply_upgrade_files "${src_root}" "${remove_sourcelens}"
	update_env_versions "${new_version}"

	if [[ "${remove_sourcelens}" -eq 1 && "${purge_sourcelens_data}" -eq 1 ]]; then
		purge_sourcelens_data_dir
	fi
	if [[ "${remove_sourcelens}" -eq 1 ]]; then
		log "SourceLens application runtime removed from this host"
	fi

	step "[6/7] Loading images and starting services ..."
	if [[ "${upgrade_sourcelens}" -eq 1 ]]; then
		install_bundled_sourcelens
	fi
	if [[ "$(configured_sourcelens_mode)" == "bundled" ]] \
		&& sourcelens_installed \
		&& [[ "${remove_sourcelens}" -eq 0 ]]; then
		configure_lens_bridge_env
	fi
	ensure_data_dirs
	sync_runtime_media
	compose_in_root up -d postgres redis
	compose_in_root run --rm worker migrate
	compose_in_root up -d --no-build --remove-orphans
	wait_for_hfl_health || die "HyperFileLens failed its post-upgrade health gate"
	wait_for_sourcelens_health || die "bundled SourceLens failed its post-upgrade health gate"

	step "[7/7] Cleaning up temporary directory ..."
	cleanup_upgrade_tmp
	trap finish_session EXIT

	log "Upgrade complete: ${new_version}"
	compose_in_root ps
	print_console_access_summary
}

main() {
	local -a args=()
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--log-file)
			[[ $# -ge 2 && -n "${2:-}" && "${2:0:1}" != "-" ]] || die "--log-file requires a value" 2
			LOG_FILE="$2"
			shift 2
			;;
		--verbose)
			VERBOSE=1
			shift
			;;
		--print-config)
			PRINT_CONFIG=1
			shift
			;;
		*)
			args+=("$1")
			shift
			;;
		esac
	done
	set -- "${args[@]}"

	case "${VERBOSE}" in
	0 | 1) ;;
	*) die "--verbose/HFL_LOG_VERBOSE must resolve to 0 or 1" 2 ;;
	esac
	if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
		print_config
		return 0
	fi
	if [[ $# -gt 0 && ( "$1" == "-h" || "$1" == "--help" || "$1" == "help" ) ]]; then
		usage
		return 0
	fi
	configure_logging
	SESSION_STARTED=1
	trap finish_session EXIT
	trap 'exit 130' INT TERM
	log "Installer session started"

	if [[ $# -eq 0 ]]; then
		cmd_install
		return 0
	fi

	local cmd=$1
	case "${cmd}" in
	install | start | stop | restart | status | uninstall | upgrade | lang-pack)
		shift
		;;
	-*)
		cmd_install "$@"
		return 0
		;;
	*)
		die "unknown command: ${cmd} (use --help)" 2
		;;
	esac

	case "${cmd}" in
	install) cmd_install "$@" ;;
	start) cmd_start "$@" ;;
	stop) cmd_stop "$@" ;;
	restart) cmd_restart "$@" ;;
	status) cmd_status "$@" ;;
	uninstall) cmd_uninstall "$@" ;;
	upgrade) cmd_upgrade "$@" ;;
	lang-pack) cmd_language_pack "$@" ;;
	esac
}

main "$@"

#!/usr/bin/env bash
# Shared SourceLens helpers for development and release workflows.
set -euo pipefail

_sourcelens_common_loaded="${_sourcelens_common_loaded:-}"
if [[ -n "${_sourcelens_common_loaded}" ]]; then
	return 0 2>/dev/null || exit 0
fi
_sourcelens_common_loaded=1

_sourcelens_common_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HFL_ROOT="$(cd "${_sourcelens_common_dir}/../.." && pwd)"
SOURCELENS_INSTALLER_DIR="${HFL_ROOT}/deploy/installer"
SOURCELENS_BUILD_DIR="${HFL_ROOT}/build/sourcelens"
SOURCELENS_SOURCE_CACHE="${SOURCELENS_BUILD_DIR}/source"
SOURCELENS_DEV_DIR="${SOURCELENS_BUILD_DIR}/dev"
SOURCELENS_DATA_DIR="${HFL_ROOT}/data/sourcelens"
SOURCELENS_DEV_ENV_FILE="${SOURCELENS_DATA_DIR}/config/.env"
SOURCELENS_BUILD_ENV_FILE="${HFL_ROOT}/tools/sourcelens/defaults.env"
SOURCELENS_COMPOSE_PROJECT="${SOURCELENS_COMPOSE_PROJECT:-hyperfilelens-sourcelens}"
SOURCELENS_SHARED_NETWORK="hyperfilelens-bridge"

SOURCELENS_COMPOSE=()

# shellcheck source=../lib/logging.sh
source "${HFL_ROOT}/tools/lib/logging.sh"
# shellcheck source=../lib/docker-images.sh
source "${HFL_ROOT}/tools/lib/docker-images.sh"
sourcelens_log() { hfl_log_info "$@"; }
sourcelens_die() { hfl_die "$1" "${2:-1}"; }

sourcelens_load_config() {
	local console_port_override="${SOURCELENS_NGINX_HTTPS_PORT:-}"
	if [[ -f "${SOURCELENS_BUILD_ENV_FILE}" ]]; then
		# shellcheck disable=SC1090
		source "${SOURCELENS_BUILD_ENV_FILE}"
	fi
	if [[ -n "${console_port_override}" ]]; then
		SOURCELENS_NGINX_HTTPS_PORT="${console_port_override}"
	fi
	BUILD_SOURCELENS="${BUILD_SOURCELENS:-1}"
	SOURCELENS_GIT_URL="${SOURCELENS_GIT_URL:-https://github.com/HyperBDR/sourcelens.git}"
	SOURCELENS_GIT_REF="${SOURCELENS_GIT_REF:-v0.4.0}"
	SOURCELENS_UPSTREAM_IMAGE_PREFIX="${SOURCELENS_UPSTREAM_IMAGE_PREFIX:-oneprocloud}"
	SOURCELENS_IMAGE_REGISTRY="${SOURCELENS_IMAGE_REGISTRY:-}"
	SOURCELENS_IMAGE_REGISTRY="${SOURCELENS_IMAGE_REGISTRY%/}"
	SOURCELENS_LENSNODE_IMAGE="${SOURCELENS_LENSNODE_IMAGE:-}"
	SOURCELENS_NGINX_HTTPS_PORT="${SOURCELENS_NGINX_HTTPS_PORT:-11445}"
	SOURCELENS_CONSOLE_BIND_ADDRESS="${SOURCELENS_CONSOLE_BIND_ADDRESS:-0.0.0.0}"
	SOURCELENS_CONSOLE_PORT="${SOURCELENS_CONSOLE_PORT:-${SOURCELENS_NGINX_HTTPS_PORT}}"
	SOURCELENS_INSTALL_DIR="${SOURCELENS_INSTALL_DIR:-/opt/hyperfilelens/sourcelens}"
	SOURCELENS_EMBED_LENSNODE="${SOURCELENS_EMBED_LENSNODE:-0}"
	SOURCELENS_DOCKER_PLATFORM="${SOURCELENS_DOCKER_PLATFORM:-${DOCKER_DEFAULT_PLATFORM:-linux/amd64}}"
	SOURCELENS_APT_MIRROR="${SOURCELENS_APT_MIRROR:-${APT_MIRROR:-${BUILD_APT_MIRROR:-}}}"
	SOURCELENS_PIP_INDEX_URL="${SOURCELENS_PIP_INDEX_URL:-${PIP_INDEX_URL:-${BUILD_PIP_INDEX_URL:-}}}"
	SOURCELENS_PIP_TRUSTED_HOST="${SOURCELENS_PIP_TRUSTED_HOST:-${PIP_TRUSTED_HOST:-${BUILD_PIP_TRUSTED_HOST:-}}}"
	SOURCELENS_UV_HTTP_TIMEOUT="${SOURCELENS_UV_HTTP_TIMEOUT:-${UV_HTTP_TIMEOUT:-${BUILD_UV_HTTP_TIMEOUT:-120}}}"
	SOURCELENS_UV_CONCURRENT_DOWNLOADS="${SOURCELENS_UV_CONCURRENT_DOWNLOADS:-${UV_CONCURRENT_DOWNLOADS:-${BUILD_UV_CONCURRENT_DOWNLOADS:-2}}}"
	SOURCELENS_PIP_RETRY_MAX="${SOURCELENS_PIP_RETRY_MAX:-${HFL_PIP_RETRY_MAX:-${BUILD_PIP_RETRY_MAX:-5}}}"
	SOURCELENS_PIP_RETRY_DELAY="${SOURCELENS_PIP_RETRY_DELAY:-${HFL_PIP_RETRY_DELAY:-${BUILD_PIP_RETRY_DELAY:-5}}}"
	SOURCELENS_NPM_REGISTRY="${SOURCELENS_NPM_REGISTRY:-${NPM_REGISTRY:-${BUILD_NPM_REGISTRY:-}}}"
	SOURCELENS_DOCKER_MIRROR="${SOURCELENS_DOCKER_MIRROR:-${DOCKER_DOWNLOAD_MIRROR:-}}"
	SOURCELENS_DOCKER_PULL_TIMEOUT="${SOURCELENS_DOCKER_PULL_TIMEOUT:-${DOCKER_PULL_TIMEOUT_SECONDS:-180}}"
	SOURCELENS_DOCKER_PULL_RETRIES="${SOURCELENS_DOCKER_PULL_RETRIES:-${DOCKER_PULL_RETRIES:-2}}"
	SOURCELENS_OFFLINE="${SOURCELENS_OFFLINE:-${DEV_OFFLINE:-0}}"
	SOURCELENS_FORCE_PULL="${SOURCELENS_FORCE_PULL:-0}"
	SOURCELENS_GIT_TIMEOUT_SECONDS="${SOURCELENS_GIT_TIMEOUT_SECONDS:-120}"
	SOURCELENS_GIT_RETRIES="${SOURCELENS_GIT_RETRIES:-2}"
}

sourcelens_resolve_version() {
	[[ "${SOURCELENS_GIT_REF}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]] \
		|| sourcelens_die "invalid SourceLens release ref: ${SOURCELENS_GIT_REF} (expected vX.Y.Z)" 2
	SOURCELENS_VERSION="${BASH_REMATCH[1]}"
	if [[ "${SOURCELENS_HFL_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
		SOURCELENS_DISTRIBUTION_TAG="${SOURCELENS_HFL_VERSION}-sl${SOURCELENS_VERSION}"
	else
		SOURCELENS_DISTRIBUTION_TAG="${SOURCELENS_VERSION}"
	fi
	if [[ -z "${SOURCELENS_LENSNODE_IMAGE}" ]]; then
		SOURCELENS_LENSNODE_IMAGE="$(sourcelens_lensnode_image_ref)"
	fi
}

sourcelens_strip_trailing_slashes() {
	local value="${1:-}"
	while [[ "${value}" == */ ]]; do
		value="${value%/}"
	done
	printf '%s' "${value}"
}

sourcelens_platform_uses_ubuntu_ports() {
	local platform="${1:-}"
	case "${platform}" in
	linux/arm64 | linux/arm64/* | arm64 | aarch64 | linux/arm/v* | armhf | armv*) return 0 ;;
	*) return 1 ;;
	esac
}

sourcelens_normalize_apt_mirror_url() {
	local distro=$1
	local platform="${3:-}"
	local mirror
	mirror="$(sourcelens_strip_trailing_slashes "${2:-}")"
	[[ -n "${mirror}" ]] || return 0

	case "${distro}" in
	ubuntu)
		if sourcelens_platform_uses_ubuntu_ports "${platform}"; then
			case "${mirror}" in
			*/ubuntu-ports) printf '%s' "${mirror}" ;;
			*/ubuntu) printf '%s-ports' "${mirror}" ;;
			*) printf '%s/ubuntu-ports' "${mirror}" ;;
			esac
		else
			case "${mirror}" in
			*/ubuntu) printf '%s' "${mirror}" ;;
			*/ubuntu-ports) printf '%s' "${mirror%-ports}" ;;
			*) printf '%s/ubuntu' "${mirror}" ;;
			esac
		fi
		;;
	debian)
		case "${mirror}" in
		*/debian) printf '%s' "${mirror}" ;;
		*) printf '%s/debian' "${mirror}" ;;
		esac
		;;
	*)
		sourcelens_die "unsupported apt mirror distro: ${distro}"
		;;
	esac
}

sourcelens_restore_source_dockerfiles() {
	local src=$1
	[[ -d "${src}/.git" ]] || return 0
	git -C "${src}" checkout -- \
		Dockerfile \
		lensnode/Dockerfile \
		frontend/Dockerfile \
		frontend/Dockerfile.dev 2>/dev/null || true
}

# GitHub HTTPS auth for private SourceLens clone/fetch (env GITHUB_TOKEN or --github-token).
sourcelens_git_needs_github_token() {
	local url="${1:-${SOURCELENS_GIT_URL}}"
	[[ "${url}" =~ ^https://([^/@]+@)?github\.com/ ]]
}

sourcelens_git() {
	local token="${GITHUB_TOKEN:-}"
	if [[ -n "${token}" ]]; then
		GIT_TERMINAL_PROMPT=0 \
			git \
			-c "url.https://x-access-token:${token}@github.com/.insteadOf=https://github.com/" \
			-c "url.https://x-access-token:${token}@github.com/.insteadOf=git@github.com:" \
			"$@"
	else
		GIT_TERMINAL_PROMPT=0 \
			git \
			-c "url.https://github.com/.insteadOf=https://github.com/" \
			"$@"
	fi
}

sourcelens_git_network() {
	local attempt timeout_seconds="${SOURCELENS_GIT_TIMEOUT_SECONDS}" retries="${SOURCELENS_GIT_RETRIES}"
	local clone_dest=""
	[[ "${1:-}" != "clone" ]] || clone_dest="${!#}"
	[[ "${timeout_seconds}" =~ ^[1-9][0-9]*$ && "${retries}" =~ ^[1-9][0-9]*$ ]] \
		|| sourcelens_die "SourceLens Git timeout and retries must be positive integers" 2
	for attempt in $(seq 1 "${retries}"); do
		if [[ -n "${clone_dest}" && "${attempt}" -gt 1 ]]; then
			rm -rf "${clone_dest}"
		fi
		if [[ -n "${GITHUB_TOKEN:-}" ]]; then
			if timeout --foreground "${timeout_seconds}s" env GIT_TERMINAL_PROMPT=0 git \
				-c "url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf=https://github.com/" \
				-c "url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf=git@github.com:" "$@"; then
				return 0
			fi
		elif timeout --foreground "${timeout_seconds}s" env GIT_TERMINAL_PROMPT=0 git \
			-c "url.https://github.com/.insteadOf=https://github.com/" "$@"; then
			return 0
		fi
		sourcelens_log "SourceLens Git command failed or timed out (attempt ${attempt}/${retries})"
	done
	[[ -z "${clone_dest}" ]] || rm -rf "${clone_dest}"
	return 1
}

sourcelens_image_exists() {
	docker image inspect "$1" >/dev/null 2>&1
}

sourcelens_image_digest() {
	local image=$1 digest
	digest="$(docker image inspect "${image}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
	[[ -n "${digest}" ]] \
		|| digest="$(docker image inspect "${image}" --format '{{.Id}}' 2>/dev/null || true)"
	[[ -n "${digest}" ]] || digest="${image}"
	printf '%s' "${digest}"
}

sourcelens_lensnode_image_id() {
	local ref=$1
	docker image inspect "${ref}" --format '{{.Id}}' 2>/dev/null || true
}

sourcelens_lensnode_supports_insecure_tls() {
	local ref=$1
	docker run --rm -e LENSNODE_INSECURE_TLS=1 "${ref}" \
		python -c "from lensnode.tls import tls_insecure_enabled; raise SystemExit(0 if tls_insecure_enabled() else 1)" \
		>/dev/null 2>&1
}

sourcelens_gateway_lensnode_bundle_image_id() {
	local archive=$1
	python3 - "${archive}" <<'PY'
import gzip
import json
import sys
import tarfile

path = sys.argv[1]
try:
    with gzip.open(path, "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r:") as tar:
            member = tar.getmember("index.json")
            data = json.load(tar.extractfile(member))
except (
    EOFError,
    OSError,
    KeyError,
    gzip.BadGzipFile,
    json.JSONDecodeError,
    tarfile.TarError,
):
    sys.exit(0)

manifests = data.get("manifests") or []
if not manifests:
    sys.exit(0)
digest = manifests[0].get("digest", "")
if digest.startswith("sha256:"):
    print(digest)
PY
}

sourcelens_ensure_compose() {
	if ((${#SOURCELENS_COMPOSE[@]})); then
		return 0
	fi
	if docker compose version >/dev/null 2>&1; then
		SOURCELENS_COMPOSE=(docker compose)
	else
		sourcelens_die "Docker Compose v2 is required"
	fi
}

sourcelens_ensure_shared_network() {
	if docker network inspect "${SOURCELENS_SHARED_NETWORK}" >/dev/null 2>&1; then
		return 0
	fi
	sourcelens_log "Creating shared bridge network ${SOURCELENS_SHARED_NETWORK}"
	docker network create "${SOURCELENS_SHARED_NETWORK}" >/dev/null
}

sourcelens_ensure_tls_certs() {
	local cert_dir=$1
	local cert="${cert_dir}/tls.crt"
	local key="${cert_dir}/tls.key"
	mkdir -p "${cert_dir}"
	if [[ -s "${cert}" && -s "${key}" ]]; then
		return 0
	fi
	command -v openssl >/dev/null 2>&1 \
		|| sourcelens_die "openssl is required to generate SourceLens TLS certificates"
	sourcelens_log "Generating SourceLens development TLS certificates in ${cert_dir#${HFL_ROOT}/}"
	openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
		-keyout "${key}" \
		-out "${cert}" \
		-subj "/CN=localhost" \
		-addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1" 2>/dev/null
	chmod 644 "${cert}"
	chmod 600 "${key}"
}

sourcelens_sync_source() {
	command -v git >/dev/null 2>&1 || sourcelens_die "git not found (required to fetch SourceLens)"
	if sourcelens_git_needs_github_token && [[ -z "${GITHUB_TOKEN:-}" ]]; then
		sourcelens_log "Note: SOURCELENS_GIT_URL uses GitHub HTTPS; set GITHUB_TOKEN or pass --github-token for private repo clone"
	elif sourcelens_git_needs_github_token && [[ -n "${GITHUB_TOKEN:-}" ]]; then
		sourcelens_log "Using GITHUB_TOKEN for GitHub HTTPS auth"
	fi
	mkdir -p "$(dirname "${SOURCELENS_SOURCE_CACHE}")"
	if [[ -d "${SOURCELENS_SOURCE_CACHE}" && ! -d "${SOURCELENS_SOURCE_CACHE}/.git" ]]; then
		sourcelens_log "Removing incomplete SourceLens clone at ${SOURCELENS_SOURCE_CACHE#${HFL_ROOT}/}"
		rm -rf "${SOURCELENS_SOURCE_CACHE}"
	fi
	if [[ "${SOURCELENS_OFFLINE}" -eq 1 && ! -d "${SOURCELENS_SOURCE_CACHE}/.git" ]]; then
		sourcelens_die "SourceLens source cache is missing and offline mode forbids cloning"
	fi
	if [[ ! -d "${SOURCELENS_SOURCE_CACHE}/.git" ]]; then
		sourcelens_log "Cloning ${SOURCELENS_GIT_URL} (${SOURCELENS_GIT_REF})..."
		sourcelens_git_network clone "${SOURCELENS_GIT_URL}" "${SOURCELENS_SOURCE_CACHE}"
	fi
	git -C "${SOURCELENS_SOURCE_CACHE}" reset --hard HEAD >/dev/null
	rm -f "${SOURCELENS_SOURCE_CACHE}/.hfl-built-commit"
	git -C "${SOURCELENS_SOURCE_CACHE}" clean -fd -- \
		backend/lens/bridge_views.py \
		backend/lens/migrations/0018_lensnode_owner.py \
		lensnode/lensnode/tls.py \
		lensnode/tests/test_tls.py >/dev/null
	sourcelens_log "Checking out SourceLens ref ${SOURCELENS_GIT_REF}..."
	(
		cd "${SOURCELENS_SOURCE_CACHE}"
		if [[ "${SOURCELENS_OFFLINE}" -eq 1 ]]; then
			fetch_succeeded=0
			sourcelens_log "Offline mode: using the existing SourceLens source cache"
		elif sourcelens_git_network fetch origin --tags --prune; then
			fetch_succeeded=1
		else
			fetch_succeeded=0
			sourcelens_log "SourceLens fetch failed; using the existing local source cache"
		fi
		if sourcelens_git show-ref --verify --quiet "refs/heads/${SOURCELENS_GIT_REF}"; then
			sourcelens_git checkout "${SOURCELENS_GIT_REF}"
			if [[ "${fetch_succeeded}" -eq 1 ]]; then
				sourcelens_git_network pull --ff-only origin "${SOURCELENS_GIT_REF}" || true
			fi
		elif sourcelens_git show-ref --verify --quiet "refs/tags/${SOURCELENS_GIT_REF}"; then
			sourcelens_git checkout "${SOURCELENS_GIT_REF}"
		else
			sourcelens_git checkout "${SOURCELENS_GIT_REF}"
		fi
		if [[ "${SOURCELENS_OFFLINE}" -eq 1 ]]; then
			sourcelens_git submodule update --init --recursive --no-fetch
		else
			sourcelens_git_network submodule update --init --recursive
		fi
	)
	# shellcheck source=sourcelens-lensnode-patch.sh
	source "${HFL_ROOT}/tools/sourcelens/lensnode-patch.sh"
	sourcelens_apply_lensnode_hfl_patches "${SOURCELENS_SOURCE_CACHE}"
	sourcelens_restore_source_dockerfiles "${SOURCELENS_SOURCE_CACHE}"
}

sourcelens_built_commit_stamp() {
	printf '%s/.build-stamp' "${SOURCELENS_BUILD_DIR}"
}

sourcelens_read_built_commit() {
	local stamp
	stamp="$(sourcelens_built_commit_stamp)"
	[[ -f "${stamp}" ]] || return 0
	tr -d ' \n\r' <"${stamp}"
}

sourcelens_write_built_commit() {
	local commit=$1
	local stamp
	stamp="$(sourcelens_built_commit_stamp)"
	mkdir -p "$(dirname "${stamp}")"
	printf '%s\n' "${commit}" >"${stamp}"
}

sourcelens_current_build_stamp() {
	local commit patch_file patch_digest="none"
	commit="$(git -C "${SOURCELENS_SOURCE_CACHE}" rev-parse HEAD 2>/dev/null || true)"
	patch_file="${SOURCELENS_INSTALLER_DIR}/sourcelens/lensnode-tls.patch"
	if [[ -f "${patch_file}" ]]; then
		patch_digest="$(sha256sum "${patch_file}" | awk '{print $1}')"
	fi
	printf '%s:%s:%s' "${SOURCELENS_VERSION}" "${commit}" "${patch_digest}"
}

sourcelens_restore_compose_file() {
	local src=$1
	[[ -d "${src}/.git" ]] || return 0
	git -C "${src}" checkout -- docker-compose.yml 2>/dev/null || true
}

sourcelens_patch_compose_lensnode_apt_mirror() {
	local src=$1
	local debian_default=$2
	local compose="${src}/docker-compose.yml"
	[[ -f "${compose}" ]] || return 0
	python3 - "${compose}" "${debian_default}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
debian_default = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
out = []
service = None
in_lensnode_build = False
in_lensnode_args = False
has_apt = False
insert_after_idx = None

for idx, line in enumerate(lines):
    stripped = line.strip()
    if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
        service = stripped[:-1]
        in_lensnode_build = False
        in_lensnode_args = False
    if service == "lensnode" and stripped == "build:":
        in_lensnode_build = True
    if service == "lensnode" and in_lensnode_build and stripped == "args:":
        in_lensnode_args = True
        has_apt = False
        insert_after_idx = None
    if service == "lensnode" and in_lensnode_args:
        if stripped.startswith("APT_MIRROR_URL:"):
            has_apt = True
            indent = line[: len(line) - len(line.lstrip())]
            line = (
                f"{indent}APT_MIRROR_URL: "
                f"${{DEBIAN_APT_MIRROR_URL:-{debian_default}}}\n"
            )
        elif line.startswith("        ") and ":" in stripped:
            insert_after_idx = len(out)
        elif stripped != "args:" and stripped and not line.startswith("        "):
            in_lensnode_args = False
    out.append(line)

if not has_apt and insert_after_idx is not None:
    out.insert(
        insert_after_idx + 1,
        f"        APT_MIRROR_URL: ${{DEBIAN_APT_MIRROR_URL:-{debian_default}}}\n",
    )

path.write_text("".join(out), encoding="utf-8")
PY
}

sourcelens_patch_dockerfile_uv_network() {
	local src=$1
	local timeout=$2
	local concurrent=$3
	local dockerfile
	for dockerfile in "${src}/Dockerfile" "${src}/lensnode/Dockerfile"; do
		[[ -f "${dockerfile}" ]] || continue
		python3 - "${dockerfile}" "${timeout}" "${concurrent}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
timeout, concurrent = sys.argv[2:4]
settings = [
    ("UV_HTTP_TIMEOUT", timeout),
    ("UV_CONCURRENT_DOWNLOADS", concurrent),
]
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
out = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("ARG PIP_TRUSTED_HOST"):
        out.append(line)
        indent = line[: len(line) - len(line.lstrip())]
        for name, default in settings:
            if f"ARG {name}" not in text:
                out.append(f"{indent}ARG {name}={default}\n")
        continue
    if "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}" in stripped:
        if stripped.startswith("ENV "):
            out.append(line)
            indent = line[: len(line) - len(line.lstrip())]
            for name, _ in settings:
                if f"{name}=${{{name}}}" not in text:
                    out.append(f"{indent}ENV {name}=${{{name}}}\n")
            continue
        missing = [name for name, _ in settings if f"{name}=${{{name}}}" not in text]
        if not missing:
            out.append(line)
            continue
        indent = line[: len(line) - len(line.lstrip())]
        base = line[:-1] if line.endswith("\n") else line
        if not base.rstrip().endswith("\\"):
            base = f"{base.rstrip()} \\"
        out.append(f"{base}\n")
        for idx, name in enumerate(missing):
            suffix = " \\\n" if idx < len(missing) - 1 else "\n"
            out.append(f"{indent}{name}=${{{name}}}{suffix}")
        continue
    out.append(line)

updated = "".join(out)
for name, default in settings:
    if f"ARG {name}" not in updated or f"{name}=${{{name}}}" not in updated:
        sys.stderr.write(f"ERROR: could not patch {name} in {path}\n")
        sys.exit(1)

path.write_text(updated, encoding="utf-8")
PY
	done
}

sourcelens_patch_dockerfile_pip_resilience() {
	local src=$1
	local retry_max=$2
	local retry_delay=$3
	local dockerfile
	for dockerfile in "${src}/Dockerfile" "${src}/lensnode/Dockerfile"; do
		[[ -f "${dockerfile}" ]] || continue
		python3 - "${dockerfile}" "${retry_max}" "${retry_delay}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
retry_max, retry_delay = sys.argv[2:4]
text = path.read_text(encoding="utf-8")
if "hfl-pip-resilience" in text:
    sys.exit(0)

if not text.lstrip().startswith("# syntax="):
    text = "# syntax=docker/dockerfile:1.4\n# hfl-pip-resilience\n" + text

mount_run = (
    "RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked "
    "--mount=type=cache,target=/root/.cache/pip,sharing=locked set -eux; \\\n"
)
inject = (
    f"    export UV_CACHE_DIR=/root/.cache/uv; \\\n"
    f"    export HFL_PIP_RETRY_MAX={retry_max}; \\\n"
    f"    export HFL_PIP_RETRY_DELAY={retry_delay}; \\\n"
    "    hfl_retry() { max=${HFL_PIP_RETRY_MAX}; delay=${HFL_PIP_RETRY_DELAY}; n=1; "
    'while [ "$n" -le "$max" ]; do if "$@"; then return 0; fi; '
    'echo "[hfl] pip/uv attempt ${n}/${max} failed, retrying..."; '
    'n=$((n+1)); [ "$n" -le "$max" ] && sleep "$delay"; done; return 1; }; \\\n'
)

docker_instr = (
    "FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ARG", "ENTRYPOINT", "COPY",
    "WORKDIR", "SHELL", "HEALTHCHECK", "STOPSIGNAL", "USER", "VOLUME",
)

def is_run_start(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("RUN set -eux;") or (
        stripped.startswith("RUN --mount=") and " set -eux;" in stripped
    )

def is_docker_instruction(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return any(stripped.startswith(f"{name} ") or stripped == name for name in docker_instr)

lines = text.splitlines(keepends=True)
out = []
idx = 0
while idx < len(lines):
    line = lines[idx]
    if is_run_start(line):
        block = [line]
        j = idx + 1
        while j < len(lines):
            nxt = lines[j]
            if is_docker_instruction(nxt):
                break
            block.append(nxt)
            j += 1
        block_text = "".join(block)
        if "hfl-pip-resilience-applied" in block_text:
            out.append(block_text)
            idx = j
            continue
        if "uv pip install" in block_text or "uv pip compile" in block_text:
            if block[0].lstrip().startswith("RUN --mount="):
                block.insert(1, inject)
            else:
                block[0] = mount_run
                block.insert(1, inject)
            block_text = "".join(block)
            block_text = block_text.replace("uv pip compile", "hfl_retry uv pip compile")
            block_text = block_text.replace("uv pip install", "hfl_retry uv pip install")
            if not block_text.rstrip().endswith("# hfl-pip-resilience-applied"):
                block_text = block_text.rstrip("\n") + "\n    # hfl-pip-resilience-applied\n"
            out.append(block_text)
            idx = j
            continue
    out.append(line)
    idx += 1

path.write_text("".join(out), encoding="utf-8")
PY
	done
}

sourcelens_patch_compose_uv_network() {
	local src=$1
	local timeout=$2
	local concurrent=$3
	local compose="${src}/docker-compose.yml"
	[[ -f "${compose}" ]] || return 0
	python3 - "${compose}" "${timeout}" "${concurrent}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
timeout, concurrent = sys.argv[2:4]
services = {"backend-api", "lensnode"}
settings = [
    ("UV_HTTP_TIMEOUT", timeout),
    ("UV_CONCURRENT_DOWNLOADS", concurrent),
]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
out = []
service = None
in_build = False
in_args = False
present = set()
insert_after_idx = None

for line in lines:
    stripped = line.strip()
    if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
        service = stripped[:-1]
        in_build = False
        in_args = False
        present = set()
    if service in services and stripped == "build:":
        in_build = True
    if service in services and in_build and stripped == "args:":
        in_args = True
        present = set()
        insert_after_idx = None
    if service in services and in_args:
        for name, default in settings:
            if stripped.startswith(f"{name}:"):
                present.add(name)
                indent = line[: len(line) - len(line.lstrip())]
                line = f"{indent}{name}: ${{{name}:-{default}}}\n"
        if line.startswith("        ") and ":" in stripped:
            insert_after_idx = len(out)
        elif stripped != "args:" and stripped and not line.startswith("        "):
            missing = [item for item in settings if item[0] not in present]
            if missing and insert_after_idx is not None:
                offset = 1
                for name, default in missing:
                    out.insert(
                        insert_after_idx + offset,
                        f"        {name}: ${{{name}:-{default}}}\n",
                    )
                    offset += 1
            in_args = False
    out.append(line)

path.write_text("".join(out), encoding="utf-8")
PY
}

sourcelens_patch_frontend_dockerfile_npm_registry() {
	local src=$1
	local dockerfile="${src}/frontend/Dockerfile"
	[[ -f "${dockerfile}" ]] || return 0
	python3 - "${dockerfile}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
out = []
inserted_arg = "ARG NPM_REGISTRY" in text
inserted_run = "fetch-retries" in text
for line in lines:
    stripped = line.strip()
    if not inserted_arg and stripped.startswith("ARG VITE_GA_ID"):
        out.append(line)
        out.append("ARG NPM_REGISTRY\n")
        inserted_arg = True
        continue
    if (
        not inserted_run
        and stripped.startswith("RUN npm ci")
        and "npm config set registry" not in text
    ):
        out.append(
            'RUN if [ -n "${NPM_REGISTRY}" ]; then \\\n'
            '      npm config set registry "${NPM_REGISTRY}"; \\\n'
            '      npm config set fetch-retries 5; \\\n'
            '      npm config set fetch-retry-mintimeout 20000; \\\n'
            '      npm config set fetch-retry-maxtimeout 120000; \\\n'
            '    fi\n'
        )
        inserted_run = True
    elif (
        not inserted_run
        and "npm config set registry" in stripped
        and "fetch-retries" not in text
    ):
        out.append(line.rstrip("\n").rstrip("\\").rstrip() + " ; \\\n")
        out.append("      npm config set fetch-retries 5; \\\n")
        out.append("      npm config set fetch-retry-mintimeout 20000; \\\n")
        out.append("      npm config set fetch-retry-maxtimeout 120000; \\\n")
        out.append("    fi\n")
        inserted_run = True
        continue
    out.append(line)

if not inserted_arg:
    sys.stderr.write(f"ERROR: could not patch NPM_REGISTRY in {path}\n")
    sys.exit(1)

path.write_text("".join(out), encoding="utf-8")
PY
}

sourcelens_patch_compose_npm_registry() {
	local src=$1
	local compose="${src}/docker-compose.yml"
	[[ -f "${compose}" ]] || return 0
	python3 - "${compose}" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
pattern = re.compile(
    r"(?ms)(^  frontend:\n.*?^    build:\n.*?^      args:\n)(.*?)(?=^    \S)"
)
matches = list(pattern.finditer(text))
if len(matches) != 1:
    raise SystemExit(
        f"expected one frontend build args block in {path}, found {len(matches)}"
    )

match = matches[0]
args = match.group(2)
line = "        NPM_REGISTRY: ${NPM_REGISTRY:-}\n"
if re.search(r"(?m)^        NPM_REGISTRY:.*$", args):
    args = re.sub(r"(?m)^        NPM_REGISTRY:.*$", line.rstrip(), args, count=1)
else:
    args = args.rstrip("\n") + "\n" + line
text = text[: match.start(2)] + args + text[match.end(2) :]
path.write_text(text, encoding="utf-8")
PY
}

sourcelens_distribution_image_ref() {
	local component=$1 tag="${2:-${SOURCELENS_DISTRIBUTION_TAG:-${SOURCELENS_VERSION}}}"
	local repository="hyperfilelens-sourcelens-${component}"
	if [[ -n "${SOURCELENS_IMAGE_REGISTRY}" ]]; then
		printf '%s/%s:%s' "${SOURCELENS_IMAGE_REGISTRY}" "${repository}" "${tag}"
	else
		printf '%s:%s' "${repository}" "${tag}"
	fi
}

sourcelens_upstream_image_ref() {
	local component=$1 tag="${2:-${SOURCELENS_VERSION}}"
	printf '%s/sourcelens-%s:%s' "${SOURCELENS_UPSTREAM_IMAGE_PREFIX}" "${component}" "${tag}"
}

sourcelens_backend_image_ref() {
	sourcelens_distribution_image_ref backend "${1:-${SOURCELENS_DISTRIBUTION_TAG:-${SOURCELENS_VERSION}}}"
}

sourcelens_frontend_image_ref() {
	sourcelens_distribution_image_ref frontend "${1:-${SOURCELENS_DISTRIBUTION_TAG:-${SOURCELENS_VERSION}}}"
}

sourcelens_lensnode_image_ref() {
	sourcelens_distribution_image_ref lensnode "${1:-${SOURCELENS_DISTRIBUTION_TAG:-${SOURCELENS_VERSION}}}"
}

sourcelens_app_images_ready() {
	sourcelens_image_exists "$(sourcelens_backend_image_ref)" \
		&& sourcelens_image_exists "$(sourcelens_frontend_image_ref)" \
		&& sourcelens_image_exists "$(sourcelens_lensnode_image_ref)"
}

sourcelens_upstream_images_ready() {
	sourcelens_image_exists "$(sourcelens_upstream_image_ref backend)" \
		&& sourcelens_image_exists "$(sourcelens_upstream_image_ref frontend)" \
		&& sourcelens_image_exists "$(sourcelens_upstream_image_ref lensnode)"
}

sourcelens_tag_app_images_latest() {
	local component upstream_ref distribution_ref latest_ref
	for component in backend frontend lensnode; do
		upstream_ref="$(sourcelens_upstream_image_ref "${component}")"
		distribution_ref="$(sourcelens_distribution_image_ref "${component}")"
		latest_ref="$(sourcelens_distribution_image_ref "${component}" latest)"
		docker tag "${upstream_ref}" "${distribution_ref}"
		docker tag "${upstream_ref}" "${latest_ref}"
		sourcelens_log "Tagged ${upstream_ref} -> ${distribution_ref} (alias: ${latest_ref})"
	done
}

sourcelens_tag_lensnode_alias() {
	local lensnode_ref
	lensnode_ref="$(sourcelens_lensnode_image_ref)"
	if [[ "${lensnode_ref}" != "${SOURCELENS_LENSNODE_IMAGE}" ]]; then
		docker tag "${lensnode_ref}" "${SOURCELENS_LENSNODE_IMAGE}"
	fi
}

sourcelens_build_skippable() {
	[[ "$(sourcelens_read_built_commit)" == "$(sourcelens_current_build_stamp)" ]] \
		&& sourcelens_app_images_ready
}

# Export LensNode image for Gateway hfl-enroll.
# Optional source_archive: copy an existing release image tar instead of docker save.
sourcelens_publish_gateway_lensnode_bundle() {
	local force=${1:-0}
	local source_archive="${2:-}"
	local dest_dir="${HFL_GATEWAY_BOOTSTRAP_DIR:-${HFL_ROOT}/data/media/gateway-bootstrap}"
	local dest="${dest_dir}/lensnode-image-linux-amd64.tar.gz"
	local refs=()

	mkdir -p "${dest_dir}"
	command -v flock >/dev/null 2>&1 \
		|| sourcelens_die "flock is required for atomic LensNode bundle publishing"

	if [[ -n "${source_archive}" && -f "${source_archive}" ]]; then
		(
			local temporary="${dest}.tmp.$$"
			exec 9>"${dest}.lock"
			flock 9
			trap 'rm -f "${temporary}"' EXIT INT TERM
			# Release staging exposes the same LensNode archive at two public paths.
			# A hard link keeps both contracts without storing the 250+ MiB blob
			# twice; copying remains the safe fallback across filesystems.
			if ! ln "${source_archive}" "${temporary}" 2>/dev/null; then
				cp "${source_archive}" "${temporary}"
			fi
			gzip -t "${temporary}"
			[[ -n "$(sourcelens_gateway_lensnode_bundle_image_id "${temporary}")" ]] \
				|| sourcelens_die "source LensNode archive is missing a valid Docker image index"
			chmod 0644 "${temporary}"
			mv -f "${temporary}" "${dest}"
			trap - EXIT INT TERM
		)
		sourcelens_log "Published gateway LensNode bundle -> ${dest#${HFL_ROOT}/}"
		return 0
	fi

	for ref in \
		"$(sourcelens_lensnode_image_ref)" \
		"$(sourcelens_lensnode_image_ref latest)" \
		"${SOURCELENS_LENSNODE_IMAGE}"; do
		if sourcelens_image_exists "${ref}"; then
			refs+=("${ref}")
		fi
	done
	if ((${#refs[@]} == 0)); then
		sourcelens_log "No SourceLens LensNode image found; skipping gateway bundle export"
		return 0
	fi

	local primary_ref="${refs[0]}"
	local bundle_id="" current_id=""
	if [[ "${force}" -eq 0 && -f "${dest}" ]]; then
		current_id="$(sourcelens_lensnode_image_id "${primary_ref}")"
		bundle_id="$(sourcelens_gateway_lensnode_bundle_image_id "${dest}")"
		if [[ -n "${current_id}" && -n "${bundle_id}" && "${current_id}" == "${bundle_id}" ]] \
			&& sourcelens_lensnode_supports_insecure_tls "${primary_ref}"; then
			sourcelens_log "Gateway LensNode bundle up to date (${bundle_id}); skipping export"
			return 0
		fi
		if [[ -n "${current_id}" && -n "${bundle_id}" && "${current_id}" != "${bundle_id}" ]]; then
			sourcelens_log "Gateway LensNode bundle image ${bundle_id} differs from local ${current_id}; refreshing export"
		else
			sourcelens_log "Gateway LensNode bundle stale or missing HFL TLS patch; refreshing export"
		fi
	fi

	if ! sourcelens_lensnode_supports_insecure_tls "${primary_ref}"; then
		sourcelens_die "LensNode image ${primary_ref} lacks HFL TLS bypass (lensnode.tls); rebuild SourceLens app images first"
	fi

	sourcelens_log "Saving gateway LensNode bundle atomically -> ${dest#${HFL_ROOT}/}"
	(
		local temporary="${dest}.tmp.$$"
		exec 9>"${dest}.lock"
		flock 9
		trap 'rm -f "${temporary}"' EXIT INT TERM
		docker save "${refs[@]}" | gzip -c >"${temporary}"
		gzip -t "${temporary}"
		local exported_id
		exported_id="$(sourcelens_gateway_lensnode_bundle_image_id "${temporary}")"
		[[ -n "${exported_id}" && "${exported_id}" == "$(sourcelens_lensnode_image_id "${primary_ref}")" ]] \
			|| sourcelens_die "exported LensNode archive failed image identity validation"
		chmod 0644 "${temporary}"
		mv -f "${temporary}" "${dest}"
		trap - EXIT INT TERM
	)
	bundle_id="$(sourcelens_gateway_lensnode_bundle_image_id "${dest}")"
	sourcelens_log "Published gateway LensNode bundle ($(du -h "${dest}" | awk '{print $1}'), ${bundle_id:-unknown id})"
}

sourcelens_build_app_images() {
	local force=${1:-0}
	local no_cache=${2:-0}
	local requested_services="${SOURCELENS_BUILD_SERVICES:-backend-api frontend lensnode}"
	local full_build=1
	if [[ "${requested_services}" != "backend-api frontend lensnode" ]]; then
		full_build=0
		local service
		for service in ${requested_services}; do
			case "${service}" in
			backend-api | frontend | lensnode) ;;
			*) sourcelens_die "unsupported SourceLens build service: ${service}" 2 ;;
			esac
		done
	fi
	sourcelens_ensure_compose
	if [[ "${full_build}" -eq 1 && "${force}" -eq 0 && "${no_cache}" -eq 0 ]] && sourcelens_build_skippable; then
		sourcelens_log "SourceLens app images already built for source stamp $(sourcelens_read_built_commit); skipping compose build"
		sourcelens_tag_lensnode_alias
		return 0
	fi
	if [[ "${full_build}" -eq 1 && "${force}" -eq 0 && "${no_cache}" -eq 0 \
		&& "$(sourcelens_read_built_commit)" == "$(sourcelens_current_build_stamp)" ]] \
		&& sourcelens_upstream_images_ready; then
		sourcelens_log "SourceLens upstream images match the build stamp; applying normalized distribution tags"
		sourcelens_tag_app_images_latest
		sourcelens_tag_lensnode_alias
		return 0
	fi
	if [[ "${full_build}" -eq 1 && "${force}" -eq 0 && "${no_cache}" -eq 0 ]] && sourcelens_app_images_ready; then
		sourcelens_log "SourceLens app images present but source commit changed; rebuilding"
	fi

	local src="${SOURCELENS_SOURCE_CACHE}"
	local version="${SOURCELENS_VERSION}"
	local ubuntu_apt_mirror_url=""
	local debian_apt_mirror_url=""

	if [[ -n "${SOURCELENS_APT_MIRROR:-}" ]]; then
		ubuntu_apt_mirror_url="$(sourcelens_normalize_apt_mirror_url ubuntu "${SOURCELENS_APT_MIRROR}" "${SOURCELENS_DOCKER_PLATFORM}")"
		debian_apt_mirror_url="$(sourcelens_normalize_apt_mirror_url debian "${SOURCELENS_APT_MIRROR}" "${SOURCELENS_DOCKER_PLATFORM}")"
	fi
	if [[ -z "${debian_apt_mirror_url}" ]]; then
		debian_apt_mirror_url="https://mirrors.tuna.tsinghua.edu.cn/debian"
	fi

	sourcelens_restore_source_dockerfiles "${src}"
	sourcelens_restore_compose_file "${src}"
	sourcelens_patch_dockerfile_uv_network "${src}" "${SOURCELENS_UV_HTTP_TIMEOUT}" \
		"${SOURCELENS_UV_CONCURRENT_DOWNLOADS}"
	sourcelens_patch_dockerfile_pip_resilience "${src}" \
		"${SOURCELENS_PIP_RETRY_MAX}" "${SOURCELENS_PIP_RETRY_DELAY}"
	sourcelens_patch_frontend_dockerfile_npm_registry "${src}"
	sourcelens_patch_compose_lensnode_apt_mirror "${src}" "${debian_apt_mirror_url}"
	sourcelens_patch_compose_uv_network "${src}" "${SOURCELENS_UV_HTTP_TIMEOUT}" \
		"${SOURCELENS_UV_CONCURRENT_DOWNLOADS}"
	sourcelens_patch_compose_npm_registry "${src}" "${SOURCELENS_NPM_REGISTRY}"
	sourcelens_log "Building SourceLens Docker images (APP_VERSION=${version}, base images from docker.io like HFL)..."
	(
		cd "${src}"
		export APP_VERSION="${version}"
		export DOCKER_DEFAULT_PLATFORM="${SOURCELENS_DOCKER_PLATFORM}"
		sourcelens_log "Using SourceLens Docker platform: ${DOCKER_DEFAULT_PLATFORM}"
		if [[ -n "${ubuntu_apt_mirror_url}" ]]; then
			sourcelens_log "Using SourceLens Ubuntu apt mirror: ${ubuntu_apt_mirror_url}"
			export APT_MIRROR_URL="${ubuntu_apt_mirror_url}"
		else
			unset APT_MIRROR_URL
		fi
		export DEBIAN_APT_MIRROR_URL="${debian_apt_mirror_url}"
		sourcelens_log "Using SourceLens Debian apt mirror: ${DEBIAN_APT_MIRROR_URL}"
		export PIP_INDEX_URL="${SOURCELENS_PIP_INDEX_URL}"
		export PIP_TRUSTED_HOST="${SOURCELENS_PIP_TRUSTED_HOST}"
		export UV_HTTP_TIMEOUT="${SOURCELENS_UV_HTTP_TIMEOUT}"
		export UV_CONCURRENT_DOWNLOADS="${SOURCELENS_UV_CONCURRENT_DOWNLOADS}"
		export NPM_REGISTRY="${SOURCELENS_NPM_REGISTRY}"
		sourcelens_log "Using SourceLens pip index: ${PIP_INDEX_URL}"
		sourcelens_log "Using SourceLens pip resilience: BuildKit uv/pip cache + retry max=${SOURCELENS_PIP_RETRY_MAX} delay=${SOURCELENS_PIP_RETRY_DELAY}s"
		sourcelens_log "Using SourceLens uv network: timeout=${UV_HTTP_TIMEOUT}s concurrent=${UV_CONCURRENT_DOWNLOADS} (uv retries=default)"
		sourcelens_log "Using SourceLens npm registry: ${NPM_REGISTRY}"
		local -a build_args=(build)
		[[ "${no_cache}" -eq 1 ]] && build_args+=(--no-cache)
		# shellcheck disable=SC2206
		local -a services=(${requested_services})
		build_args+=("${services[@]}")
		DOCKER_BUILDKIT=1 "${SOURCELENS_COMPOSE[@]}" "${build_args[@]}"
	)
	if [[ "${full_build}" -eq 0 ]]; then
		sourcelens_log "Built requested SourceLens service(s): ${requested_services}"
		return 0
	fi
	sourcelens_tag_app_images_latest
	sourcelens_tag_lensnode_alias
	sourcelens_write_built_commit "$(sourcelens_current_build_stamp)"
}

sourcelens_ensure_nginx_image() {
	local force_pull=${1:-0}
	sourcelens_ensure_runtime_image "nginx:stable-alpine" "${force_pull}"
}

sourcelens_ensure_runtime_image() {
	local image=$1 force_pull=${2:-${SOURCELENS_FORCE_PULL}}
	sourcelens_log "Resolving runtime image ${image} (offline=${SOURCELENS_OFFLINE}, force_pull=${force_pull})"
	if ! hfl_docker_ensure_image "${image}" "${SOURCELENS_DOCKER_MIRROR}" \
		"${force_pull}" "${SOURCELENS_OFFLINE}" "${SOURCELENS_DOCKER_PLATFORM}" \
		"${SOURCELENS_DOCKER_PULL_TIMEOUT}" "${SOURCELENS_DOCKER_PULL_RETRIES}"; then
		sourcelens_die "unable to prepare ${image}: ${HFL_DOCKER_LAST_ERROR}"
	fi
	sourcelens_log "Runtime image ${image} ready (source=${HFL_DOCKER_IMAGE_SOURCE})"
}

sourcelens_ensure_runtime_images() {
	local force_pull=${1:-${SOURCELENS_FORCE_PULL}}
	local image source_ref target_ref
	for image in nginx:stable-alpine postgres:17 redis:alpine; do
		sourcelens_ensure_runtime_image "${image}" "${force_pull}"
	done
	for image in \
		"nginx:stable-alpine hyperfilelens-sourcelens-nginx:stable-alpine" \
		"postgres:17 hyperfilelens-postgres:17" \
		"redis:alpine hyperfilelens-redis:alpine"; do
		source_ref=${image%% *}
		target_ref=${image#* }
		docker tag "${source_ref}" "${target_ref}" \
			|| sourcelens_die "unable to tag runtime image ${source_ref} as ${target_ref}"
		sourcelens_log "Tagged runtime image ${source_ref} -> ${target_ref}"
	done
}

sourcelens_patch_env_runtime_defaults() {
	local path=$1
	local script="${SOURCELENS_INSTALLER_DIR}/sourcelens/patch-env-runtime.py"
	[[ -f "${script}" ]] || sourcelens_die "missing ${script}"
	python3 "${script}" "${path}"
	python3 - "${path}" \
		"${SOURCELENS_CONSOLE_BIND_ADDRESS}" \
		"${SOURCELENS_CONSOLE_PORT}" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
bind_address = sys.argv[2]
port = sys.argv[3]
text = path.read_text(encoding="utf-8")

for name, value in {
    "SOURCELENS_CONSOLE_BIND_ADDRESS": bind_address,
    "SOURCELENS_CONSOLE_PORT": port,
    "NGINX_HTTPS_PORT": port,
}.items():
    pattern = rf"^{re.escape(name)}=.*$"
    line = f"{name}={value}"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, line, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\n{line}\n"
path.write_text(text, encoding="utf-8")
PY
}

sourcelens_patch_runtime_nginx() {
	local path=$1
	python3 - "${path}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
sources = (
    "set $ui_upstream http://frontend:80;",
    "set $ui_upstream http://sourcelens-ui:80;",
)
target = "set $ui_upstream http://ui:80;"
if target not in text and not any(source in text for source in sources):
    raise SystemExit(f"SourceLens UI upstream declaration not found in {path}")
for source in sources:
    text = text.replace(source, target)
text = text.replace(
    "/etc/nginx/certs/nginx-selfsigned.crt",
    "/etc/nginx/certs/tls.crt",
)
text = text.replace(
    "/etc/nginx/certs/nginx-selfsigned.key",
    "/etc/nginx/certs/tls.key",
)
if "/etc/nginx/certs/tls.crt" not in text or "/etc/nginx/certs/tls.key" not in text:
    raise SystemExit(f"SourceLens TLS certificate declarations not found in {path}")
path.write_text(text, encoding="utf-8")
PY
}

sourcelens_write_runtime_compose() {
	local compose_path=$1
	local template="${SOURCELENS_INSTALLER_DIR}/sourcelens/docker-compose.template.yml"
	local backend_image frontend_image lensnode_image
	backend_image="$(sourcelens_backend_image_ref)"
	frontend_image="$(sourcelens_frontend_image_ref)"
	lensnode_image="$(sourcelens_lensnode_image_ref)"
	[[ -f "${template}" ]] || sourcelens_die "missing SourceLens Compose template: ${template}"

	python3 - "${template}" "${compose_path}" \
		"${backend_image}" "${frontend_image}" "${lensnode_image}" \
		"${SOURCELENS_CONSOLE_BIND_ADDRESS}" \
		"${SOURCELENS_CONSOLE_PORT}" \
		"${SOURCELENS_EMBED_LENSNODE}" <<'PY'
import pathlib
import re
import sys

template_path, compose_path, backend_image, frontend_image, lensnode_image, bind_address, https_port, embed_raw = sys.argv[1:9]
embed_lensnode = str(embed_raw).strip().lower() in {"1", "true", "yes", "on"}
text = pathlib.Path(template_path).read_text(encoding="utf-8")


def render_optional_block(value: str, name: str, enabled: bool) -> str:
    pattern = re.compile(
        rf"(?ms)^# HFL_{re.escape(name)}_BEGIN\n(.*?)^# HFL_{re.escape(name)}_END\n"
    )
    matches = pattern.findall(value)
    if len(matches) != 1:
        raise SystemExit(f"expected one {name} block in {template_path}, found {len(matches)}")
    return pattern.sub(lambda match: match.group(1) if enabled else "", value)


text = render_optional_block(text, "EMBED_BACKEND_ENV", embed_lensnode)
text = render_optional_block(text, "EMBED_LENSNODE_SERVICE", embed_lensnode)
replacements = {
    "__SOURCELENS_BACKEND_IMAGE__": backend_image,
    "__SOURCELENS_FRONTEND_IMAGE__": frontend_image,
    "__SOURCELENS_LENSNODE_IMAGE__": lensnode_image,
    "__SOURCELENS_CONSOLE_BIND_ADDRESS__": bind_address,
    "__SOURCELENS_CONSOLE_PORT__": https_port,
}
for token, value in replacements.items():
    text = text.replace(token, value)
if "__SOURCELENS_" in text or "HFL_EMBED_" in text:
    raise SystemExit(f"unresolved SourceLens Compose template marker in {template_path}")

destination = pathlib.Path(compose_path)
temporary = destination.with_suffix(destination.suffix + ".tmp")
temporary.write_text(text, encoding="utf-8")
temporary.replace(destination)
PY
}

sourcelens_ensure_dev_data_dirs() {
	mkdir -p \
		"${SOURCELENS_DATA_DIR}/postgresql/data" \
		"${SOURCELENS_DATA_DIR}/redis" \
		"${SOURCELENS_DATA_DIR}/logs/api" \
		"${SOURCELENS_DATA_DIR}/logs/worker" \
		"${SOURCELENS_DATA_DIR}/logs/scheduler" \
		"${SOURCELENS_DATA_DIR}/logs/nginx" \
		"${SOURCELENS_DATA_DIR}/logs/postgresql" \
		"${SOURCELENS_DATA_DIR}/logs/redis" \
		"${SOURCELENS_DATA_DIR}/storage" \
		"${SOURCELENS_DATA_DIR}/workspace" \
		"${SOURCELENS_DATA_DIR}/django/staticfiles"
}

sourcelens_prepare_dev_runtime_tree() {
	local src="${SOURCELENS_SOURCE_CACHE}"
	local dev_root="${SOURCELENS_DEV_DIR}"
	local nginx_config="${src}/docker/nginx/default.conf"
	[[ -f "${nginx_config}" ]] \
		|| sourcelens_die "missing SourceLens nginx config: ${nginx_config}"

	mkdir -p "${dev_root}/deploy/nginx" "${dev_root}/deploy/postgresql"
	cp "${nginx_config}" "${dev_root}/deploy/nginx/default.conf"
	sourcelens_patch_runtime_nginx "${dev_root}/deploy/nginx/default.conf"
	sourcelens_ensure_tls_certs "${HFL_ROOT}/deploy/nginx/certs"
	rm -rf "${dev_root}/deploy/nginx/certs"
	ln -s "${HFL_ROOT}/deploy/nginx/certs" "${dev_root}/deploy/nginx/certs"
	if [[ -d "${src}/docker/postgresql" ]]; then
		rsync -a "${src}/docker/postgresql/" "${dev_root}/deploy/postgresql/"
	fi

	sourcelens_ensure_dev_data_dirs
	mkdir -p "${dev_root}/data"
	for subdir in postgresql redis logs storage workspace django; do
		ln -sfn "${SOURCELENS_DATA_DIR}/${subdir}" "${dev_root}/data/${subdir}"
	done

	local env_file="${SOURCELENS_DEV_ENV_FILE}"
	local legacy_env_file="${dev_root}/.env"
	local env_sample="${src}/env.sample"
	[[ -f "${env_sample}" ]] || sourcelens_die "SourceLens env.sample not found"
	mkdir -p "$(dirname "${env_file}")"
	if [[ -f "${legacy_env_file}" && ! -L "${legacy_env_file}" && ! -f "${env_file}" ]]; then
		cp "${legacy_env_file}" "${env_file}"
		sourcelens_log "Migrated SourceLens dev config to ${env_file#${HFL_ROOT}/}"
	fi
	if [[ ! -f "${env_file}" ]]; then
		cp "${env_sample}" "${env_file}"
		sourcelens_patch_env_runtime_defaults "${env_file}"
		sourcelens_log "Created ${env_file#${HFL_ROOT}/}"
	else
		python3 - "${env_file}" "${env_sample}" <<'PY'
import pathlib
import re
import sys

env_path = pathlib.Path(sys.argv[1])
example_path = pathlib.Path(sys.argv[2])
text = env_path.read_text(encoding="utf-8")
existing = set(re.findall(r"^([A-Z0-9_]+)=", text, flags=re.M))
for line in example_path.read_text(encoding="utf-8").splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        continue
    key = line.split("=", 1)[0].strip()
    if key and key not in existing:
        text = text.rstrip() + f"\n{line}\n"
env_path.write_text(text, encoding="utf-8")
PY
	fi
	sourcelens_patch_env_runtime_defaults "${env_file}"
	if [[ -e "${legacy_env_file}" && ! -L "${legacy_env_file}" ]]; then
		rm -f "${legacy_env_file}"
	fi
	ln -sfn "${env_file}" "${dev_root}/.env"

	sourcelens_write_runtime_compose "${dev_root}/docker-compose.yml"
}

sourcelens_migrate_legacy_dev_project() {
	local id project working_dir config_files removed=0
	while IFS= read -r id; do
		[[ -n "${id}" ]] || continue
		project="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "${id}" 2>/dev/null || true)"
		working_dir="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "${id}" 2>/dev/null || true)"
		config_files="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "${id}" 2>/dev/null || true)"
		[[ "${project}" == "sourcelens" ]] || continue
		if [[ "${working_dir}" != "${SOURCELENS_DEV_DIR}" \
			&& ",${config_files}," != *",${SOURCELENS_DEV_DIR}/docker-compose.yml,"* ]]; then
			continue
		fi
		sourcelens_log "Migrating owned legacy SourceLens dev container ${id:0:12}"
		docker rm -f "${id}" >/dev/null
		removed=1
	done < <(docker ps -aq --no-trunc)
	if [[ "${removed}" == "1" ]]; then
		sourcelens_log "Legacy dev project migration completed; unrelated SourceLens projects were not touched"
	fi
}

sourcelens_dev_compose() {
	sourcelens_ensure_compose
	(
		cd "${SOURCELENS_DEV_DIR}"
		"${SOURCELENS_COMPOSE[@]}" --env-file "${SOURCELENS_DEV_ENV_FILE}" \
			-p "${SOURCELENS_COMPOSE_PROJECT}" -f docker-compose.yml "$@"
	)
}

sourcelens_ensure_database_initialized() {
	local check_cmd='cd /opt/backend && python manage.py migrate --check >/dev/null'
	local init_cmd='cd /opt/backend && python manage.py sourcelens_init --skip-collectstatic'
	local static_cmd='cd /opt/backend && mkdir -p core/staticfiles && python manage.py collectstatic --noinput'

	if ! sourcelens_dev_compose exec -T api sh -lc "${check_cmd}"; then
		sourcelens_log "Initializing SourceLens database (missing or pending migrations)"
		sourcelens_dev_compose exec -T api sh -lc "${init_cmd}"
	else
		sourcelens_log "SourceLens database migrations are current"
	fi

	sourcelens_log "Collecting SourceLens static assets"
	sourcelens_dev_compose exec -T api sh -lc "${static_cmd}"
}

sourcelens_configure_hfl_env() {
	local hfl_env="${HFL_ROOT}/.env"
	[[ -f "${hfl_env}" ]] || return 0
	python3 - "${hfl_env}" <<'PY'
import pathlib
import re
import sys

env_path = pathlib.Path(sys.argv[1])
text = env_path.read_text(encoding="utf-8")

def read_key(name: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(name)}=(.*)$", text, flags=re.M)
    if not match:
        return default
    return match.group(1).strip().strip('"').strip("'")

frontend = read_key("FRONTEND_URL", "https://127.0.0.1:11443").rstrip("/")
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
print(f"[sourcelens] configured {', '.join(updates.keys())} in {env_path}")
PY
}

sourcelens_wait_for_health() {
	local attempt
	for attempt in $(seq 1 60); do
		if sourcelens_dev_compose exec -T nginx \
			curl -fsS --connect-timeout 3 -m 5 \
			http://127.0.0.1/health >/dev/null 2>&1; then
			sourcelens_log "Health check OK (sourcelens-nginx-1:/health)"
			return 0
		fi
		sleep 5
	done
	sourcelens_die "SourceLens did not become healthy on its private network"
}

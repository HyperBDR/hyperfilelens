#!/usr/bin/env bash
# Build a HyperFileLens release install package (air-gap delivery).
# Run from repository root with Docker and Go; SourceLens builds also require Git and Docker Compose.
#
# Usage:
#   ./release/build.sh
#   ./release/build.sh --github-download-mirror https://ghfast.top --docker-download-mirror docker.m.daocloud.io --apt-mirror https://mirrors.tuna.tsinghua.edu.cn
set -euo pipefail
export COPYFILE_DISABLE=1
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${ROOT}/release"
RELEASE_BUILD_DIR="${ROOT}/build/release"
STAGING_BASE="${RELEASE_BUILD_DIR}/staging"
DIST_DIR="${RELEASE_BUILD_DIR}/dist"
# shellcheck source=../tools/lib/safe-path.sh
source "${ROOT}/tools/lib/safe-path.sh"
# shellcheck source=../tools/lib/version.sh
source "${ROOT}/tools/lib/version.sh"
# shellcheck source=../tools/lib/logging.sh
source "${ROOT}/tools/lib/logging.sh"
# shellcheck source=../tools/lib/env-file.sh
source "${ROOT}/tools/lib/env-file.sh"
# shellcheck source=../tools/kopia/common.sh
source "${ROOT}/tools/kopia/common.sh"

MIRROR_GITHUB_DOWNLOAD=""
MIRROR_GITHUB_TOKEN=""
MIRROR_DOCKER_DOWNLOAD=""
MIRROR_DOCKER_APT=""
MIRROR_APT=""
FORCE_PULL=0
NO_CACHE=0
SOURCELENS_FORCE_BUILD="${SOURCELENS_FORCE_BUILD:-0}"
BUILD_SOURCELENS="${BUILD_SOURCELENS:-}"
SOURCELENS_GIT_REF="${SOURCELENS_GIT_REF:-}"
LOG_FILE="${HFL_LOG_FILE:-}"
VERBOSE="${HFL_LOG_VERBOSE:-0}"
PRINT_CONFIG=0
OPT_VERSION=""
SOURCELENS_BUILD_ENV="${ROOT}/tools/sourcelens/defaults.env"

log() { hfl_log_info "$@"; }
die() { hfl_die "$1" "${2:-1}"; }

tar_create_gz() {
	local out=$1
	local base_dir=$2
	local entry=$3

	COPYFILE_DISABLE=1 tar -C "${base_dir}" -czf "${out}" "${entry}"
}

normalize_release_permissions() {
	local pkg_root=$1
	find "${pkg_root}" -type d -exec chmod 755 {} +
	find "${pkg_root}" -type f -exec chmod 644 {} +
	chmod 755 "${pkg_root}/install.sh" "${pkg_root}/apply-runtime-config.py"
	if [[ -d "${pkg_root}/sourcelens" ]]; then
		chmod 755 "${pkg_root}/sourcelens/install.sh" \
			"${pkg_root}/sourcelens/patch-env-runtime.py"
		find "${pkg_root}/sourcelens/deploy/postgresql/initdb.d" \
			-type f -name '*.sh' -exec chmod 755 {} +
	fi
	find "${pkg_root}/payload/media" -type f -name '*.sh' -exec chmod 755 {} +
	if [[ -d "${pkg_root}/payload/media/enroll-bootstrap" ]]; then
		find "${pkg_root}/payload/media/enroll-bootstrap" -type f -exec chmod 755 {} +
	fi
	if [[ -f "${pkg_root}/deploy/nginx/certs/tls.key" ]]; then
		chmod 600 "${pkg_root}/deploy/nginx/certs/tls.key"
	fi
}

validate_release_security() {
	local pkg_root=$1 bad=""
	local cert_dir="${pkg_root}/deploy/nginx/certs"
	local allowed_key="${cert_dir}/tls.key"
	bad="$(find "${pkg_root}" \
		\( -name '.env' -o -name '*.key' -o -name '*.pem' -o -name '*.p12' \
		-o -name '*.pfx' -o -name 'id_rsa' \) ! -path "${allowed_key}" -print -quit)"
	[[ -z "${bad}" ]] || die "release package contains forbidden secret material: ${bad#${pkg_root}/}"
	while IFS= read -r candidate; do
		[[ "${candidate}" == "${allowed_key}" ]] && continue
		bad="${candidate}"
		break
	done < <(
		find "${pkg_root}" -type f -size -2M -exec \
			grep -IlE -- '-----BEGIN ([A-Z0-9]+ )?PRIVATE KEY-----' {} + 2>/dev/null || true
	)
	[[ -z "${bad}" ]] \
		|| die "release package contains an unapproved private key: ${bad#${pkg_root}/}"
	for required in tls.crt tls.key root-ca.crt SHA256SUMS README.md; do
		[[ -s "${cert_dir}/${required}" ]] \
			|| die "release package is missing deploy/nginx/certs/${required}"
	done
	(
		cd "${cert_dir}"
		sha256sum --strict --check SHA256SUMS >/dev/null
	) || die "release default TLS checksum validation failed"
	[[ "$(stat -c '%a' "${allowed_key}")" == "600" ]] \
		|| die "release default TLS private key must have mode 0600"
	openssl verify -CAfile "${cert_dir}/root-ca.crt" "${cert_dir}/tls.crt" >/dev/null 2>&1 \
		|| die "release default TLS certificate chain validation failed"
	local cert_pub key_pub
	cert_pub="$(openssl x509 -in "${cert_dir}/tls.crt" -pubkey -noout | sha256sum | cut -d' ' -f1)"
	key_pub="$(openssl pkey -in "${allowed_key}" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1)"
	[[ "${cert_pub}" == "${key_pub}" ]] \
		|| die "release default TLS certificate and key do not match"
	for public_dir in \
		"${pkg_root}/payload/media/agent-releases" \
		"${pkg_root}/payload/media/enroll-bootstrap" \
		"${pkg_root}/payload/media/gateway-bootstrap"; do
		[[ -d "${public_dir}" ]] || continue
		bad="$(find "${public_dir}" -type f ! -perm -004 -print -quit)"
		[[ -z "${bad}" ]] \
			|| die "release download is not readable by the nginx worker: ${bad#${pkg_root}/}"
	done
	log "Release secret and download permission validation passed"
}

stage_default_tls_bundle() {
	local pkg_root=$1
	local source_dir="${ROOT}/deploy/nginx/certs"
	local target_dir="${pkg_root}/deploy/nginx/certs"
	mkdir -p "${target_dir}"
	rsync -a --delete "${source_dir}/" "${target_dir}/"
}

require_value() {
	if [[ $# -lt 2 || -z "${2:-}" || "${2:0:1}" == "-" ]]; then
		die "${1} requires a value" 2
	fi
}

load_repo_env_defaults() {
	hfl_env_select_repo_file "${ROOT}"
	local key
	for key in \
		GITHUB_DOWNLOAD_MIRROR GITHUB_TOKEN DOCKER_DOWNLOAD_MIRROR \
		DOCKER_APT_MIRROR APT_MIRROR PIP_INDEX_URL PIP_TRUSTED_HOST \
		PIP_TIMEOUT NPM_REGISTRY GOPROXY GOSUMDB BUILD_SOURCELENS \
		DOCKER_PULL_TIMEOUT_SECONDS \
		KOPIA_ARTIFACT_MODE KOPIA_GIT_URL KOPIA_GIT_REF \
		SOURCELENS_GIT_REF SOURCELENS_GIT_URL SENTRY_ENABLED SENTRY_DSN \
		SENTRY_ENVIRONMENT SENTRY_RELEASE SENTRY_TRACES_SAMPLE_RATE \
		SENTRY_SEND_DEFAULT_PII VITE_SHOW_EULA; do
		hfl_env_load_default "${key}"
	done
}

apply_mirror_env_defaults() {
	MIRROR_GITHUB_DOWNLOAD="${MIRROR_GITHUB_DOWNLOAD:-${GITHUB_DOWNLOAD_MIRROR:-${BUILD_GITHUB_DOWNLOAD_MIRROR:-}}}"
	MIRROR_GITHUB_TOKEN="${MIRROR_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
	MIRROR_DOCKER_DOWNLOAD="${MIRROR_DOCKER_DOWNLOAD:-${DOCKER_DOWNLOAD_MIRROR:-${BUILD_DOCKER_DOWNLOAD_MIRROR:-}}}"
	MIRROR_DOCKER_APT="${MIRROR_DOCKER_APT:-${DOCKER_APT_MIRROR:-${BUILD_DOCKER_APT_MIRROR:-}}}"
	MIRROR_APT="${MIRROR_APT:-${APT_MIRROR:-${BUILD_APT_MIRROR:-}}}"
}

apply_go_proxy_env_defaults() {
	export GOPROXY="${GOPROXY:-${BUILD_GOPROXY:-https://proxy.golang.org,direct}}"
	export GOSUMDB="${GOSUMDB:-${BUILD_GOSUMDB:-sum.golang.org}}"
}

validate_docker_pull_timeout() {
	DOCKER_PULL_TIMEOUT_SECONDS="${DOCKER_PULL_TIMEOUT_SECONDS:-180}"
	[[ "${DOCKER_PULL_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
		|| die "DOCKER_PULL_TIMEOUT_SECONDS must be a positive integer" 2
	export DOCKER_PULL_TIMEOUT_SECONDS
}

export_build_mirror_env() {
	apply_mirror_env_defaults
	export APT_MIRROR="${MIRROR_APT:-${APT_MIRROR:-${BUILD_APT_MIRROR:-}}}"
	export PIP_INDEX_URL="${PIP_INDEX_URL:-${BUILD_PIP_INDEX_URL:-}}"
	export PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-${BUILD_PIP_TRUSTED_HOST:-}}"
	export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-${BUILD_UV_HTTP_TIMEOUT:-120}}"
	export UV_CONCURRENT_DOWNLOADS="${UV_CONCURRENT_DOWNLOADS:-${BUILD_UV_CONCURRENT_DOWNLOADS:-2}}"
	export NPM_REGISTRY="${NPM_REGISTRY:-${BUILD_NPM_REGISTRY:-}}"
}

mirror_args() {
	local args=()
	[[ -n "${MIRROR_GITHUB_DOWNLOAD}" ]] && args+=(--github-download-mirror "${MIRROR_GITHUB_DOWNLOAD}")
	[[ -n "${MIRROR_GITHUB_TOKEN}" ]] && args+=(--github-token "${MIRROR_GITHUB_TOKEN}")
	[[ -n "${MIRROR_DOCKER_DOWNLOAD}" ]] && args+=(--docker-download-mirror "${MIRROR_DOCKER_DOWNLOAD}")
	[[ -n "${MIRROR_APT}" ]] && args+=(--apt-mirror "${MIRROR_APT}")
	((${#args[@]})) && printf '%s\0' "${args[@]}"
}

validate_ubuntu2404_arch() {
	case "${UBUNTU2404_ARCH}" in
	amd64 | arm64 | all) ;;
	*)
		die "invalid --ubuntu2404-arch ${UBUNTU2404_ARCH} (use amd64, arm64, or all)" 2
		;;
	esac
}

apply_ubuntu2404_arch_default() {
	UBUNTU2404_ARCH="${UBUNTU2404_ARCH:-amd64}"
	validate_ubuntu2404_arch
}

usage() {
	cat <<'USAGE'
Usage: release/build.sh [options]

Build hyperfilelens-<version>-<commit7>.tar.gz into build/release/dist/

Version:
  --version VERSION                  Local untagged build version (default: 0.1.0)
                                     A matching exact Git tag is authoritative when present.

  - Full agent bundle (all platforms)
  - Host Docker CE debs for Ubuntu 20.04/24.04 amd64 (offline install)
  - Control-plane Docker images + postgres/redis
  - Image-only runtime package: images, payload/media, compose, and deploy config

Mirror options (Kopia fetch + Agent publishing + runtime image pull; env fallback):
  --github-download-mirror URL     GitHub download mirror (env: GITHUB_DOWNLOAD_MIRROR)
  --github-token TOKEN             GitHub token for API/release fetch and private SourceLens clone (env: GITHUB_TOKEN)
  --docker-download-mirror URL     Docker Hub mirror for ubuntu:24.04, postgres, redis (env: DOCKER_DOWNLOAD_MIRROR)
  --docker-pull-timeout SECONDS    Timeout for each Docker pull attempt (env: DOCKER_PULL_TIMEOUT_SECONDS)
  --docker-apt-mirror URL          Docker CE apt repo base URL (env: DOCKER_APT_MIRROR / BUILD_DOCKER_APT_MIRROR)
  --apt-mirror URL                 Ubuntu apt mirror for NAS container (env: APT_MIRROR)
  --ubuntu2404-arch ARCH           NAS deb arch for agent bundle: amd64 | arm64 | all (default: amd64)
  --go-proxy URL                   Go module proxy (env: GOPROXY)
  --go-sumdb VALUE                 Go checksum database (env: GOSUMDB)
  --pip-index-url URL              Python package index (env: PIP_INDEX_URL)
  --pip-trusted-host HOST          Trusted pip host (env: PIP_TRUSTED_HOST)
  --npm-registry URL               npm registry (env: NPM_REGISTRY)

Kopia artifacts (tools/kopia/defaults.env; default: build patched source):
  --kopia-mode MODE               build or download
  --kopia-git-url URL             Kopia source repository URL
  --kopia-ref REF                 Kopia release ref in vX.Y.Z form

  --pull                           Re-check registry and pull runtime images (default: use local if present)
  --no-cache                       Rebuild HFL and SourceLens Docker layers without BuildKit cache

SourceLens bundle (tools/sourcelens/defaults.env; default: enabled):
  --no-sourcelens                  Skip SourceLens clone/build/bundle
  --sourcelens-ref REF             SourceLens release tag in vX.Y.Z form
  --sourcelens-git-url URL         Override SourceLens repository URL (env: SOURCELENS_GIT_URL)
  --force-build                    Rebuild SourceLens images even when the build stamp matches

Output options:
  --log-file FILE                  Append runtime logs to FILE
  --verbose                        Enable debug logs
  --print-config                   Print effective non-secret configuration and exit
  -h, --help                       Show this help

Examples:
  ./release/build.sh
  ./release/build.sh --ubuntu2404-arch amd64
  ./release/build.sh --github-download-mirror https://ghfast.top --docker-download-mirror docker.m.daocloud.io --apt-mirror https://mirrors.tuna.tsinghua.edu.cn
USAGE
}

print_config() {
	local resolved_version sourcelens_version
	resolved_version="$(resolve_release_version)" || return $?
	[[ "${SOURCELENS_GIT_REF}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]] \
		|| die "invalid SourceLens release ref: ${SOURCELENS_GIT_REF} (expected vX.Y.Z)" 2
	sourcelens_version="${BASH_REMATCH[1]}"
	apply_mirror_env_defaults
	apply_go_proxy_env_defaults
	validate_docker_pull_timeout
	apply_ubuntu2404_arch_default
	export_build_mirror_env
	cat <<EOF
release_dir=${DIST_DIR}
staging_dir=${STAGING_BASE}
hfl_version=${resolved_version}
agent_version=${resolved_version}
kopia_mode=${KOPIA_ARTIFACT_MODE}
kopia_git_url=${KOPIA_GIT_URL}
kopia_ref=${KOPIA_GIT_REF}
kopia_version=${KOPIA_VERSION}
with_sourcelens=${BUILD_SOURCELENS:-1}
sourcelens_ref=${SOURCELENS_GIT_REF}
sourcelens_version=${sourcelens_version}
sourcelens_git_url=${SOURCELENS_GIT_URL:-<default>}
sourcelens_upstream_image_prefix=${SOURCELENS_UPSTREAM_IMAGE_PREFIX}
sourcelens_image_registry=${SOURCELENS_IMAGE_REGISTRY:-<local>}
ubuntu2404_arch=${UBUNTU2404_ARCH}
force_pull=${FORCE_PULL}
no_cache=${NO_CACHE}
force_sourcelens_build=${SOURCELENS_FORCE_BUILD}
github_download_mirror=${MIRROR_GITHUB_DOWNLOAD:-<official>}
github_token=$(hfl_redact "${MIRROR_GITHUB_TOKEN}")
docker_download_mirror=${MIRROR_DOCKER_DOWNLOAD:-<official>}
docker_pull_timeout_seconds=${DOCKER_PULL_TIMEOUT_SECONDS:-180}
docker_apt_mirror=${MIRROR_DOCKER_APT:-https://download.docker.com/linux/ubuntu}
apt_mirror=${MIRROR_APT:-<official>}
go_proxy=${GOPROXY}
go_sumdb=${GOSUMDB}
pip_index_url=${PIP_INDEX_URL:-<official>}
pip_trusted_host=${PIP_TRUSTED_HOST:-<unset>}
npm_registry=${NPM_REGISTRY:-<official>}
log_file=${LOG_FILE:-<none>}
verbose=${VERBOSE}
EOF
}

load_sourcelens_build_config() {
	if [[ -f "${SOURCELENS_BUILD_ENV}" ]]; then
		# shellcheck disable=SC1090
		source "${SOURCELENS_BUILD_ENV}"
	fi
	if [[ -n "${BUILD_SOURCELENS}" ]]; then
		export BUILD_SOURCELENS
	elif [[ -z "${BUILD_SOURCELENS:-}" ]]; then
		export BUILD_SOURCELENS=1
	fi
}

parse_common_option() {
	case "$1" in
	--github-download-mirror)
		require_value "$1" "${2:-}"
		MIRROR_GITHUB_DOWNLOAD="$2"
		return 0
		;;
	--github-token)
		require_value "$1" "${2:-}"
		MIRROR_GITHUB_TOKEN="$2"
		return 0
		;;
	--docker-download-mirror)
		require_value "$1" "${2:-}"
		MIRROR_DOCKER_DOWNLOAD="$2"
		return 0
		;;
	--docker-pull-timeout)
		require_value "$1" "${2:-}"
		[[ "$2" =~ ^[1-9][0-9]*$ ]] || die "$1 requires a positive integer" 2
		export DOCKER_PULL_TIMEOUT_SECONDS="$2"
		return 0
		;;
	--docker-apt-mirror)
		require_value "$1" "${2:-}"
		MIRROR_DOCKER_APT="$2"
		return 0
		;;
	--apt-mirror)
		require_value "$1" "${2:-}"
		MIRROR_APT="$2"
		return 0
		;;
	--ubuntu2404-arch)
		require_value "$1" "${2:-}"
		UBUNTU2404_ARCH="$2"
		return 0
		;;
	--go-proxy)
		require_value "$1" "${2:-}"
		export GOPROXY="$2"
		return 0
		;;
	--go-sumdb)
		require_value "$1" "${2:-}"
		export GOSUMDB="$2"
		return 0
		;;
	--pip-index-url)
		require_value "$1" "${2:-}"
		export PIP_INDEX_URL="$2"
		return 0
		;;
	--pip-trusted-host)
		require_value "$1" "${2:-}"
		export PIP_TRUSTED_HOST="$2"
		return 0
		;;
	--npm-registry)
		require_value "$1" "${2:-}"
		export NPM_REGISTRY="$2"
		return 0
		;;
	esac
	return 1
}

parse_args() {
	load_repo_env_defaults
	load_sourcelens_build_config
	kopia_load_config
	while [[ $# -gt 0 ]]; do
		case "$1" in
		-h | --help)
			usage
			exit 0
			;;
		--version)
			require_value "$1" "${2:-}"
			OPT_VERSION="${2#v}"
			export RELEASE_VERSION="${OPT_VERSION}"
			shift 2
			;;
		--kopia-mode)
			require_value "$1" "${2:-}"
			export KOPIA_ARTIFACT_MODE="$2"
			case "${KOPIA_ARTIFACT_MODE}" in build | download) ;; *) die "invalid Kopia mode: ${KOPIA_ARTIFACT_MODE}" 2 ;; esac
			shift 2
			;;
		--kopia-git-url)
			require_value "$1" "${2:-}"
			export KOPIA_GIT_URL="$2"
			shift 2
			;;
		--kopia-ref)
			require_value "$1" "${2:-}"
			export KOPIA_GIT_REF="$2"
			[[ "${KOPIA_GIT_REF}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]] || die "invalid Kopia ref: ${KOPIA_GIT_REF}" 2
			KOPIA_VERSION="${BASH_REMATCH[1]}"
			shift 2
			;;
		--no-sourcelens)
			export BUILD_SOURCELENS=0
			shift
			;;
		--sourcelens-ref)
			require_value "$1" "${2:-}"
			export SOURCELENS_GIT_REF="$2"
			shift 2
			;;
		--sourcelens-git-url)
			require_value "$1" "${2:-}"
			export SOURCELENS_GIT_URL="$2"
			shift 2
			;;
		--print-config)
			PRINT_CONFIG=1
			shift
			;;
		--verbose)
			VERBOSE=1
			shift
			;;
		--log-file)
			require_value "$1" "${2:-}"
			LOG_FILE="$2"
			shift 2
			;;
		--github-download-mirror | --github-token | --docker-download-mirror | --docker-pull-timeout | --docker-apt-mirror | --apt-mirror | --ubuntu2404-arch | --go-proxy | --go-sumdb | --pip-index-url | --pip-trusted-host | --npm-registry)
			parse_common_option "$@" || die "failed to parse option: $1"
			shift 2
			;;
		--pull)
			FORCE_PULL=1
			shift
			;;
		--no-cache)
			NO_CACHE=1
			shift
			;;
		--force-build)
			SOURCELENS_FORCE_BUILD=1
			shift
			;;
		*)
			die "unknown argument: $1 (try --help)" 2
			;;
		esac
	done
}

prepare_kopia_artifacts() {
	local args=(
		--kopia-mode "${KOPIA_ARTIFACT_MODE}"
		--kopia-git-url "${KOPIA_GIT_URL}"
		--kopia-ref "${KOPIA_GIT_REF}"
	)
	if [[ -n "${MIRROR_GITHUB_DOWNLOAD}" ]]; then
		args+=(--github-download-mirror "${MIRROR_GITHUB_DOWNLOAD}")
	fi
	if [[ -n "${MIRROR_GITHUB_TOKEN}" ]]; then
		args+=(--github-token "${MIRROR_GITHUB_TOKEN}")
	fi
	log "Preparing unified Kopia artifact matrix"
	"${ROOT}/release/build-kopia.sh" "${args[@]}"
}

fetch_host_docker_debs() {
	local args=()
	[[ -n "${MIRROR_APT}" ]] && args+=(--apt-mirror "${MIRROR_APT}")
	[[ -n "${MIRROR_DOCKER_APT}" ]] && args+=(--docker-apt-mirror "${MIRROR_DOCKER_APT}")
	local ubuntu_release
	for ubuntu_release in 20.04 24.04; do
		log "Fetching host Docker CE debs (ubuntu ${ubuntu_release} amd64)"
		"${ROOT}/tools/dependencies/fetch-docker-ce-debs.sh" \
			--ubuntu-release "${ubuntu_release}" "${args[@]}"
	done
}

stage_host_docker_bundles() {
	local pkg_root=$1 ubuntu_release release_id source_dir destination
	local gateway_dir="${pkg_root}/payload/media/gateway-bootstrap"
	mkdir -p "${gateway_dir}"
	for ubuntu_release in 20.04 24.04; do
		case "${ubuntu_release}" in
		20.04) release_id=2004 ;;
		24.04) release_id=2404 ;;
		esac
		source_dir="${ROOT}/build/dependencies/docker/ubuntu-${ubuntu_release}/amd64"
		destination="${gateway_dir}/docker-debs-ubuntu${release_id}-amd64.tar.gz"
		[[ -d "${source_dir}" ]] || die "missing Docker deb cache ${source_dir}"
		tar -C "${source_dir}" -czf "${destination}" .
	done
}

publish_agent() {
	local pkg_root=$1
	local args=(
		--bundle all
		--ubuntu2404-arch "${UBUNTU2404_ARCH}"
		--releases-dir "${pkg_root}/payload/media/agent-releases"
	)
	args+=(--commit "${RELEASE_COMMIT}")
	args+=(--version "${HFL_VERSION}")
	args+=(--kopia-mode "${KOPIA_ARTIFACT_MODE}")
	args+=(--kopia-git-url "${KOPIA_GIT_URL}")
	args+=(--kopia-ref "${KOPIA_GIT_REF}")
	[[ "${FORCE_PULL}" -eq 1 ]] && args+=(--pull)
	[[ -n "${GOPROXY:-}" ]] && args+=(--go-proxy "${GOPROXY}")
	[[ -n "${GOSUMDB:-}" ]] && args+=(--go-sumdb "${GOSUMDB}")
	local mirror
	while IFS= read -r -d '' mirror; do
		args+=("${mirror}")
	done < <(mirror_args || true)
	log "Publishing Agent packages (full bundle, ubuntu2404-arch=${UBUNTU2404_ARCH})"
	"${ROOT}/tools/agent/publish.sh" "${args[@]}"
}

build_sourcelens_bundle() {
	local pkg_root=$1
	local images_dir=$2
	local args=(--pkg-root "${pkg_root}" --images-dir "${images_dir}")
	[[ "${FORCE_PULL}" -eq 1 ]] && args+=(--pull)
	[[ "${NO_CACHE}" -eq 1 ]] && args+=(--no-cache)
	[[ "${SOURCELENS_FORCE_BUILD}" -eq 1 ]] && args+=(--force-build)
	[[ -n "${SOURCELENS_GIT_REF:-}" ]] && args+=(--sourcelens-ref "${SOURCELENS_GIT_REF}")
	if [[ -n "${SOURCELENS_GIT_URL:-}" ]]; then
		args+=(--sourcelens-git-url "${SOURCELENS_GIT_URL}")
	fi
	APT_MIRROR="${MIRROR_APT:-}" \
		SOURCELENS_HFL_VERSION="${HFL_VERSION}" \
		GITHUB_TOKEN="${MIRROR_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}" \
		PIP_INDEX_URL="${PIP_INDEX_URL:-${BUILD_PIP_INDEX_URL:-}}" \
		PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-${BUILD_PIP_TRUSTED_HOST:-}}" \
		BUILD_SOURCELENS="${BUILD_SOURCELENS:-1}" \
		"${RELEASE_DIR}/build-sourcelens.sh" "${args[@]}"
}

read_version() {
	resolve_release_version
}

git_commit_short() {
	if command -v git >/dev/null 2>&1 && git -C "${ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo "unknown"
	else
		echo "unknown"
	fi
}

preflight() {
	command -v docker >/dev/null 2>&1 || die "docker not found" 2
	docker info >/dev/null 2>&1 || die "docker daemon not reachable"
	command -v python3 >/dev/null 2>&1 || die "python3 not found" 2
	command -v rsync >/dev/null 2>&1 || die "rsync not found" 2
	command -v sha256sum >/dev/null 2>&1 || die "sha256sum not found" 2
	command -v tar >/dev/null 2>&1 || die "tar not found" 2
	command -v gzip >/dev/null 2>&1 || die "gzip not found" 2
	load_sourcelens_build_config
	if [[ "${BUILD_SOURCELENS}" == "1" ]]; then
		command -v git >/dev/null 2>&1 || die "git not found (required for SourceLens bundle)" 2
		if ! docker compose version >/dev/null 2>&1 \
			&& ! command -v docker-compose >/dev/null 2>&1; then
			die "Docker Compose not found (required for SourceLens bundle)" 2
		fi
	fi
}

build_control_plane_images() {
	[[ -n "${HFL_VERSION:-}" ]] || die "HFL_VERSION is not resolved" 2
	local -a common_args=(
		--platform linux/amd64
		--network host
	)
	if [[ "${FORCE_PULL}" -eq 1 ]]; then
		common_args+=(--pull)
	fi
	if [[ "${NO_CACHE}" -eq 1 ]]; then
		common_args+=(--no-cache)
	fi

	log "Building hyperfilelens-backend:${HFL_VERSION} (alias: latest)"
	docker build "${common_args[@]}" \
		-f "${ROOT}/deploy/docker/backend.Dockerfile" \
		-t "hyperfilelens-backend:${HFL_VERSION}" \
		-t hyperfilelens-backend:latest \
		--build-arg "APT_MIRROR=${APT_MIRROR:-}" \
		--build-arg "PIP_INDEX_URL=${PIP_INDEX_URL:-}" \
		--build-arg "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-}" \
		--build-arg "PIP_TIMEOUT=${PIP_TIMEOUT:-600}" \
		--build-arg "KOPIA_BINARY=${KOPIA_BINARY:-build/kopia/dist/linux/amd64/kopia}" \
		"${ROOT}"

	log "Building hyperfilelens-frontend:${HFL_VERSION} (alias: latest)"
	docker build "${common_args[@]}" \
		-f "${ROOT}/deploy/docker/frontend.Dockerfile" \
		-t "hyperfilelens-frontend:${HFL_VERSION}" \
		-t hyperfilelens-frontend:latest \
		--build-arg "NPM_REGISTRY=${NPM_REGISTRY:-}" \
		--build-arg "SENTRY_ENABLED=${SENTRY_ENABLED:-false}" \
		--build-arg "SENTRY_DSN=${SENTRY_DSN:-}" \
		--build-arg "SENTRY_ENVIRONMENT=${SENTRY_ENVIRONMENT:-production}" \
		--build-arg "SENTRY_RELEASE=${SENTRY_RELEASE:-}" \
		--build-arg "SENTRY_TRACES_SAMPLE_RATE=${SENTRY_TRACES_SAMPLE_RATE:-0}" \
		--build-arg "SENTRY_SEND_DEFAULT_PII=${SENTRY_SEND_DEFAULT_PII:-false}" \
		--build-arg "VITE_SHOW_EULA=${VITE_SHOW_EULA:-false}" \
		"${ROOT}"
}

tree_sha256() {
	local dir=$1
	(
		export LC_ALL=C
		cd "${dir}"
		find . -type f ! -path './__pycache__/*' ! -name '*.pyc' -print0 \
			| sort -z \
			| xargs -0 sha256sum \
			| sha256sum \
			| awk '{print $1}'
	)
}

normalize_docker_mirror_host() {
	local mirror="${1:-}"
	mirror="${mirror#https://}"
	mirror="${mirror#http://}"
	mirror="${mirror%/}"
	printf '%s' "${mirror}"
}

docker_mirror_image_ref() {
	local image=$1
	local mirror_host=$2
	if [[ -z "${mirror_host}" ]]; then
		printf '%s' "${image}"
		return 0
	fi
	if [[ "${image}" == */* ]]; then
		printf '%s/%s' "${mirror_host}" "${image}"
	else
		printf '%s/library/%s' "${mirror_host}" "${image}"
	fi
}

image_exists_locally() {
	docker image inspect "$1" >/dev/null 2>&1
}

pull_image() {
	local image=$1
	local mirror_host mirrored

	if [[ "${FORCE_PULL}" -eq 0 ]] && image_exists_locally "${image}"; then
		log "Using local ${image} (skip pull; pass --pull to refresh from registry)"
		return 0
	fi

	mirror_host="$(normalize_docker_mirror_host "${MIRROR_DOCKER_DOWNLOAD}")"
	if [[ -n "${mirror_host}" ]]; then
		mirrored="$(docker_mirror_image_ref "${image}" "${mirror_host}")"
		if [[ "${FORCE_PULL}" -eq 0 ]] && image_exists_locally "${mirrored}"; then
			log "Using local ${mirrored}, tagging as ${image}"
			docker tag "${mirrored}" "${image}"
			return 0
		fi
		log "Pulling ${mirrored} via mirror ${mirror_host}..."
		if docker pull --help 2>&1 | grep -q -- '--progress'; then
			if docker pull --progress=plain "${mirrored}"; then
				docker tag "${mirrored}" "${image}"
				return 0
			fi
		elif docker pull "${mirrored}"; then
			docker tag "${mirrored}" "${image}"
			return 0
		fi
		log "Mirror pull failed, trying docker.io ${image}..."
	fi

	log "Pulling ${image} from docker.io..."
	if docker pull --help 2>&1 | grep -q -- '--progress'; then
		docker pull --progress=plain "${image}"
	else
		docker pull "${image}"
	fi
}

log_image_digest() {
	local image=$1
	local digest
	digest="$(image_digest "${image}")"
	log "  ${image} → ${digest}"
	printf '%s' "${digest}"
}

image_digest() {
	local image=$1
	local digest
	digest="$(docker image inspect "${image}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
	if [[ -z "${digest}" ]]; then
		digest="$(docker image inspect "${image}" --format '{{.Id}}' 2>/dev/null || true)"
	fi
	[[ -n "${digest}" ]] || digest="${image}"
	printf '%s' "${digest}"
}

save_image_archive() {
	local archive=$1
	shift
	local part="${archive}.part"
	rm -f "${part}"
	docker save "$@" | gzip -c >"${part}"
	gzip -t "${part}"
	mv -f "${part}" "${archive}"
}

save_images() {
	local images_dir=$1
	local archive
	mkdir -p "${images_dir}"

	log "Saving hyperfilelens backend + frontend images..."
	archive="${images_dir}/00-hyperfilelens.tar.gz"
	save_image_archive "${archive}" \
		"hyperfilelens-backend:${HFL_VERSION}" hyperfilelens-backend:latest \
		"hyperfilelens-frontend:${HFL_VERSION}" hyperfilelens-frontend:latest
	log "  wrote $(du -h "${archive}" | awk '{print $1}') ${archive##*/}"

	log "Saving hyperfilelens-postgres:17..."
	archive="${images_dir}/01-postgres-17.tar.gz"
	docker tag postgres:17 hyperfilelens-postgres:17
	save_image_archive "${archive}" hyperfilelens-postgres:17
	log "  wrote $(du -h "${archive}" | awk '{print $1}') ${archive##*/}"

	log "Saving hyperfilelens-redis:alpine..."
	archive="${images_dir}/02-redis-alpine.tar.gz"
	docker tag redis:alpine hyperfilelens-redis:alpine
	save_image_archive "${archive}" hyperfilelens-redis:alpine
	log "  wrote $(du -h "${archive}" | awk '{print $1}') ${archive##*/}"
}

write_manifest() {
	local pkg_root=$1
	local version=$2
	local commit=$3
	local payload_sha=$4
	local backend_digest=$5
	local frontend_digest=$6
	local postgres_digest=$7
	local redis_digest=$8
	local built_at version_file build_info
	built_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	version_file="${ROOT}/tools/dependencies/versions/docker-ce.env"
	build_info="${pkg_root}/sourcelens/BUILD_INFO.json"

	python3 - "${pkg_root}/MANIFEST.json" "${version}" "${built_at}" "${commit}" \
		"${payload_sha}" \
		"${backend_digest}" "${frontend_digest}" "${postgres_digest}" "${redis_digest}" \
		"${version_file}" "${build_info}" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

(
    out_path,
    version,
    built_at,
    commit,
    payload_sha,
    backend_d,
    frontend_d,
    postgres_d,
    redis_d,
    version_file,
    build_info_path,
) = sys.argv[1:12]
pkg_root = pathlib.Path(out_path).parent

pins = {}
for line in pathlib.Path(version_file).read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    pins[key.strip()] = value.strip()

def display_engine_version(raw: str) -> str:
    m = re.search(r"(\d+\.\d+\.\d+)", raw)
    return m.group(1) if m else raw


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


docker_bundles = []
for ubuntu_release, release_id in (("20.04", "2004"), ("24.04", "2404")):
    relative = pathlib.Path(
        f"payload/media/gateway-bootstrap/docker-debs-ubuntu{release_id}-amd64.tar.gz"
    )
    archive = pkg_root / relative
    if not archive.is_file():
        raise SystemExit(f"missing Docker offline bundle: {relative}")
    docker_bundles.append(
        {
            "ubuntu_release": ubuntu_release,
            "arch": "amd64",
            "file": relative.as_posix(),
            "size": archive.stat().st_size,
            "sha256": sha256_file(archive),
        }
    )

images = [
    {
        "file": "images/00-hyperfilelens.tar.gz",
        "refs": [
            f"hyperfilelens-backend:{version}",
            "hyperfilelens-backend:latest",
            f"hyperfilelens-frontend:{version}",
            "hyperfilelens-frontend:latest",
        ],
        "digests": [backend_d, frontend_d],
        "role": "hyperfilelens",
    },
    {
        "file": "images/01-postgres-17.tar.gz",
        "refs": ["hyperfilelens-postgres:17"],
        "digests": [postgres_d],
        "role": "shared",
    },
    {
        "file": "images/02-redis-alpine.tar.gz",
        "refs": ["hyperfilelens-redis:alpine"],
        "digests": [redis_d],
        "role": "shared",
    },
]

sourcelens = {"enabled": False}
build_info = pathlib.Path(build_info_path)
if build_info.is_file():
    info = json.loads(build_info.read_text(encoding="utf-8"))
    sourcelens = {
        "enabled": True,
        "git_url": info.get("git_url", ""),
        "git_ref": info.get("git_ref", ""),
        "git_commit": info.get("git_commit", ""),
        "git_commit_short": info.get("git_commit_short", ""),
        "version": info.get("version", ""),
        "patch_sha256": info.get("patch_sha256", ""),
        "network": info.get("network", "hyperfilelens-bridge"),
        "install_dir": info.get("install_dir", "/opt/hyperfilelens/sourcelens"),
        "lensnode_image": info.get("lensnode_image", "sourcelens-lensnode:latest"),
    }
    images.extend(
        [
            {
                "file": "images/10-sourcelens-app.tar.gz",
                "refs": [
                    info["images"]["backend"]["ref"],
                    f"{info['images']['backend']['ref'].rsplit(':', 1)[0]}:latest",
                    info["images"]["frontend"]["ref"],
                    f"{info['images']['frontend']['ref'].rsplit(':', 1)[0]}:latest",
                ],
                "digests": [
                    info["images"]["backend"]["digest"],
                    info["images"]["frontend"]["digest"],
                ],
                "source_refs": [
                    info["images"]["backend"].get("upstream_ref", ""),
                    info["images"]["frontend"].get("upstream_ref", ""),
                ],
                "role": "sourcelens-app",
            },
            {
                "file": "images/11-sourcelens-lensnode.tar.gz",
                "refs": [
                    info["images"]["lensnode"]["ref"],
                    f"{info['images']['lensnode']['ref'].rsplit(':', 1)[0]}:latest",
                    info.get("lensnode_image", "sourcelens-lensnode:latest"),
                ],
                "digests": [info["images"]["lensnode"]["digest"]],
                "source_refs": [info["images"]["lensnode"].get("upstream_ref", "")],
                "role": "sourcelens-lensnode",
            },
            {
                "file": "images/12-nginx-stable-alpine.tar.gz",
                "refs": ["hyperfilelens-sourcelens-nginx:stable-alpine"],
                "digests": [info["images"]["nginx"]["digest"]],
                "role": "sourcelens-nginx",
            },
        ]
    )

for image in images:
    archive = pkg_root / image["file"]
    if not archive.is_file():
        raise SystemExit(f"missing image archive: {image['file']}")
    image["sha256"] = sha256_file(archive)

tls_artifacts = {}
for role, relative in (
    ("server_certificate", "deploy/nginx/certs/tls.crt"),
    ("server_private_key", "deploy/nginx/certs/tls.key"),
    ("root_ca", "deploy/nginx/certs/root-ca.crt"),
):
    path = pkg_root / relative
    if not path.is_file():
        raise SystemExit(f"missing default TLS artifact: {relative}")
    tls_artifacts[role] = {
        "file": relative,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }

manifest = {
    "product": "hyperfilelens",
    "version": version,
    "built_at": built_at,
    "git_commit": commit,
    "host_runtime": {
        "os_id": "ubuntu",
        "os_versions": ["20.04", "24.04"],
        "arch": "amd64",
        "docker": {
            "engine_version": display_engine_version(pins.get("ENGINE_VERSION", "")),
            "compose_plugin_version": display_engine_version(pins.get("COMPOSE_PLUGIN_VERSION", "")),
            "min_engine_version": pins.get("MIN_ENGINE_VERSION", "24.0.0"),
            "min_compose_version": "2.20.0",
            "bundles": docker_bundles,
        },
    },
    "sourcelens": sourcelens,
    "images": images,
    "artifacts": {
        "payload_tree_sha256": payload_sha,
        "agent_version": version,
        "default_tls": tls_artifacts,
    },
}
pathlib.Path(out_path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY
}

validate_release_publish_artifacts() {
	local pkg_root=$1
	local releases="${pkg_root}/payload/media/agent-releases"
	local enroll="${pkg_root}/payload/media/enroll-bootstrap"
	[[ -d "${releases}" && -n "$(ls -A "${releases}" 2>/dev/null)" ]] \
		|| die "release package missing agent-releases artifacts"
	[[ -d "${enroll}" && -n "$(ls -A "${enroll}" 2>/dev/null)" ]] \
		|| die "release package missing enroll-bootstrap artifacts"
	if [[ ! -d "${pkg_root}/sourcelens" ]]; then
		return 0
	fi
	local gb="${pkg_root}/payload/media/gateway-bootstrap"
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
		[[ -f "${gb}/${name}" ]] || die "BUILD_SOURCELENS=1 but missing gateway-bootstrap/${name}"
	done
	log "Publish artifact validation passed"
}

write_package_readme() {
	local pkg_root=$1
	local version=$2
	cat > "${pkg_root}/README.md" <<EOF
# HyperFileLens ${version}

Release installation package for **Ubuntu 20.04/24.04 amd64** air-gap hosts.
Includes OS-specific offline Docker CE archives plus application container images.
When bundled, SourceLens runs from \`/opt/hyperfilelens/sourcelens\` on the private
\`hyperfilelens-bridge\` Docker network. External Agent and LensNode traffic
enters through the configured HyperFileLens Tenant HTTPS endpoint.

## Host requirements

### Minimum (PoC / lab)

- Ubuntu **20.04 or 24.04 amd64**
- 2 CPU cores · 4GB RAM · 100GB system disk
- Docker Engine ≥ 24.0 with Compose v2 ≥ 2.20, or no existing Docker installation
- The configured Tenant, Platform Operations, and bundled SourceLens Console host ports

### Recommended (production)

- Ubuntu 20.04 / 24.04 amd64
- 4 CPU cores · 8GB–16GB RAM · 200GB+ SSD

### Notes

- **amd64 only**; ARM64 is not supported for the control-plane host.
- OS-specific Docker packages target Ubuntu 20.04 and 24.04 amd64.
- Existing healthy Docker is reused; an existing but unsuitable installation causes a safe failure.
- When Docker is absent, the installer uses the matching offline archive without network access.
- The 2 CPU / 4GB profile is intended for light workloads; use 8GB+ for sustained production scans.

## Install

\`\`\`bash
tar xzf hyperfilelens-${version}-<commit7>.tar.gz
cd hyperfilelens-${version}
sudo ./install.sh install
\`\`\`

The default \`SOURCELENS_MODE=bundled\` deploys the packaged SourceLens stack and configures its private bridge URL.
Set \`SOURCELENS_MODE=external\` and \`LENS_BASE_URL=https://sourcelens.example.com\` to use an existing platform without installing, stopping, or upgrading it. Use \`sudo ./install.sh install --hfl-only\` for a one-time SourceLens skip.

The installer prints the effective Tenant, Platform Operations, Django Admin, and bundled SourceLens Console URLs from the six host-publishing settings in \`.env\`.

After \`install\`, the script prints the console URL and fixed initial login credentials from \`.env\`:

- HFL defaults to \`admin@hyperfilelens.com\` / \`Admin@123\`
- bundled SourceLens defaults to \`admin\` / \`adminpassword\`
- \`SEED_INITIAL_DATA=1\` enables first-run seeding via the worker service

Passwords changed in either database are not reset by upgrades. Change the public defaults after first login unless external access controls provide the required protection.

The package includes the repository-pinned TLS identity under \`deploy/nginx/certs/\`.
Install \`root-ca.crt\` into a client trust store to remove warnings for covered local names.
Existing complete \`tls.crt\` / \`tls.key\` pairs are preserved during upgrade; an incomplete pair stops the upgrade before services are changed.

## Upgrade

\`\`\`bash
sudo ./install.sh upgrade --from /path/to/hyperfilelens-<version>-<commit>.tar.gz
sudo ./install.sh upgrade --from /path/to/new.tar.gz --hfl-only
sudo ./install.sh upgrade --from /path/to/new.tar.gz --remove-sourcelens
\`\`\`

When the package includes \`sourcelens/\`, upgrade also refreshes SourceLens under \`/opt/hyperfilelens/sourcelens\` and updates
\`data/media/gateway-bootstrap/\` / \`data/media/enroll-bootstrap/\` publish artifacts on this host. Existing enrolled nodes and
installed Data Gateways are not upgraded automatically; new enrollments and offline DG installs use the updated files.
\`data/media/agent-releases/\` versions are merged (older versions are kept).

## Uninstall

\`\`\`bash
sudo ./install.sh uninstall
sudo ./install.sh uninstall --with-sourcelens
sudo ./install.sh uninstall --with-sourcelens --purge-sourcelens-data --purge-media --purge-all
\`\`\`

## Commands

\`install\` | \`start\` | \`stop\` | \`restart\` | \`status\` | \`uninstall\` | \`upgrade\`
EOF
}

main() {
	parse_args "$@"
	hfl_logging_configure release "${LOG_FILE}" "${VERBOSE}"
	apply_mirror_env_defaults
	apply_go_proxy_env_defaults
	validate_docker_pull_timeout
	apply_ubuntu2404_arch_default
	if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
		print_config
		return 0
	fi
	hfl_logging_start
	preflight
	log "Checking English-only public source trees"
	python3 "${ROOT}/tools/quality/check-english-source.py"
	local version commit_full commit7 release_commit pkg_name pkg_root images_dir tar_path tar_basename
	version="$(read_version)"
	HFL_VERSION="${version}"
	commit_full="$(resolve_commit_full "${ROOT}")"
	commit7="$(resolve_commit7 "${ROOT}")"
	release_commit="${commit_full}"
	RELEASE_COMMIT="${release_commit}"
	pkg_name="hyperfilelens-${version}"
	if [[ -n "${PACKAGE_BASENAME:-}" ]]; then
		tar_basename="${PACKAGE_BASENAME}"
	else
		tar_basename="$(release_package_basename_for_version "${version}" "${commit7}")"
	fi
	safe_assert_package_basename "${tar_basename}"
	pkg_root="${STAGING_BASE}/${pkg_name}"
	images_dir="${pkg_root}/images"

	log "Version ${version} (git ${commit7}, ${commit_full})"
	safe_assert_staging_pkg_root "${pkg_root}" "${STAGING_BASE}"
	safe_rm_dir "${pkg_root}"
	mkdir -p "${images_dir}"
	mkdir -p "${pkg_root}/deploy/nginx/certs"

	log "Preparing Kopia artifacts for Backend and Agent packaging"
	prepare_kopia_artifacts

	log "Fetching host Docker CE debs (ubuntu 20.04/24.04 amd64)"
	fetch_host_docker_debs

	log "Building control-plane Docker images"
	export_build_mirror_env
	build_control_plane_images

	log "Building SourceLens bundle (BUILD_SOURCELENS=${BUILD_SOURCELENS:-1})"
	build_sourcelens_bundle "${pkg_root}" "${images_dir}"

	publish_agent "${pkg_root}"
	stage_host_docker_bundles "${pkg_root}"

	log "Pulling third-party runtime images"
	local postgres_digest redis_digest backend_digest frontend_digest
	pull_image postgres:17
	postgres_digest="$(log_image_digest postgres:17)"
	pull_image redis:alpine
	redis_digest="$(log_image_digest redis:alpine)"
	backend_digest="$(log_image_digest hyperfilelens-backend:latest)"
	frontend_digest="$(log_image_digest hyperfilelens-frontend:latest)"

	save_images "${images_dir}"

	log "Staging package files"
	printf '%s\n' "${version}" > "${pkg_root}/VERSION"
	cp "${ROOT}/deploy/docker-compose.yml" "${pkg_root}/docker-compose.yml"
	cp "${ROOT}/.env.example" "${pkg_root}/.env.example"
	cp "${ROOT}/LICENSE" "${pkg_root}/LICENSE"
	stage_default_tls_bundle "${pkg_root}"
	cp "${ROOT}/deploy/nginx/default.conf" "${pkg_root}/deploy/nginx/default.conf"
	mkdir -p "${pkg_root}/deploy/nginx/snippets"
	rsync -a "${ROOT}/deploy/nginx/snippets/" "${pkg_root}/deploy/nginx/snippets/"
	cp "${ROOT}/deploy/installer/install.sh" "${pkg_root}/install.sh"
	cp "${ROOT}/deploy/installer/apply-runtime-config.py" "${pkg_root}/apply-runtime-config.py"
	chmod +x "${pkg_root}/install.sh" "${pkg_root}/apply-runtime-config.py"
	mkdir -p "${pkg_root}/deploy/logrotate"
	cp "${ROOT}/deploy/logrotate/hyperfilelens.conf" "${pkg_root}/deploy/logrotate/hyperfilelens.conf"

	normalize_release_permissions "${pkg_root}"

	local payload_sha
	payload_sha="$(tree_sha256 "${pkg_root}/payload")"

	write_manifest "${pkg_root}" "${version}" "${release_commit}" "${payload_sha}" \
		"${backend_digest}" "${frontend_digest}" "${postgres_digest}" "${redis_digest}"
	validate_release_publish_artifacts "${pkg_root}"
	write_package_readme "${pkg_root}" "${version}"
	validate_release_security "${pkg_root}"

	mkdir -p "${DIST_DIR}"
	tar_path="${DIST_DIR}/${tar_basename}"
	local tar_tmp="${tar_path}.part"
	rm -f "${tar_tmp}"
	log "Creating ${tar_path}"
	tar_create_gz "${tar_tmp}" "${STAGING_BASE}" "${pkg_name}"
	mv -f "${tar_tmp}" "${tar_path}"
	chmod 644 "${tar_path}"
	cp "${ROOT}/deploy/nginx/certs/root-ca.crt" "${DIST_DIR}/hyperfilelens-root-ca.crt"
	chmod 644 "${DIST_DIR}/hyperfilelens-root-ca.crt"
	(
		cd "${DIST_DIR}"
		sha256sum "$(basename "${tar_path}")" hyperfilelens-root-ca.crt >SHA256SUMS
	)

	log "Package sizes:"
	du -sh "${images_dir}" "${pkg_root}/payload" "${tar_path}" || true
	log "Done: ${tar_path}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	hfl_logging_configure release
	trap 'rc=$?; hfl_logging_finish "${rc}"' EXIT
	trap 'exit 130' INT TERM
	main "$@"
fi

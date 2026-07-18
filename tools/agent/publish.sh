#!/usr/bin/env bash
# Build Agent distributions under build/agent/<version>/package/, then publish copies to
# data/media/agent-releases/<version>/ (runtime path for nginx; survives build.sh --clean).
#
# Pipeline (Agent): fetch-deps.sh → build.sh → package.sh
# This script:       fetch + build + package → copy package/* + enroll scripts → media/agent-releases/
#
# Usage:
#   ./tools/agent/publish.sh
#   ./tools/agent/publish.sh --matrix "linux:amd64"
#   ./tools/agent/publish.sh --version 0.1.0
#
set -euo pipefail

DEFAULT_MATRIX="linux:amd64 linux:arm64 darwin:amd64 darwin:arm64 windows:amd64"

require_value() {
	hfl_require_value "$1" "${2:-}"
}

usage() {
	cat <<USAGE
Usage: ./tools/agent/publish.sh [options]

Role: fetch-deps.sh → build.sh → package.sh, then publish packages and enrollment binaries.

Options:
  --version VERSION                Release version (default: exact Git tag or 0.1.0; env: RELEASE_VERSION)
  --matrix MATRIX                  os:arch list (default: full matrix; env: AGENT_MATRIX)
  --commit COMMIT                  Full build commit (env: AGENT_COMMIT)
  --bundle KIND                    all | standard | ubuntu2404 (env: AGENT_BUNDLE)
  --ubuntu2404-arch ARCH           NAS deb arch when --bundle is all or ubuntu2404: amd64 | arm64 | all
                                   (env: AGENT_UBUNTU2404_ARCH; default: amd64)
  --force-fetch                    Re-download fetch-deps.sh inputs (--force)
  --releases-dir DIR               Publish target (default: data/media/agent-releases; env: AGENT_RELEASES_DIR)

Build (passed to build.sh):
  --go-proxy URL                   Go module proxy (env: GOPROXY)
  --go-sumdb VALUE                 Go checksum database (env: GOSUMDB)

Fetch (passed to fetch-deps.sh):
  --kopia-version VERSION          Kopia version without v prefix (env: KOPIA_VERSION)
  --github-download-mirror URL     GitHub download mirror (env: GITHUB_DOWNLOAD_MIRROR)
  --github-token TOKEN             GitHub API token (env: GITHUB_TOKEN)
  --docker-download-mirror URL     Docker Hub mirror for NAS ubuntu:24.04 (env: DOCKER_DOWNLOAD_MIRROR)
  --apt-mirror URL                 Ubuntu apt mirror for NAS container (env: APT_MIRROR)

Output:
  --log-file FILE                  Append runtime logs to FILE (env: HFL_LOG_FILE)
  --verbose                        Enable debug logs (env: HFL_LOG_VERBOSE=1)
  --print-config                   Print effective non-secret configuration and exit

  -h, --help                       Show this help

Examples:
  ./tools/agent/publish.sh
  ./tools/agent/publish.sh --bundle standard
  ./tools/agent/publish.sh --bundle standard --version VERSION --matrix MATRIX --force-fetch --releases-dir DIR --github-download-mirror URL --github-token TOKEN
  ./tools/agent/publish.sh --bundle ubuntu2404
  ./tools/agent/publish.sh --bundle ubuntu2404 --version VERSION --ubuntu2404-arch ARCH --force-fetch --releases-dir DIR --github-download-mirror URL --github-token TOKEN --docker-download-mirror URL --apt-mirror URL
  ./tools/agent/publish.sh --bundle all
  ./tools/agent/publish.sh --bundle all --version VERSION --matrix MATRIX --ubuntu2404-arch ARCH --force-fetch --releases-dir DIR --github-download-mirror URL --github-token TOKEN --docker-download-mirror URL --apt-mirror URL

  # Optional third-party accelerators for networks with restricted upstream access.
  ./tools/agent/publish.sh --github-download-mirror https://ghfast.top --docker-download-mirror docker.m.daocloud.io --apt-mirror https://mirrors.tuna.tsinghua.edu.cn

Mirror examples are not operated by HyperFileLens and are never enabled automatically.
USAGE
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/version.sh
source "${ROOT}/tools/lib/version.sh"
# shellcheck source=../lib/logging.sh
source "${ROOT}/tools/lib/logging.sh"
AGENT_DIR="${ROOT}/src/agent"
BUILD_DIR="${ROOT}/build/agent"
DEFAULT_RELEASES_DIR="${ROOT}/data/media/agent-releases"
BUNDLE="${AGENT_BUNDLE:-all}"
FORCE_FETCH=0
UBUNTU2404_ARCH="${AGENT_UBUNTU2404_ARCH:-amd64}"
MATRIX="${AGENT_MATRIX:-${DEFAULT_MATRIX}}"
OPT_VERSION=""
OPT_RELEASES_DIR=""
OPT_MATRIX=""
OPT_COMMIT=""
OPT_BUNDLE=""
OPT_GO_PROXY=""
OPT_GO_SUMDB=""
OPT_GITHUB_DOWNLOAD_MIRROR=""
OPT_GITHUB_TOKEN=""
OPT_DOCKER_DOWNLOAD_MIRROR=""
OPT_APT_MIRROR=""
OPT_KOPIA_VERSION=""
LOG_FILE="${HFL_LOG_FILE:-}"
VERBOSE="${HFL_LOG_VERBOSE:-0}"
PRINT_CONFIG=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	--version)
		require_value "$1" "${2:-}"
		OPT_VERSION="$2"
		shift 2
		;;
	--releases-dir)
		require_value "$1" "${2:-}"
		OPT_RELEASES_DIR="$2"
		shift 2
		;;
	--force-fetch | --refresh-kopia-cache)
		FORCE_FETCH=1
		shift
		;;
	--matrix)
		require_value "$1" "${2:-}"
		OPT_MATRIX="$2"
		shift 2
		;;
	--commit)
		require_value "$1" "${2:-}"
		OPT_COMMIT="$2"
		shift 2
		;;
	--bundle)
		require_value "$1" "${2:-}"
		OPT_BUNDLE="$2"
		shift 2
		;;
	--ubuntu2404-arch)
		require_value "$1" "${2:-}"
		UBUNTU2404_ARCH="$2"
		shift 2
		;;
	--go-proxy)
		require_value "$1" "${2:-}"
		OPT_GO_PROXY="$2"
		shift 2
		;;
	--go-sumdb)
		require_value "$1" "${2:-}"
		OPT_GO_SUMDB="$2"
		shift 2
		;;
	--kopia-version)
		require_value "$1" "${2:-}"
		OPT_KOPIA_VERSION="${2#v}"
		shift 2
		;;
	--github-download-mirror)
		require_value "$1" "${2:-}"
		OPT_GITHUB_DOWNLOAD_MIRROR="$2"
		shift 2
		;;
	--github-token)
		require_value "$1" "${2:-}"
		OPT_GITHUB_TOKEN="$2"
		shift 2
		;;
	--docker-download-mirror)
		require_value "$1" "${2:-}"
		OPT_DOCKER_DOWNLOAD_MIRROR="$2"
		shift 2
		;;
	--apt-mirror)
		require_value "$1" "${2:-}"
		OPT_APT_MIRROR="$2"
		shift 2
		;;
	--log-file)
		require_value "$1" "${2:-}"
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
	-h | --help)
		usage
		exit 0
		;;
	-*)
		hfl_log_fail "Unknown option: $1"
		usage
		exit 2
		;;
	*)
		hfl_log_fail "Unexpected argument: $1"
		usage
		exit 2
		;;
	esac
done

VERSION="$(normalize_release_version "${OPT_VERSION:-$(resolve_release_version)}")" || exit $?
COMMIT="${OPT_COMMIT:-${AGENT_COMMIT:-$(resolve_commit_full "${ROOT}")}}"
RELEASES_DIR="${OPT_RELEASES_DIR:-${AGENT_RELEASES_DIR:-${DEFAULT_RELEASES_DIR}}}"
GO_PROXY="${OPT_GO_PROXY:-${GOPROXY:-}}"
GO_SUMDB="${OPT_GO_SUMDB:-${GOSUMDB:-}}"

if [[ -n "${OPT_MATRIX}" ]]; then
	MATRIX="${OPT_MATRIX}"
fi

if [[ -n "${OPT_BUNDLE}" ]]; then
	BUNDLE="${OPT_BUNDLE}"
fi

case "${BUNDLE}" in
all | standard | ubuntu2404) ;;
*)
	hfl_die "Invalid --bundle ${BUNDLE} (use all, standard, or ubuntu2404)" 2
	;;
esac

GITHUB_DOWNLOAD_MIRROR="${OPT_GITHUB_DOWNLOAD_MIRROR:-${GITHUB_DOWNLOAD_MIRROR:-}}"
GITHUB_TOKEN="${OPT_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
DOCKER_DOWNLOAD_MIRROR="${OPT_DOCKER_DOWNLOAD_MIRROR:-${DOCKER_DOWNLOAD_MIRROR:-}}"
APT_MIRROR="${OPT_APT_MIRROR:-${APT_MIRROR:-}}"
# shellcheck source=../dependencies/versions/kopia.env
source "${ROOT}/tools/dependencies/versions/kopia.env"
KOPIA_VERSION="${OPT_KOPIA_VERSION:-${KOPIA_VERSION}}"
[[ "${KOPIA_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
	|| hfl_die "Invalid Kopia version: ${KOPIA_VERSION}" 2

ubuntu2404_matrix() {
	case "${UBUNTU2404_ARCH}" in
	all) echo "linux:amd64 linux:arm64" ;;
	amd64 | arm64) echo "linux:${UBUNTU2404_ARCH}" ;;
	*)
		hfl_die "Invalid --ubuntu2404-arch ${UBUNTU2404_ARCH} (use amd64, arm64, or all)" 2
		;;
	esac
}

if [[ "${BUNDLE}" == "ubuntu2404" && -z "${OPT_MATRIX}" ]]; then
	MATRIX="$(ubuntu2404_matrix)"
fi

BOOTSTRAP_DIR="${ROOT}/deploy/bootstrap"
BOOTSTRAP_SCRIPTS=(agent-bootstrap-linux.sh agent-bootstrap-macos.sh agent-bootstrap-windows.ps1 gateway-bootstrap-linux.sh)
GATEWAY_BOOTSTRAP_LINUX_SCRIPT=gateway-bootstrap-linux.sh
GATEWAY_SIDECAR_SCRIPT=gateway-install-lensnode-sidecar.sh
GATEWAY_LIFECYCLE_SCRIPT=gateway-lifecycle.sh
GATEWAY_DOCKER_INSTALL_SCRIPT=gateway-install-docker-ubuntu2404-amd64.sh
GATEWAY_DOCKER_DEBS_ARCHIVE=docker-debs-ubuntu2404-amd64.tar.gz
GATEWAY_LENSNODE_IMAGE=lensnode-image-linux-amd64.tar.gz
ENROLL_BOOTSTRAP_DIR="${RELEASES_DIR%/agent-releases}/enroll-bootstrap"
GATEWAY_BOOTSTRAP_DIR="${RELEASES_DIR%/agent-releases}/gateway-bootstrap"

print_config() {
	cat <<EOF
version=${VERSION}
commit=${COMMIT}
bundle=${BUNDLE}
matrix=${MATRIX}
ubuntu2404_arch=${UBUNTU2404_ARCH}
build_dir=${BUILD_DIR}/${VERSION}
releases_dir=${RELEASES_DIR}
force_fetch=${FORCE_FETCH}
kopia_version=${KOPIA_VERSION}
go_proxy=${GO_PROXY:-<official>}
go_sumdb=${GO_SUMDB:-<official>}
github_download_mirror=${GITHUB_DOWNLOAD_MIRROR:-<official>}
github_token=$(hfl_redact "${GITHUB_TOKEN}")
docker_download_mirror=${DOCKER_DOWNLOAD_MIRROR:-<official>}
apt_mirror=${APT_MIRROR:-<official>}
log_file=${LOG_FILE:-<none>}
verbose=${VERBOSE}
EOF
}

hfl_logging_configure agent-publish "${LOG_FILE}" "${VERBOSE}"
if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
	print_config
	exit 0
fi
trap 'rc=$?; hfl_logging_finish "${rc}"' EXIT
trap 'exit 130' INT TERM
hfl_logging_start

if [[ -z "${VERSION}" ]]; then
	hfl_die "Could not resolve release version (use --version or git tag v*)" 2
fi

for name in "${BOOTSTRAP_SCRIPTS[@]}"; do
	if [[ ! -f "${BOOTSTRAP_DIR}/${name}" ]]; then
		hfl_die "Missing bootstrap template ${BOOTSTRAP_DIR}/${name}" 3
	fi
done
if [[ ! -f "${BOOTSTRAP_DIR}/${GATEWAY_SIDECAR_SCRIPT}" ]]; then
	hfl_die "Missing bootstrap template ${BOOTSTRAP_DIR}/${GATEWAY_SIDECAR_SCRIPT}" 3
fi
if [[ ! -f "${BOOTSTRAP_DIR}/${GATEWAY_LIFECYCLE_SCRIPT}" ]]; then
	hfl_die "Missing bootstrap template ${BOOTSTRAP_DIR}/${GATEWAY_LIFECYCLE_SCRIPT}" 3
fi
if [[ ! -f "${BOOTSTRAP_DIR}/${GATEWAY_DOCKER_INSTALL_SCRIPT}" ]]; then
	hfl_die "Missing bootstrap template ${BOOTSTRAP_DIR}/${GATEWAY_DOCKER_INSTALL_SCRIPT}" 3
fi

validate_matrix() {
	local item goos goarch
	for item in ${MATRIX}; do
		IFS=: read -r goos goarch <<<"${item}"
		case "${goos}" in
		linux | darwin)
			case "${goarch}" in
			amd64 | arm64) ;;
			*)
				hfl_die "Unsupported ${goos} arch in matrix: ${item}" 2
				;;
			esac
			;;
		windows)
			if [[ "${goarch}" != "amd64" ]]; then
				hfl_die "Unsupported windows arch in matrix: ${item}" 2
			fi
			;;
		*)
			hfl_die "Unsupported platform in matrix: ${item}" 2
			;;
		esac
	done
}

matrix_has_linux() {
	local item goos goarch
	for item in ${MATRIX}; do
		IFS=: read -r goos goarch <<<"${item}"
		[[ "${goos}" == "linux" ]] && return 0
	done
	return 1
}

archive_ext_for() {
	case "$1" in
	windows) echo "zip" ;;
	*) echo "tar.gz" ;;
	esac
}

ubuntu2404_archive_matches() {
	local base=$1
	case "${UBUNTU2404_ARCH}" in
	all) return 0 ;;
	amd64 | arm64)
		[[ "${base}" == *"-linux-${UBUNTU2404_ARCH}-ubuntu2404.tar.gz" ]]
		;;
	esac
}

fetch_common_args=()
fetch_common_args+=(--kopia-version "${KOPIA_VERSION}")
if [[ "${FORCE_FETCH}" -eq 1 ]]; then
	fetch_common_args+=(--force)
fi
if [[ -n "${GITHUB_DOWNLOAD_MIRROR}" ]]; then
	fetch_common_args+=(--github-download-mirror "${GITHUB_DOWNLOAD_MIRROR}")
fi
if [[ -n "${GITHUB_TOKEN}" ]]; then
	export GITHUB_TOKEN
fi
if [[ -n "${DOCKER_DOWNLOAD_MIRROR}" ]]; then
	fetch_common_args+=(--docker-download-mirror "${DOCKER_DOWNLOAD_MIRROR}")
fi
if [[ -n "${APT_MIRROR}" ]]; then
	fetch_common_args+=(--apt-mirror "${APT_MIRROR}")
fi

publish_archives() {
	local published=0 archive dest item goos goarch ext base

	mkdir -p "${RELEASES_DIR}/${VERSION}"

	if [[ "${BUNDLE}" == "ubuntu2404" ]]; then
		shopt -s nullglob
		for archive in "${BUILD_DIR}/${VERSION}/package"/hfl-agent-"${VERSION}"-*-ubuntu2404.tar.gz; do
			[[ -f "${archive}" ]] || continue
			base="$(basename "${archive}")"
			ubuntu2404_archive_matches "${base}" || continue
			dest="${RELEASES_DIR}/${VERSION}/${base}"
			cp -f "${archive}" "${dest}"
			hfl_log_ok "Published ${base}"
			published=$((published + 1))
		done
		shopt -u nullglob
	elif [[ "${BUNDLE}" == "standard" ]]; then
		for item in ${MATRIX}; do
			IFS=: read -r goos goarch <<<"${item}"
			ext="$(archive_ext_for "${goos}")"
			archive="${BUILD_DIR}/${VERSION}/package/hfl-agent-${VERSION}-${goos}-${goarch}.${ext}"
			if [[ ! -f "${archive}" ]]; then
				hfl_die "Missing build archive ${archive}" 3
			fi
			dest="${RELEASES_DIR}/${VERSION}/$(basename "${archive}")"
			cp -f "${archive}" "${dest}"
			hfl_log_ok "Published $(basename "${dest}")"
			published=$((published + 1))
		done
	else
		for item in ${MATRIX}; do
			IFS=: read -r goos goarch <<<"${item}"
			ext="$(archive_ext_for "${goos}")"
			archive="${BUILD_DIR}/${VERSION}/package/hfl-agent-${VERSION}-${goos}-${goarch}.${ext}"
			if [[ ! -f "${archive}" ]]; then
				hfl_die "Missing build archive ${archive}" 3
			fi
			dest="${RELEASES_DIR}/${VERSION}/$(basename "${archive}")"
			cp -f "${archive}" "${dest}"
			hfl_log_ok "Published $(basename "${dest}")"
			published=$((published + 1))

			if [[ "${goos}" == "linux" ]]; then
				archive="${BUILD_DIR}/${VERSION}/package/hfl-agent-${VERSION}-${goos}-${goarch}-ubuntu2404.tar.gz"
				if [[ -f "${archive}" ]]; then
					dest="${RELEASES_DIR}/${VERSION}/$(basename "${archive}")"
					cp -f "${archive}" "${dest}"
					hfl_log_ok "Published $(basename "${dest}")"
					published=$((published + 1))
				fi
			fi
		done
	fi

	if [[ "${published}" -eq 0 ]]; then
		hfl_die "No Agent archives published from ${BUILD_DIR}/${VERSION}/package/" 3
	fi

	hfl_log_step "Copying bootstrap templates"
	for name in "${BOOTSTRAP_SCRIPTS[@]}"; do
		dest="${RELEASES_DIR}/${VERSION}/${name}"
		cp -f "${BOOTSTRAP_DIR}/${name}" "${dest}"
		if [[ "${name}" == *.sh ]]; then
			chmod 755 "${dest}"
		fi
		hfl_log_ok "Published ${name}"
	done

	hfl_log_step "Publishing hfl-enroll binaries"
	mkdir -p "${ENROLL_BOOTSTRAP_DIR}"
	for item in ${MATRIX}; do
		IFS=: read -r goos goarch <<<"${item}"
		enroll_name="hfl-enroll-${goos}-${goarch}"
		[[ "${goos}" == "windows" ]] && enroll_name="${enroll_name}.exe"
		src="${BUILD_DIR}/${VERSION}/${goos}/${goarch}/${enroll_name}"
		if [[ ! -f "${src}" ]]; then
			hfl_die "Missing hfl-enroll build output ${src}" 3
		fi
		dest="${ENROLL_BOOTSTRAP_DIR}/${enroll_name}"
		cp -f "${src}" "${dest}"
		chmod 755 "${dest}" 2>/dev/null || true
		hfl_log_ok "Published ${enroll_name}"
	done

	hfl_log_step "Publishing gateway sidecar bootstrap"
	mkdir -p "${GATEWAY_BOOTSTRAP_DIR}"
	gateway_bootstrap_src="${BOOTSTRAP_DIR}/${GATEWAY_BOOTSTRAP_LINUX_SCRIPT}"
	cp -f "${gateway_bootstrap_src}" "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_BOOTSTRAP_LINUX_SCRIPT}"
	chmod 755 "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_BOOTSTRAP_LINUX_SCRIPT}"
	hfl_log_ok "Published ${GATEWAY_BOOTSTRAP_LINUX_SCRIPT}"
	sidecar_src="${BOOTSTRAP_DIR}/${GATEWAY_SIDECAR_SCRIPT}"
	cp -f "${sidecar_src}" "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_SIDECAR_SCRIPT}"
	chmod 755 "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_SIDECAR_SCRIPT}"
	hfl_log_ok "Published ${GATEWAY_SIDECAR_SCRIPT}"
	lifecycle_src="${BOOTSTRAP_DIR}/${GATEWAY_LIFECYCLE_SCRIPT}"
	cp -f "${lifecycle_src}" "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_LIFECYCLE_SCRIPT}"
	chmod 755 "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_LIFECYCLE_SCRIPT}"
	hfl_log_ok "Published ${GATEWAY_LIFECYCLE_SCRIPT}"
	docker_install_src="${BOOTSTRAP_DIR}/${GATEWAY_DOCKER_INSTALL_SCRIPT}"
	cp -f "${docker_install_src}" "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_DOCKER_INSTALL_SCRIPT}"
	chmod 755 "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_DOCKER_INSTALL_SCRIPT}"
	hfl_log_ok "Published ${GATEWAY_DOCKER_INSTALL_SCRIPT}"
	host_debs_candidates=(
		"${ROOT}/build/dependencies/docker/ubuntu-24.04/amd64"
		"${ROOT}/host/debs"
	)
	host_debs_dir=""
	for candidate in "${host_debs_candidates[@]}"; do
		if [[ -d "${candidate}" ]] && compgen -G "${candidate}/*.deb" >/dev/null; then
			host_debs_dir="${candidate}"
			break
		fi
	done
	if [[ -n "${host_debs_dir}" ]]; then
		tar -czf "${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_DOCKER_DEBS_ARCHIVE}" -C "${host_debs_dir}" .
		hfl_log_ok "Published ${GATEWAY_DOCKER_DEBS_ARCHIVE}"
	else
		hfl_log_skip "${GATEWAY_DOCKER_DEBS_ARCHIVE}: host debs not found; run release/build.sh or tools/dependencies/fetch-docker-ce-debs.sh"
	fi
	lensnode_image_dest="${GATEWAY_BOOTSTRAP_DIR}/${GATEWAY_LENSNODE_IMAGE}"
	if [[ -f "${lensnode_image_dest}" ]]; then
		hfl_log_ok "${GATEWAY_LENSNODE_IMAGE} is already in place"
	else
		hfl_log_skip "${GATEWAY_LENSNODE_IMAGE}: enable SourceLens in dev/stack.sh or release/build.sh"
	fi
}

validate_matrix

hfl_log_step "Publishing HyperFileLens Agent releases"
hfl_log_info "Version: ${VERSION}"
hfl_log_info "Build directory: ${BUILD_DIR}/${VERSION}/package/"
hfl_log_info "Publish directory: ${RELEASES_DIR}/${VERSION}/"
hfl_log_info "Matrix: ${MATRIX}"
hfl_log_info "Commit: ${COMMIT}"
hfl_log_info "Bundle: ${BUNDLE}"
if [[ "${BUNDLE}" != "standard" ]]; then
	hfl_log_info "Ubuntu 24.04 architecture: ${UBUNTU2404_ARCH}"
fi

if [[ "${BUNDLE}" != "standard" ]] && matrix_has_linux; then
	hfl_log_step "Fetching Ubuntu 24.04 NAS dependency debs"
	"${AGENT_DIR}/scripts/fetch-deps.sh" --nas-deps "${fetch_common_args[@]}" \
		--version "${VERSION}" \
		--matrix "${MATRIX}" \
		--ubuntu2404-arch "${UBUNTU2404_ARCH}"
fi

hfl_log_step "Building Agent"
build_args=(--release \
	--version "${VERSION}" \
	--matrix "${MATRIX}" \
	--commit "${COMMIT}")
[[ -n "${GO_PROXY}" ]] && build_args+=(--go-proxy "${GO_PROXY}")
[[ -n "${GO_SUMDB}" ]] && build_args+=(--go-sumdb "${GO_SUMDB}")
"${AGENT_DIR}/scripts/build.sh" "${build_args[@]}"

hfl_log_step "Fetching Kopia CLI archives"
"${AGENT_DIR}/scripts/fetch-deps.sh" --kopia "${fetch_common_args[@]}" \
	--version "${VERSION}" \
	--matrix "${MATRIX}"

hfl_log_step "Packaging distribution archives"
package_args=(--version "${VERSION}" --matrix "${MATRIX}" --commit "${COMMIT}" --bundle "${BUNDLE}")
if [[ "${BUNDLE}" != "standard" ]] && matrix_has_linux; then
	package_args+=(--ubuntu2404-arch "${UBUNTU2404_ARCH}")
fi
"${AGENT_DIR}/scripts/package.sh" "${package_args[@]}"

if [[ ! -d "${BUILD_DIR}/${VERSION}/package" ]]; then
	hfl_die "Missing package output ${BUILD_DIR}/${VERSION}/package/" 3
fi

publish_archives

hfl_log_ok "Agent artifacts published for version ${VERSION}"

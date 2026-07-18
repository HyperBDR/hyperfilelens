#!/usr/bin/env bash
# Download external Agent runtime resources only (Kopia CLI and Ubuntu NAS debs).
# Does not compile source or assemble distribution archives.
set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${AGENT_ROOT}/../.." && pwd)"
# shellcheck source=../../../tools/lib/version.sh
source "${REPO_ROOT}/tools/lib/version.sh"

DEFAULT_MATRIX="linux:amd64 linux:arm64 darwin:amd64 darwin:arm64 windows:amd64"
VERBOSE="${AGENT_VERBOSE:-0}"
LOG_FILE="${AGENT_LOG_FILE:-}"
PRINT_CONFIG=0
SESSION_STARTED=0

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_finish_sentence() {
	local msg="$*"
	msg="${msg%"${msg##*[![:space:]]}"}"
	case "${msg}" in
	*. | *.? | *!) printf '%s' "${msg}" ;;
	*) printf '%s.' "${msg}" ;;
	esac
}

_hfl_emit_raw() {
	local level=$1
	shift
	printf '[%s] [%s] %s\n' "$(hfl_now)" "${level}" "$(hfl_finish_sentence "$@")" >&2
}

log_info() { _hfl_emit_raw "INFO " "$@"; }
log_ok() { _hfl_emit_raw " OK  " "$@"; }
log_step() { _hfl_emit_raw "STEP " "$@"; }
log_skip() { _hfl_emit_raw "SKIP " "$@"; }
log_warn() { _hfl_emit_raw "WARN " "$@"; }
log_fail() {
	local message=$1
	local code=${2:-1}
	_hfl_emit_raw "FAIL " "${message}"
	exit "${code}"
}

finish_session() {
	local rc=$?
	trap - EXIT
	if [[ "${SESSION_STARTED}" -eq 1 ]]; then
		if [[ "${rc}" -eq 0 ]]; then
			log_info "Agent dependency fetch session finished successfully"
		else
			log_warn "Agent dependency fetch session finished with errors (exit=${rc})"
		fi
	fi
	exit "${rc}"
}

require_value() {
	if [[ $# -lt 2 || -z "${2:-}" || "${2:0:1}" == "-" ]]; then
		printf 'ERROR: %s requires a value\n' "$1" >&2
		exit 2
	fi
}

usage() {
	cat <<'USAGE'
Usage: ./src/agent/scripts/fetch-deps.sh [--all|--kopia|--nas-deps] [options]

Purpose:
  Fetch external Agent runtime resources only. This script does not compile HFL
  source or assemble customer-facing archives. With no component, --all is used.

Components:
  --all                  Fetch Kopia CLI archives and Ubuntu 24.04 NAS debs
  --kopia                Fetch Kopia CLI archives only
  --nas-deps             Fetch nfs-common/cifs-utils offline debs through Docker

Inputs:
  tools/dependencies/versions/kopia.env, GitHub Releases, ubuntu:24.04, Ubuntu apt repositories

Outputs:
  build/agent/<version>/<os>/<arch>/kopia-*
  build/agent/<version>/KOPIA_INFO.json
  build/dependencies/agent/ubuntu-24.04/<arch>/*.deb
  build/dependencies/agent/ubuntu-24.04/<arch>/MANIFEST.json

Options:
  --version VERSION                Release version (env: RELEASE_VERSION)
  --matrix MATRIX                  Space-separated os:arch list (env: AGENT_MATRIX)
  --force                          Refresh cached inputs (env: AGENT_FORCE_FETCH=1)
  --pull                           Refresh the NAS Ubuntu image even when a matching local image exists
  --kopia-version VERSION          Kopia version without v prefix (env: KOPIA_VERSION)
  --github-download-mirror URL     Explicit GitHub download mirror (env: GITHUB_DOWNLOAD_MIRROR)
  --github-token TOKEN             GitHub API token (env: GITHUB_TOKEN; environment recommended)
  --ubuntu2404-arch ARCH           amd64 | arm64 | all (env: AGENT_UBUNTU2404_ARCH)
  --docker-download-mirror URL     Docker Hub mirror (env: DOCKER_DOWNLOAD_MIRROR)
  --docker-pull-timeout SECONDS    Timeout for each Docker pull attempt (env: DOCKER_PULL_TIMEOUT_SECONDS)
  --apt-mirror URL                 Ubuntu apt mirror (env: APT_MIRROR)
  --log-file FILE                  Append console output to FILE (env: AGENT_LOG_FILE)
  --verbose                        Enable detailed source logging (env: AGENT_VERBOSE=1)
  --print-config                   Print resolved configuration without fetching
  -h, --help                       Show this help

Supported matrix entries:
  linux:amd64 linux:arm64 darwin:amd64 darwin:arm64 windows:amd64

Precedence:
  CLI option > environment variable > tools/dependencies/versions/kopia.env > built-in default

Exit codes:
  0 success; 1 fetch failure; 2 invalid input or missing tool; 130 interrupted

Examples:
  ./src/agent/scripts/fetch-deps.sh --all
  ./src/agent/scripts/fetch-deps.sh --kopia --matrix "linux:amd64 linux:arm64"
  ./src/agent/scripts/fetch-deps.sh --nas-deps --ubuntu2404-arch amd64

  # Optional third-party accelerators for networks with restricted upstream access.
  ./src/agent/scripts/fetch-deps.sh --all \
    --github-download-mirror https://ghfast.top \
    --docker-download-mirror docker.m.daocloud.io \
    --apt-mirror https://mirrors.tuna.tsinghua.edu.cn

Mirror examples are not operated by HyperFileLens. Kopia archives are verified
against the checksums.txt published with the selected upstream release.
USAGE
}

DO_KOPIA=0
DO_NAS=0
FORCE=0
FORCE_PULL=0
EXPLICIT=0
OPT_VERSION=""
OPT_MATRIX=""
OPT_KOPIA_VERSION=""
OPT_UBUNTU2404_ARCH=""
OPT_GITHUB_DOWNLOAD_MIRROR=""
OPT_GITHUB_TOKEN=""
OPT_DOCKER_DOWNLOAD_MIRROR=""
OPT_DOCKER_PULL_TIMEOUT=""
OPT_APT_MIRROR=""

while [[ $# -gt 0 ]]; do
	case "$1" in
	--kopia)
		DO_KOPIA=1
		EXPLICIT=1
		shift
		;;
	--nas-deps)
		DO_NAS=1
		EXPLICIT=1
		shift
		;;
	--all)
		DO_KOPIA=1
		DO_NAS=1
		EXPLICIT=1
		shift
		;;
	--force)
		FORCE=1
		shift
		;;
	--pull)
		FORCE_PULL=1
		shift
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
	--version)
		require_value "$1" "${2:-}"
		OPT_VERSION="$2"
		shift 2
		;;
	--matrix)
		require_value "$1" "${2:-}"
		OPT_MATRIX="$2"
		shift 2
		;;
	--kopia-version)
		require_value "$1" "${2:-}"
		OPT_KOPIA_VERSION="${2#v}"
		shift 2
		;;
	--ubuntu2404-arch)
		require_value "$1" "${2:-}"
		OPT_UBUNTU2404_ARCH="$2"
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
	--docker-pull-timeout)
		require_value "$1" "${2:-}"
		OPT_DOCKER_PULL_TIMEOUT="$2"
		shift 2
		;;
	--apt-mirror)
		require_value "$1" "${2:-}"
		OPT_APT_MIRROR="$2"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	-*)
		printf 'ERROR: unknown option: %s\n' "$1" >&2
		usage >&2
		exit 2
		;;
	*)
		printf 'ERROR: unexpected argument: %s\n' "$1" >&2
		usage >&2
		exit 2
		;;
	esac
done

case "${VERBOSE}" in
0 | 1 | true | false | yes | no) ;;
*) printf 'ERROR: AGENT_VERBOSE must be 0 or 1\n' >&2; exit 2 ;;
esac
case "${VERBOSE}" in true | yes) VERBOSE=1 ;; false | no) VERBOSE=0 ;; esac

case "${AGENT_FORCE_FETCH:-0}" in
1 | true | yes) FORCE=1 ;;
0 | false | no | "") ;;
*) printf 'ERROR: AGENT_FORCE_FETCH must be 0 or 1\n' >&2; exit 2 ;;
esac
case "${AGENT_FORCE_PULL:-0}" in
1 | true | yes) FORCE_PULL=1 ;;
0 | false | no | "") ;;
*) printf 'ERROR: AGENT_FORCE_PULL must be 0 or 1\n' >&2; exit 2 ;;
esac

AGENT_VERSION="$(normalize_release_version "${OPT_VERSION:-$(resolve_release_version)}")" || exit $?
# shellcheck source=../../../tools/dependencies/versions/kopia.env
source "${REPO_ROOT}/tools/dependencies/versions/kopia.env"
KOPIA_VERSION="${OPT_KOPIA_VERSION:-${KOPIA_VERSION}}"
[[ "${KOPIA_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
	|| { printf 'ERROR: invalid Kopia version: %s\n' "${KOPIA_VERSION}" >&2; exit 2; }
MATRIX="${OPT_MATRIX:-${AGENT_MATRIX:-${DEFAULT_MATRIX}}}"
AGENT_ARTIFACTS_DIR="${REPO_ROOT}/build/agent"
WORK_ROOT="${AGENT_ARTIFACTS_DIR}/${AGENT_VERSION}"
NAS_DEPS_ROOT="${REPO_ROOT}/build/dependencies/agent/ubuntu-24.04"
GITHUB_DOWNLOAD_MIRROR="${OPT_GITHUB_DOWNLOAD_MIRROR:-${GITHUB_DOWNLOAD_MIRROR:-}}"
GITHUB_TOKEN="${OPT_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
DOCKER_DOWNLOAD_MIRROR="${OPT_DOCKER_DOWNLOAD_MIRROR:-${DOCKER_DOWNLOAD_MIRROR:-}}"
APT_MIRROR="${OPT_APT_MIRROR:-${APT_MIRROR:-}}"
DOCKER_PULL_TIMEOUT_SECONDS="${OPT_DOCKER_PULL_TIMEOUT:-${DOCKER_PULL_TIMEOUT_SECONDS:-180}}"
[[ "${DOCKER_PULL_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
	|| { printf 'ERROR: DOCKER_PULL_TIMEOUT_SECONDS must be a positive integer\n' >&2; exit 2; }
OPT_UBUNTU2404_ARCH="${OPT_UBUNTU2404_ARCH:-${AGENT_UBUNTU2404_ARCH:-}}"
KOPIA_GITHUB_REPO="kopia/kopia"

if [[ "${EXPLICIT}" -eq 0 ]]; then
	DO_KOPIA=1
	DO_NAS=1
fi

validate_matrix() {
	local item seen=" "
	[[ -n "${MATRIX//[[:space:]]/}" ]] || log_fail "Matrix cannot be empty" 2
	for item in ${MATRIX}; do
		case "${item}" in
		linux:amd64 | linux:arm64 | darwin:amd64 | darwin:arm64 | windows:amd64) ;;
		*) log_fail "Unsupported matrix entry ${item}" 2 ;;
		esac
		if [[ "${seen}" == *" ${item} "* ]]; then
			log_fail "Duplicate matrix entry ${item}" 2
		fi
		seen+="${item} "
	done
}

components_label() {
	if [[ "${DO_KOPIA}" -eq 1 && "${DO_NAS}" -eq 1 ]]; then
		printf 'kopia,nas-deps'
	elif [[ "${DO_KOPIA}" -eq 1 ]]; then
		printf 'kopia'
	else
		printf 'nas-deps'
	fi
}

print_config() {
	cat <<CONFIG
components=$(components_label)
version=${AGENT_VERSION}
matrix=${MATRIX}
kopia_version=${KOPIA_VERSION}
github_download_mirror=${GITHUB_DOWNLOAD_MIRROR:-<official>}
docker_download_mirror=${DOCKER_DOWNLOAD_MIRROR:-<official>}
apt_mirror=${APT_MIRROR:-<official>}
ubuntu2404_arch=${OPT_UBUNTU2404_ARCH:-<from-matrix>}
force=${FORCE}
force_pull=${FORCE_PULL}
docker_pull_timeout_seconds=${DOCKER_PULL_TIMEOUT_SECONDS}
kopia_output=${WORK_ROOT}
nas_output=${NAS_DEPS_ROOT}
CONFIG
}

setup_log_file() {
	[[ -n "${LOG_FILE}" ]] || return 0
	mkdir -p "$(dirname "${LOG_FILE}")"
	exec > >(tee -a "${LOG_FILE}") 2>&1
}

fetch_kopia() {
	command -v python3 >/dev/null 2>&1 || log_fail "python3 is required to fetch Kopia" 2
	log_step "Resolving Kopia v${KOPIA_VERSION}"

	local tag="v${KOPIA_VERSION}" semver="${KOPIA_VERSION}"

	local expected
	expected="$(TAG="${tag}" SEMVER="${semver}" MATRIX="${MATRIX}" python3 - <<'PY'
import json
import os

semver = os.environ["SEMVER"]
matrix = os.environ.get("MATRIX", "").split()


def cli_archive_name(goos: str, goarch: str) -> str:
    if goos == "linux":
        if goarch == "amd64":
            return f"kopia-{semver}-linux-x64.tar.gz"
        if goarch == "arm64":
            return f"kopia-{semver}-linux-arm64.tar.gz"
    if goos == "darwin":
        if goarch == "amd64":
            return f"kopia-{semver}-macOS-x64.tar.gz"
        if goarch == "arm64":
            return f"kopia-{semver}-macOS-arm64.tar.gz"
    if goos == "windows":
        if goarch == "amd64":
            return f"kopia-{semver}-windows-x64.zip"
    raise KeyError((goos, goarch))


items = []
for entry in matrix:
    entry = entry.strip()
    if not entry:
        continue
    goos, _, goarch = entry.partition(":")
    key = (goos.strip(), goarch.strip())
    try:
        name = cli_archive_name(*key)
    except KeyError:
        raise SystemExit(f"unsupported MATRIX entry {entry!r} (no kopia CLI archive mapping)") from None
    items.append({"goos": key[0], "goarch": key[1], "name": name})

print(json.dumps(items))
PY
)"

	mkdir -p "${WORK_ROOT}"

	local api_headers=(-fsSL -H "Accept: application/vnd.github+json" -H "User-Agent: hyperfilelens-kopia-download/1.0")
	if [[ -n "${GITHUB_TOKEN}" ]]; then
		api_headers+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
	fi

	local release_json=""
	if release_json="$(curl "${api_headers[@]}" "https://api.github.com/repos/${KOPIA_GITHUB_REPO}/releases/tags/${tag}" 2>/dev/null)"; then
		:
	else
		release_json=""
	fi

	if [[ "${FORCE}" -eq 1 ]]; then
		EXPECTED="${expected}" OUT="${WORK_ROOT}" python3 - <<'PY'
import json
import os
from pathlib import Path

expected = json.loads(os.environ["EXPECTED"])
out_root = Path(os.environ["OUT"])
for item in expected:
    dest = out_root / item["goos"] / item["goarch"] / item["name"]
    if dest.is_file():
        dest.unlink()
PY
	fi

	EXPECTED="${expected}" RELEASE_JSON="${release_json}" TAG="${tag}" SEMVER="${semver}" \
		OUT="${WORK_ROOT}" AGENT_VERSION="${AGENT_VERSION}" \
		FORCE_VALUE="${FORCE}" \
		GITHUB_DOWNLOAD_MIRROR="${GITHUB_DOWNLOAD_MIRROR}" \
		python3 - <<'PY'
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

USER_AGENT = "hyperfilelens-kopia-download/1.0"
expected = json.loads(os.environ["EXPECTED"])
tag = os.environ["TAG"]
semver = os.environ["SEMVER"]
repo = "kopia/kopia"
out_root = os.environ["OUT"]
release_json = os.environ.get("RELEASE_JSON", "")
force = os.environ.get("FORCE_VALUE", "0") == "1"


def log(level: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    message = message.rstrip()
    if message and message[-1] not in ".?!":
        message += "."
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr, flush=True)


def proxy_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(key, "").strip()
        if val:
            out[key] = val
    return out


def fallback_url(name: str) -> str:
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(tag, safe='')}/{quote(name, safe='')}"
    )


assets_by_name: dict[str, str] = {}
if release_json.strip():
    try:
        data = json.loads(release_json)
        for asset in data.get("assets") or []:
            name = asset.get("name") or ""
            url = asset.get("browser_download_url") or ""
            if name and url:
                assets_by_name[name] = url
    except json.JSONDecodeError:
        pass


def candidate_urls(url: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(u: str) -> None:
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    custom = os.environ.get("GITHUB_DOWNLOAD_MIRROR", "").strip().rstrip("/")
    if custom:
        add(f"{custom.rstrip('/')}/{url}")
    add(url)
    return ordered


def short_url(url: str) -> str:
    if len(url) <= 88:
        return url
    parsed = urlparse(url)
    if parsed.netloc in ("github.com", "release-assets.githubusercontent.com"):
        return f"...github.com/.../{parsed.path.rsplit('/', 1)[-1]}"
    return url[:40] + "..." + url[-40:]


def download_curl(url: str, dest: str) -> None:
    cmd = [
        "curl",
        "-fsSL",
        "--http1.1",
        "--connect-timeout",
        "30",
        "--max-time",
        "0",
        "--retry",
        "2",
        "--retry-delay",
        "2",
        "-H",
        f"User-Agent: {USER_AGENT}",
        "-o",
        dest,
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True, env={**os.environ, **proxy_env()})


def download_wget(url: str, dest: str) -> None:
    if not shutil.which("wget"):
        raise FileNotFoundError("wget not found")
    subprocess.run(
        ["wget", "-q", "--timeout=30", "-O", dest, url],
        check=True,
        capture_output=True,
        env={**os.environ, **proxy_env()},
    )


def download_urllib(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)


def download_file(url: str, dest: str) -> str:
    errors: list[str] = []
    for candidate in candidate_urls(url):
        tmp = dest + ".part"
        for attempt, fn in (
            ("curl", download_curl),
            ("wget", download_wget),
            ("urllib", download_urllib),
        ):
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
                fn(candidate, tmp)
                if os.path.getsize(tmp) <= 0:
                    raise OSError("empty download")
                os.replace(tmp, dest)
                return candidate
            except FileNotFoundError:
                continue
            except (subprocess.CalledProcessError, OSError, urllib.error.URLError) as exc:
                if os.path.isfile(tmp):
                    os.remove(tmp)
                errors.append(f"{attempt}@{short_url(candidate)}: {exc}")
    detail = "; ".join(errors[-6:]) if errors else "download failed"
    raise RuntimeError(detail)


errors = []
checksum_name = "checksums.txt"
checksum_url = assets_by_name.get(checksum_name) or fallback_url(checksum_name)
checksum_path = os.path.join(out_root, f"kopia-{semver}-checksums.txt")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


metadata_path = Path(out_root) / "KOPIA_INFO.json"
cached_checksum_valid = False
if not force and Path(checksum_path).is_file() and metadata_path.is_file():
    try:
        cached_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        cached_checksum_valid = (
            cached_metadata.get("repository") == repo
            and cached_metadata.get("tag") == tag
            and cached_metadata.get("checksums_sha256") == sha256_file(checksum_path)
        )
    except (OSError, json.JSONDecodeError):
        cached_checksum_valid = False

if cached_checksum_valid:
    checksum_source = "cache"
    log("SKIP ", f"Verified cached Kopia checksums {checksum_path}")
else:
    try:
        checksum_source = download_file(checksum_url, checksum_path)
    except RuntimeError as exc:
        log("FAIL ", f"Unable to download upstream Kopia checksums: {exc}")
        raise SystemExit(1) from exc

checksums: dict[str, str] = {}
for raw_line in Path(checksum_path).read_text(encoding="utf-8").splitlines():
    fields = raw_line.strip().split(None, 1)
    if len(fields) == 2 and len(fields[0]) == 64:
        checksums[fields[1].lstrip("*")] = fields[0].lower()

resolved_files: dict[str, dict[str, str]] = {}
for item in expected:
    goos, goarch, name = item["goos"], item["goarch"], item["name"]
    dest_dir = os.path.join(out_root, goos, goarch)
    dest_path = os.path.join(dest_dir, name)
    os.makedirs(dest_dir, exist_ok=True)

    url = assets_by_name.get(name) or fallback_url(name)
    expected_sha = checksums.get(name)
    if not expected_sha:
        errors.append(f"{name}: missing from upstream checksums.txt")
        continue

    log("STEP ", f"Fetching Kopia for {goos}/{goarch} ({name})")
    used = "cache"
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
        actual_sha = sha256_file(dest_path)
        if actual_sha == expected_sha:
            log("SKIP ", f"Verified cached Kopia archive {dest_path}")
        else:
            log("WARN ", f"Removing Kopia archive with checksum mismatch: {dest_path}")
            os.remove(dest_path)

    if not os.path.isfile(dest_path):
        try:
            used = download_file(url, dest_path)
        except RuntimeError as exc:
            errors.append(f"{name}: {exc}")
            continue

    actual_sha = sha256_file(dest_path)
    if actual_sha != expected_sha:
        os.remove(dest_path)
        errors.append(f"{name}: checksum mismatch (expected {expected_sha}, got {actual_sha})")
        continue
    log(" OK  ", f"Verified Kopia archive {dest_path}")
    resolved_files[f"{goos}:{goarch}"] = {
        "name": name,
        "sha256": actual_sha,
        "source_url": used,
    }

if errors:
    log("FAIL ", "One or more Kopia archives failed")
    for line in errors:
        log("FAIL ", line)
    log("INFO ", "Use --github-download-mirror explicitly or configure HTTP_PROXY/HTTPS_PROXY when required")
    sys.exit(1)

metadata = {
    "schema": 1,
    "agent_version": os.environ.get("AGENT_VERSION", ""),
    "repository": repo,
    "version": semver,
    "tag": tag,
    "matrix": [f"{item['goos']}:{item['goarch']}" for item in expected],
    "checksums_name": checksum_name,
    "checksums_sha256": sha256_file(checksum_path),
    "checksums_source_url": checksum_source,
    "files": resolved_files,
}
temporary_path = metadata_path.with_suffix(".json.tmp")
temporary_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary_path.replace(metadata_path)
log(" OK  ", f"Wrote {metadata_path}")
PY

	log_ok "Kopia archives are ready for matrix ${MATRIX}"
}

matrix_has_linux_arch() {
	local want=$1
	local item goos goarch
	for item in ${MATRIX}; do
		IFS=: read -r goos goarch <<<"${item}"
		[[ "${goos}" == "linux" && "${goarch}" == "${want}" ]] && return 0
	done
	return 1
}

resolve_nas_arches() {
	local -a arches=()
	local arch_filter="${OPT_UBUNTU2404_ARCH:-}"

	if [[ -n "${arch_filter}" ]]; then
		case "${arch_filter}" in
		all)
			matrix_has_linux_arch amd64 && arches+=(amd64)
			matrix_has_linux_arch arm64 && arches+=(arm64)
			if [[ ${#arches[@]} -eq 0 ]]; then
				arches=(amd64 arm64)
			fi
			;;
		amd64 | arm64)
			arches=("${arch_filter}")
			;;
		*)
			log_fail "Invalid Ubuntu 24.04 architecture ${arch_filter}; use amd64, arm64, or all" 2
			;;
		esac
	else
		matrix_has_linux_arch amd64 && arches+=(amd64)
		matrix_has_linux_arch arm64 && arches+=(arm64)
		if [[ ${#arches[@]} -eq 0 ]]; then
			arches=(amd64 arm64)
		fi
	fi

	sort_nas_arches "${arches[@]}"
}

sort_nas_arches() {
	local -a raw=("$@") sorted=()
	local a r
	for a in amd64 arm64; do
		for r in "${raw[@]}"; do
			if [[ "${r}" == "${a}" ]]; then
				sorted+=("${a}")
			fi
		done
	done
	((${#sorted[@]} > 0)) || return 0
	printf '%s\n' "${sorted[@]}"
}

docker_platform_for_arch() {
	case "$1" in
	amd64) echo "linux/amd64" ;;
	arm64) echo "linux/arm64" ;;
	esac
}

NAS_DOCKER_TIMEOUT=300
NAS_DOCKER_TIMEOUT_ARM64=1800
NAS_DEPS_MIN_DEBS=30
NAS_IMAGE="ubuntu:24.04"

hfl_nas_docker_script() {
	cat <<'NAS_SCRIPT'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
arch="__ARCH__"
dest="/out/${arch}"
apt_mirror="__APT_MIRROR__"
work="/tmp/hfl-nas-deps"
mkdir -p "${work}" "${dest}"
chmod 777 "${work}"
cd "${work}"

# Use HTTP for apt inside the ephemeral container (HTTPS needs ca-certificates first).
apt_mirror_http=""
if [[ -n "${apt_mirror}" ]]; then
  apt_mirror_http="${apt_mirror%/}"
  apt_mirror_http="${apt_mirror_http#https://}"
  apt_mirror_http="${apt_mirror_http#http://}"
  apt_mirror_http="http://${apt_mirror_http}"
fi

if [[ -f /etc/apt/sources.list.d/ubuntu.sources ]]; then
  sed -i 's|https://ports.ubuntu.com/ubuntu-ports|http://ports.ubuntu.com/ubuntu-ports|g' /etc/apt/sources.list.d/ubuntu.sources
  sed -i 's|https://archive.ubuntu.com/ubuntu|http://archive.ubuntu.com/ubuntu|g' /etc/apt/sources.list.d/ubuntu.sources
  sed -i 's|https://security.ubuntu.com/ubuntu|http://security.ubuntu.com/ubuntu|g' /etc/apt/sources.list.d/ubuntu.sources
fi

echo "  bootstrap: ca-certificates (default Ubuntu HTTP sources)"
if ! apt-get update -qq; then
  echo "ERROR: bootstrap apt-get update failed (${arch})" >&2
  exit 1
fi
if ! apt-get install -y --no-install-recommends ca-certificates; then
  echo "ERROR: bootstrap ca-certificates install failed (${arch})" >&2
  exit 1
fi

if [[ -n "${apt_mirror_http}" ]]; then
  m="${apt_mirror_http}"
  echo "  apt mirror: ${m} (${arch})"
  if [[ -f /etc/apt/sources.list.d/ubuntu.sources ]]; then
    if grep -q 'ports.ubuntu.com/ubuntu-ports' /etc/apt/sources.list.d/ubuntu.sources; then
      sed -i "s|http://ports.ubuntu.com/ubuntu-ports|${m}/ubuntu-ports|g" /etc/apt/sources.list.d/ubuntu.sources
    fi
    sed -i "s|http://archive.ubuntu.com/ubuntu|${m}/ubuntu|g" /etc/apt/sources.list.d/ubuntu.sources
    sed -i "s|http://security.ubuntu.com/ubuntu|${m}/ubuntu|g" /etc/apt/sources.list.d/ubuntu.sources
  fi
  if ! apt-get update -qq; then
    echo "ERROR: apt-get update failed after mirror switch (${arch})" >&2
    exit 1
  fi
fi

echo "  download: nfs-common cifs-utils (+dependencies)"
rm -f /var/cache/apt/archives/*.deb 2>/dev/null || true
apt-get install -y --download-only --no-install-recommends nfs-common cifs-utils

decode_apt_deb_name() {
  local encoded=$1 len i c h decoded=""
  len=${#encoded}
  i=0
  while (( i < len )); do
    c=${encoded:i:1}
    if [[ "${c}" == "%" && $((i + 2)) -lt len ]]; then
      h=${encoded:i+1:2}
      if [[ "${h}" =~ ^[0-9A-Fa-f]{2}$ ]]; then
        decoded+=$(printf "\\x${h}")
        i=$((i + 3))
        continue
      fi
    fi
    decoded+="${c}"
    i=$((i + 1))
  done
  printf '%s' "${decoded}"
}

rm -f "${dest}"/*.deb
shopt -s nullglob
for f in /var/cache/apt/archives/*.deb; do
  base="$(basename "${f}")"
  decoded="$(decode_apt_deb_name "${base}")"
  cp -f "${f}" "${dest}/${decoded}"
done
count="$(find "${dest}" -maxdepth 1 -name "*.deb" | wc -l | tr -d " ")"
if [[ "${count}" -lt 2 ]]; then
  echo "ERROR: expected nfs-common/cifs-utils debs under ${dest}, got ${count}" >&2
  exit 1
fi
if ! compgen -G "${dest}/nfs-common_*.deb" >/dev/null || ! compgen -G "${dest}/cifs-utils_*.deb" >/dev/null; then
  echo "ERROR: missing nfs-common or cifs-utils deb under ${dest}" >&2
  exit 1
fi
echo "  ${count} deb(s) in ${dest}"
NAS_SCRIPT
}

nas_deps_count() {
	local dest=$1
	find "${dest}" -maxdepth 1 -name '*.deb' 2>/dev/null | wc -l | tr -d ' '
}

nas_deps_cached() {
	local dest=$1 count
	[[ -d "${dest}" ]] || return 1
	# Reject URL-encoded leftovers from older fetch.sh (e.g. cifs-utils_2%3a7.0_….deb).
	compgen -G "${dest}/*%*.deb" >/dev/null && return 1
	compgen -G "${dest}/nfs-common_*.deb" >/dev/null || return 1
	compgen -G "${dest}/cifs-utils_*.deb" >/dev/null || return 1
	count="$(nas_deps_count "${dest}")"
	(( count >= NAS_DEPS_MIN_DEBS )) || return 1
}

write_nas_manifest() {
	local dest=$1
	local arch=$2
	command -v python3 >/dev/null 2>&1 || log_fail "python3 is required to write NAS dependency metadata" 2
	ARCH_VALUE="${arch}" APT_SOURCE="${APT_MIRROR:-official}" IMAGE_SOURCE="${NAS_IMAGE}" \
		python3 - "${dest}" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = {}
for path in sorted(root.glob("*.deb")):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files[path.name] = f"sha256:{digest}"
payload = {
    "schema": 1,
    "ubuntu_release": "24.04",
    "arch": os.environ["ARCH_VALUE"],
    "container_image": os.environ["IMAGE_SOURCE"],
    "apt_source": os.environ["APT_SOURCE"],
    "files": files,
}
temporary = root / "MANIFEST.json.tmp"
temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(root / "MANIFEST.json")
PY
	log_ok "Wrote ${dest}/MANIFEST.json"
}

nas_manifest_valid() {
	local dest=$1
	[[ -f "${dest}/MANIFEST.json" ]] || return 1
	python3 - "${dest}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
try:
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    expected = manifest["files"]
except (OSError, KeyError, json.JSONDecodeError, TypeError):
    raise SystemExit(1)
actual = {
    path.name: f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    for path in sorted(root.glob("*.deb"))
}
raise SystemExit(0 if actual == expected else 1)
PY
}

normalize_docker_mirror_host() {
	local mirror="${1:-}"
	mirror="${mirror#https://}"
	mirror="${mirror#http://}"
	mirror="${mirror%/}"
	printf '%s' "${mirror}"
}

pull_nas_image() {
	local platform=$1
	local mirror_host mirrored official="ubuntu:24.04"

	mirror_host="$(normalize_docker_mirror_host "${DOCKER_DOWNLOAD_MIRROR:-}")"
	mirrored=""
	if [[ -n "${mirror_host}" ]]; then
		mirrored="${mirror_host}/library/ubuntu:24.04"
	fi

	if [[ "${FORCE_PULL}" -eq 0 ]]; then
		if [[ -n "${mirrored}" ]] && nas_image_matches_platform "${mirrored}" "${platform}"; then
			NAS_IMAGE="${mirrored}"
			log_skip "Using local ${NAS_IMAGE} for ${platform}"
			return 0
		fi
		if nas_image_matches_platform "${official}" "${platform}"; then
			NAS_IMAGE="${official}"
			log_skip "Using local ${NAS_IMAGE} for ${platform}"
			return 0
		fi
	fi

	if [[ -n "${mirrored}" ]]; then
		log_step "Pulling ${mirrored} for ${platform} (timeout=${DOCKER_PULL_TIMEOUT_SECONDS}s)"
		if timeout --foreground "${DOCKER_PULL_TIMEOUT_SECONDS}s" \
			docker pull --platform "${platform}" "${mirrored}"; then
			NAS_IMAGE="${mirrored}"
			return 0
		fi
		log_warn "Docker mirror pull failed; trying the official registry"
	fi

	log_step "Pulling ${official} for ${platform} (timeout=${DOCKER_PULL_TIMEOUT_SECONDS}s)"
	if timeout --foreground "${DOCKER_PULL_TIMEOUT_SECONDS}s" \
		docker pull --platform "${platform}" "${official}"; then
		NAS_IMAGE="${official}"
		return 0
	fi
	if nas_image_matches_platform "${official}" "${platform}"; then
		NAS_IMAGE="${official}"
		log_warn "Registry refresh failed; using existing local ${NAS_IMAGE}"
		return 0
	fi
	if [[ -n "${mirrored}" ]] && nas_image_matches_platform "${mirrored}" "${platform}"; then
		NAS_IMAGE="${mirrored}"
		log_warn "Registry refresh failed; using existing local ${NAS_IMAGE}"
		return 0
	fi

	log_warn "Failed to pull ubuntu:24.04 for ${platform}"
	log_info "Optional mirror example: --docker-download-mirror docker.m.daocloud.io --apt-mirror https://mirrors.tuna.tsinghua.edu.cn"
	return 1
}

nas_image_matches_platform() {
	local image=$1 platform=$2 expected_arch actual
	case "${platform}" in
	linux/amd64) expected_arch=amd64 ;;
	linux/arm64) expected_arch=arm64 ;;
	*) return 1 ;;
	esac
	actual="$(docker image inspect "${image}" --format '{{.Os}}/{{.Architecture}}' 2>/dev/null || true)"
	[[ "${actual}" == "linux/${expected_arch}" ]]
}

fetch_nas_deps() {
	local out_root="${NAS_DEPS_ROOT}"

	fetch_arch_docker() {
		local arch=$1
		local platform
		platform="$(docker_platform_for_arch "${arch}")"

		local dest="${out_root}/${arch}"
		mkdir -p "${dest}"

		if nas_deps_cached "${dest}" && [[ "${FORCE}" -eq 0 ]]; then
			if nas_manifest_valid "${dest}"; then
				log_skip "Verified cached NAS dependencies for ${arch} ($(nas_deps_count "${dest}") packages)"
				return 0
			fi
			log_warn "Cached NAS dependency manifest is missing or invalid for ${arch}; refreshing"
		fi

		if [[ "${FORCE}" -eq 1 ]]; then
			rm -f "${dest}"/*.deb 2>/dev/null || true
		elif compgen -G "${dest}/*.deb" >/dev/null; then
			log_warn "Incomplete NAS dependency cache under ${dest}; refreshing"
			rm -f "${dest}"/*.deb 2>/dev/null || true
		fi

		if ! command -v docker >/dev/null 2>&1; then
			log_warn "Docker is required to fetch Ubuntu NAS dependencies for ${arch}"
			return 2
		fi
		command -v timeout >/dev/null 2>&1 \
			|| { log_warn "timeout is required to pull NAS dependency images"; return 2; }

		if ! pull_nas_image "${platform}"; then
			return 1
		fi

		if ! docker run --rm --pull=never --platform "${platform}" "${NAS_IMAGE}" true >/dev/null 2>&1; then
			log_warn "Docker platform ${platform} is unavailable on this host"
			if [[ "${arch}" == "arm64" ]]; then
				log_info "arm64 on amd64 requires QEMU binfmt; install it explicitly before retrying"
			fi
			return 2
		fi

		log_step "Fetching NAS dependencies in ${NAS_IMAGE} for ${arch}"
		local docker_timeout="${NAS_DOCKER_TIMEOUT}"
		if [[ "${arch}" == "arm64" ]]; then
			docker_timeout="${NAS_DOCKER_TIMEOUT_ARM64}"
			log_info "NAS dependency timeout: ${docker_timeout}s (arm64 under QEMU can be slow)"
		else
			log_info "NAS dependency timeout: ${docker_timeout}s"
		fi

		local container_name="hfl-nas-deps-${arch}-$$"
		local inner_script script_file exit_code
		inner_script="$(hfl_nas_docker_script)"
		inner_script="${inner_script//__ARCH__/${arch}}"
		inner_script="${inner_script//__APT_MIRROR__/${APT_MIRROR:-}}"

		script_file="$(mktemp)"
		printf '%s\n' "${inner_script}" > "${script_file}"

		hfl_nas_docker_stop() {
			rm -f "${script_file}"
			docker rm -f "${container_name}" >/dev/null 2>&1 || true
			trap - INT TERM
		}

		hfl_nas_docker_interrupt() {
			log_warn "Interrupted; stopping ${container_name}"
			hfl_nas_docker_stop
			exit 130
		}
		trap hfl_nas_docker_interrupt INT TERM

		docker rm -f "${container_name}" >/dev/null 2>&1 || true
		if ! docker run -d --init --name "${container_name}" \
			--platform "${platform}" \
			-e DEBIAN_FRONTEND=noninteractive \
			-e "APT_MIRROR=${APT_MIRROR:-}" \
			"${NAS_IMAGE}" \
			sleep infinity; then
			hfl_nas_docker_stop
			log_warn "Failed to start NAS fetch container for ${arch}"
			return 1
		fi

		if ! docker cp "${script_file}" "${container_name}:/tmp/fetch-nas-debs.sh"; then
			hfl_nas_docker_stop
			log_warn "Failed to copy NAS fetch script into the container for ${arch}"
			return 1
		fi

		exit_code=0
		set +e
		if command -v timeout >/dev/null 2>&1; then
			timeout "${docker_timeout}" docker exec "${container_name}" bash /tmp/fetch-nas-debs.sh
			exit_code=$?
		else
			docker exec "${container_name}" bash /tmp/fetch-nas-debs.sh
			exit_code=$?
		fi
		set -e

		if [[ "${exit_code}" -eq 124 ]]; then
			log_warn "Docker fetch for ${arch} timed out after ${docker_timeout}s"
			log_info "For slow QEMU builds, retry with --apt-mirror https://mirrors.tuna.tsinghua.edu.cn or select --ubuntu2404-arch amd64"
			hfl_nas_docker_stop
			return 1
		fi

		if [[ "${exit_code}" == "0" ]]; then
			rm -f "${dest}"/*.deb 2>/dev/null || true
			if ! docker cp "${container_name}:/out/${arch}/." "${dest}/"; then
				hfl_nas_docker_stop
				log_warn "Failed to copy NAS debs from the container to ${dest}"
				return 1
			fi
		fi

		hfl_nas_docker_stop

		if [[ "${exit_code}" != "0" ]]; then
			log_warn "NAS fetch container for ${arch} exited with status ${exit_code}"
			log_info "Retry from the repository root with ./src/agent/scripts/fetch-deps.sh --nas-deps --ubuntu2404-arch ${arch} --force --docker-download-mirror ${DOCKER_DOWNLOAD_MIRROR:-docker.m.daocloud.io} --apt-mirror ${APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn}"
			return 1
		fi

		if ! nas_deps_cached "${dest}"; then
			log_warn "${arch} fetch finished but ${dest} is incomplete ($(nas_deps_count "${dest}") packages)"
			return 1
		fi
		write_nas_manifest "${dest}" "${arch}"
		log_ok "NAS dependencies for ${arch} are ready ($(nas_deps_count "${dest}") packages under ${dest})"
	}

	local -a arches=()
	local arch
	while IFS= read -r arch; do
		arches+=("${arch}")
	done < <(resolve_nas_arches)

	log_info "NAS dependency target architectures: ${arches[*]} (Docker ubuntu:24.04; host apt is not used)"

	local -a failed_arches=() ok_arches=()
	for arch in "${arches[@]}"; do
		if fetch_arch_docker "${arch}"; then
			ok_arches+=("${arch}")
		else
			failed_arches+=("${arch}")
			if [[ "${arch}" == "amd64" ]] && printf ' %s ' "${arches[*]}" | grep -q ' arm64 '; then
				log_warn "amd64 failed; arm64 under QEMU can be slow, so fix amd64 first or run --ubuntu2404-arch arm64 separately"
			fi
		fi
	done

	if ((${#failed_arches[@]} > 0)); then
		((${#ok_arches[@]} > 0)) && log_info "NAS dependency fetch succeeded for: ${ok_arches[*]}"
		log_fail "NAS dependency fetch failed for: ${failed_arches[*]}"
	fi

	log_ok "NAS dependency packages are ready under ${out_root}"
}

validate_matrix

if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
	print_config
	exit 0
fi

setup_log_file
trap finish_session EXIT
trap 'exit 130' INT TERM
SESSION_STARTED=1

log_info "Agent dependency fetch session started"
if [[ "${DO_KOPIA}" -eq 1 ]]; then
	fetch_kopia
fi
if [[ "${DO_NAS}" -eq 1 ]]; then
	fetch_nas_deps
fi

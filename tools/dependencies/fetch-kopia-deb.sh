#!/usr/bin/env bash
# Download the Kopia linux-amd64 .deb for deploy/docker/backend.Dockerfile (Ubuntu 24.04; gitignored).
# Mirror and retry logic aligned with src/agent/scripts/fetch-deps.sh (--kopia).
#
# Usage:
#   ./tools/dependencies/fetch-kopia-deb.sh
#   ./tools/dependencies/fetch-kopia-deb.sh --force
#   ./tools/dependencies/fetch-kopia-deb.sh --kopia-version 0.23.0 --github-download-mirror https://ghfast.top
#
set -euo pipefail
umask 022

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KOPIA_DIR="${ROOT}/build/dependencies/kopia"
GITHUB_REPO="kopia/kopia"
# shellcheck source=../lib/logging.sh
source "${ROOT}/tools/lib/logging.sh"

require_value() {
	hfl_require_value "$1" "${2:-}"
}

usage() {
	cat <<USAGE
Usage: ./tools/dependencies/fetch-kopia-deb.sh [options]

Role: download Kopia linux-amd64 .deb for backend Docker image (ubuntu:24.04; no image build).

Output:
  build/dependencies/kopia/kopia_linux_amd64.deb
  Version from tools/dependencies/versions/kopia.env unless --kopia-version is set.

Options:
  --kopia-version VERSION          Kopia version without v prefix (env: KOPIA_VERSION)
  --github-download-mirror URL     GitHub download mirror (env: GITHUB_DOWNLOAD_MIRROR)
  --github-token TOKEN             GitHub API token (env: GITHUB_TOKEN)
  --force                          Re-download even when cached
  --log-file FILE                  Append runtime logs to FILE
  --verbose                        Enable debug logs
  --print-config                   Print effective non-secret configuration and exit
  -h, --help                       Show this help

Examples:
  ./tools/dependencies/fetch-kopia-deb.sh
  ./tools/dependencies/fetch-kopia-deb.sh --force
  ./tools/dependencies/fetch-kopia-deb.sh --github-download-mirror https://ghfast.top
  ./tools/dependencies/fetch-kopia-deb.sh --kopia-version 0.23.0 --github-download-mirror URL
USAGE
}

FORCE=0
OPT_KOPIA_VERSION=""
OPT_GITHUB_DOWNLOAD_MIRROR=""
OPT_GITHUB_TOKEN=""
LOG_FILE="${HFL_LOG_FILE:-}"
VERBOSE="${HFL_LOG_VERBOSE:-0}"
PRINT_CONFIG=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	--force)
		FORCE=1
		shift
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

command -v python3 >/dev/null 2>&1 || hfl_die "python3 not found" 2
command -v curl >/dev/null 2>&1 || hfl_die "curl not found" 2
command -v sha256sum >/dev/null 2>&1 || hfl_die "sha256sum not found" 2

# shellcheck source=versions/kopia.env
source "${ROOT}/tools/dependencies/versions/kopia.env"
KOPIA_VERSION="${OPT_KOPIA_VERSION:-${KOPIA_VERSION}}"
[[ "${KOPIA_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
	|| hfl_die "Invalid Kopia version: ${KOPIA_VERSION}" 2
GITHUB_DOWNLOAD_MIRROR="${OPT_GITHUB_DOWNLOAD_MIRROR:-${GITHUB_DOWNLOAD_MIRROR:-}}"
GITHUB_TOKEN="${OPT_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"

TAG="v${KOPIA_VERSION#v}"
DEB_NAME="kopia_${KOPIA_VERSION#v}_linux_amd64.deb"
DEST="${KOPIA_DIR}/kopia_linux_amd64.deb"
MANIFEST="${KOPIA_DIR}/MANIFEST.json"

mkdir -p "${KOPIA_DIR}"

print_config() {
	cat <<EOF
kopia_version=${KOPIA_VERSION}
github_tag=${TAG}
output=${DEST}
github_download_mirror=${GITHUB_DOWNLOAD_MIRROR:-<official>}
github_token=$(hfl_redact "${GITHUB_TOKEN}")
force=${FORCE}
log_file=${LOG_FILE:-<none>}
verbose=${VERBOSE}
EOF
}

hfl_logging_configure kopia-dependency "${LOG_FILE}" "${VERBOSE}"
if [[ "${PRINT_CONFIG}" -eq 1 ]]; then
	print_config
	exit 0
fi
trap 'rc=$?; hfl_logging_finish "${rc}"' EXIT
trap 'exit 130' INT TERM
hfl_logging_start
hfl_log_info "Kopia release: ${TAG}"

if [[ "${FORCE}" -eq 0 && -s "${DEST}" && -s "${MANIFEST}" ]]; then
	cached_sha="$(python3 - "${MANIFEST}" "${KOPIA_VERSION}" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    if data.get("version") == sys.argv[2]:
        print(data["sha256"])
except (OSError, KeyError, json.JSONDecodeError):
    pass
PY
)"
	actual_cached_sha="$(sha256sum "${DEST}" | awk '{print $1}')"
	if [[ -n "${cached_sha}" && "${cached_sha,,}" == "${actual_cached_sha,,}" ]]; then
		hfl_log_skip "Using verified cached ${DEB_NAME} at ${DEST}"
		exit 0
	fi
	hfl_log_warn "Cached Kopia artifact failed manifest validation; downloading it again"
fi

if [[ "${FORCE}" -eq 1 && -f "${DEST}" ]]; then
	rm -f "${DEST}" "${MANIFEST}"
fi

api_headers=(-fsSL -H "Accept: application/vnd.github+json" -H "User-Agent: hyperfilelens-kopia-deb-fetch/1.0")
if [[ -n "${GITHUB_TOKEN}" ]]; then
	api_headers+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
fi

RELEASE_JSON=""
if RELEASE_JSON="$(curl "${api_headers[@]}" "https://api.github.com/repos/${GITHUB_REPO}/releases/tags/${TAG}" 2>/dev/null)"; then
	:
else
	RELEASE_JSON=""
fi

DEB_NAME="$DEB_NAME" TAG="$TAG" DEST="$DEST" \
	RELEASE_JSON="$RELEASE_JSON" GITHUB_DOWNLOAD_MIRROR="$GITHUB_DOWNLOAD_MIRROR" \
	python3 - <<'PY'
import json
import datetime
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse

USER_AGENT = "hyperfilelens-kopia-deb-fetch/1.0"
AUTO_MIRRORS: tuple[str, ...] = ()

deb_name = os.environ["DEB_NAME"]
tag = os.environ["TAG"]
repo = "kopia/kopia"
dest = os.environ["DEST"]
release_json = os.environ.get("RELEASE_JSON", "")
auto_mirror = True


def emit(level: str, message: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
    now = now.replace("+00:00", "Z")
    print(f"[{now}] [{level:<5}] {message}", file=sys.stderr)


def proxy_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(key, "").strip()
        if val:
            out[key] = val
    return out


def fallback_url() -> str:
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(tag, safe='')}/{quote(deb_name, safe='')}"
    )


def resolve_url() -> str:
    if release_json.strip():
        try:
            data = json.loads(release_json)
            for asset in data.get("assets") or []:
                if asset.get("name") == deb_name:
                    url = (asset.get("browser_download_url") or "").strip()
                    if url:
                        return url
        except json.JSONDecodeError:
            pass
    return fallback_url()


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
    if auto_mirror:
        for prefix in AUTO_MIRRORS:
            mirrored = f"{prefix.rstrip('/')}/{url}"
            if mirrored not in seen:
                add(mirrored)
    return ordered


def short_url(url: str) -> str:
    if len(url) <= 88:
        return url
    parsed = urlparse(url)
    if parsed.netloc in ("github.com", "release-assets.githubusercontent.com"):
        return f"...github.com/.../{parsed.path.rsplit('/', 1)[-1]}"
    return url[:40] + "..." + url[-40:]


def download_curl(url: str, dest_path: str) -> None:
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
        dest_path,
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True, env={**os.environ, **proxy_env()})


def download_wget(url: str, dest_path: str) -> None:
    if not shutil.which("wget"):
        raise FileNotFoundError("wget not found")
    subprocess.run(
        ["wget", "-q", "--timeout=30", "-O", dest_path, url],
        check=True,
        capture_output=True,
        env={**os.environ, **proxy_env()},
    )


def download_urllib(url: str, dest_path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        with open(dest_path, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)


def download_file(url: str, dest_path: str) -> str:
    errors: list[str] = []
    for candidate in candidate_urls(url):
        tmp = dest_path + ".part"
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
                os.replace(tmp, dest_path)
                return candidate
            except FileNotFoundError:
                continue
            except (subprocess.CalledProcessError, OSError, urllib.error.URLError) as exc:
                if os.path.isfile(tmp):
                    os.remove(tmp)
                errors.append(f"{attempt}@{short_url(candidate)}: {exc}")
    detail = "; ".join(errors[-6:]) if errors else "download failed"
    raise RuntimeError(detail)


source_url = resolve_url()
emit("STEP", f"Downloading {deb_name}")
emit("INFO", f"Source: {short_url(source_url)}")
try:
    used = download_file(source_url, dest)
except RuntimeError as exc:
    emit("FAIL", f"Download failed: {exc}")
    emit("INFO", "Set GITHUB_TOKEN for API rate limits, an explicit GitHub mirror for restricted networks, or HTTP_PROXY/HTTPS_PROXY when required")
    sys.exit(1)

size_mb = os.path.getsize(dest) / (1024 * 1024)
emit(" OK ", f"Downloaded {dest} ({size_mb:.1f} MiB)")
if used != source_url:
    emit("INFO", f"Mirror used: {short_url(used)}")
PY

fetch_checksums() {
	local official="https://github.com/${GITHUB_REPO}/releases/download/${TAG}/checksums.txt"
	local target="${KOPIA_DIR}/checksums.txt.part"
	local -a urls=()
	[[ -n "${GITHUB_DOWNLOAD_MIRROR}" ]] && urls+=("${GITHUB_DOWNLOAD_MIRROR%/}/${official}")
	urls+=("${official}")
	local url
	local -a headers=(-fsSL --connect-timeout 30 --retry 2 -H "User-Agent: hyperfilelens-kopia-deb-fetch/1.0")
	[[ -n "${GITHUB_TOKEN}" ]] && headers+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
	for url in "${urls[@]}"; do
		if curl "${headers[@]}" -o "${target}" "${url}"; then
			printf '%s' "${target}"
			return 0
		fi
	done
	return 1
}

checksums_file="$(fetch_checksums)" || hfl_die "Unable to download Kopia checksums.txt" 1
expected_sha="$(awk -v name="${DEB_NAME}" '{file=$2; sub(/^\\*/, "", file); if (file == name) {print $1; exit}}' "${checksums_file}")"
[[ "${expected_sha}" =~ ^[0-9a-fA-F]{64}$ ]] || hfl_die "No checksum found for ${DEB_NAME}" 1
actual_sha="$(sha256sum "${DEST}" | awk '{print $1}')"
if [[ "${actual_sha,,}" != "${expected_sha,,}" ]]; then
	rm -f "${DEST}" "${checksums_file}"
	hfl_die "Checksum verification failed for ${DEB_NAME}" 1
fi
rm -f "${checksums_file}"

python3 - "${MANIFEST}.part" "$(basename "${DEST}")" "${DEB_NAME}" "${KOPIA_VERSION}" "${actual_sha}" "$(wc -c <"${DEST}")" <<'PY'
import json
import pathlib
import sys

out, filename, source_asset, version, sha256, size = sys.argv[1:7]
payload = {
    "product": "kopia",
    "version": version,
    "file": filename,
    "source_asset": source_asset,
    "size": int(size),
    "sha256": sha256,
}
pathlib.Path(out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
mv -f "${MANIFEST}.part" "${MANIFEST}"
hfl_log_ok "Verified and cached ${DEB_NAME}"

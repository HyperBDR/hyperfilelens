#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
# shellcheck source=../../../../tools/dependencies/versions/kopia.env
source "${REPO_ROOT}/tools/dependencies/versions/kopia.env"
EXPECTED_KOPIA_VERSION="${KOPIA_VERSION#v}"

KOPIA_BIN="${HFL_KOPIA_PATH:-${1:-}}"
if [[ -z "${KOPIA_BIN}" ]]; then
	KOPIA_BIN="$(command -v kopia || true)"
fi
if [[ -z "${KOPIA_BIN}" || ! -x "${KOPIA_BIN}" ]]; then
	echo "ERROR: set HFL_KOPIA_PATH or pass the Kopia binary path" >&2
	exit 2
fi

version="$(${KOPIA_BIN} --version)"
if [[ "${version}" != *"${EXPECTED_KOPIA_VERSION}"* ]]; then
	echo "ERROR: expected Kopia ${EXPECTED_KOPIA_VERSION}, got: ${version}" >&2
	exit 2
fi

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/hfl-kopia-compression.XXXXXX")"
trap 'rm -rf "${work_dir}"' EXIT

repository_dir="${work_dir}/repository"
source_dir="${work_dir}/source"
config_file="${work_dir}/repository.config"
mkdir -p "${repository_dir}" "${source_dir}" "${work_dir}/home" "${work_dir}/cache"
dd if=/dev/zero of="${source_dir}/compressible.bin" bs=1024 count=8 status=none

export HOME="${work_dir}/home"
export XDG_CACHE_HOME="${work_dir}/cache"
export KOPIA_CACHE_DIRECTORY="${work_dir}/cache"
export KOPIA_PASSWORD="hfl-integration-password"
export KOPIA_CHECK_FOR_UPDATES="false"
export KOPIA_USE_KEYRING="false"
export KOPIA_PERSIST_CREDENTIALS_ON_CONNECT="false"

never_extensions=(
	.7z .aac .apk .avi .bz2 .flac .gif .gz .heic .heif .iso .jpeg .jpg
	.m4a .mkv .mov .mp3 .mp4 .mpeg .mpg .ogg .pdf .png .rar .tgz .webp
	.xz .zip .zst
)
never_extensions_csv="$(IFS=,; printf '%s' "${never_extensions[*]}")"

kopia() {
	"${KOPIA_BIN}" --config-file="${config_file}" "$@"
}

reset_policy() {
	kopia policy set \
		--clear-ignore \
		--clear-dot-ignore \
		--clear-only-compress \
		--clear-never-compress \
		"${source_dir}" >/dev/null
}

apply_policy() {
	local compressor=$1
	local minimum_size=$2
	shift 2
	local -a args=(
		policy set
		--max-file-size=0
		--ignore-cache-dirs=false
		--one-file-system=false
		--ignore-file-errors=false
		--ignore-dir-errors=false
		--ignore-unknown-types=false
		"--compression=${compressor}"
		"--compression-min-size=${minimum_size}"
		--compression-max-size=0
	)
	local extension
	for extension in "$@"; do
		args+=("--add-never-compress=${extension}")
	done
	args+=("${source_dir}")
	kopia "${args[@]}" >/dev/null
}

assert_policy() {
	local expected_compressor=$1
	local expected_minimum=$2
	local expected_extensions=$3
	local policy_json
	policy_json="$(kopia policy show --json "${source_dir}")"
	POLICY_JSON="${policy_json}" \
	EXPECTED_COMPRESSOR="${expected_compressor}" \
	EXPECTED_MINIMUM="${expected_minimum}" \
	EXPECTED_EXTENSIONS="${expected_extensions}" \
	python3 - <<'PY'
import json
import os

policy = json.loads(os.environ["POLICY_JSON"])
compression = policy.get("compression") or {}
expected_compressor = os.environ["EXPECTED_COMPRESSOR"]
expected_minimum = int(os.environ["EXPECTED_MINIMUM"])
expected_extensions = [item for item in os.environ["EXPECTED_EXTENSIONS"].split(",") if item]

assert compression.get("compressorName") == expected_compressor, compression
assert int(compression.get("minSize") or 0) == expected_minimum, compression
assert int(compression.get("maxSize") or 0) == 0, compression
assert compression.get("onlyCompress") in (None, []), compression
actual_extensions = compression.get("neverCompress") or []
assert sorted(actual_extensions) == sorted(expected_extensions), compression
PY
}

kopia repository create filesystem --path="${repository_dir}" >/dev/null

reset_policy
apply_policy zstd 4096 "${never_extensions[@]}"
assert_policy zstd 4096 "${never_extensions_csv}"
kopia snapshot create "${source_dir}" --json >/dev/null

reset_policy
apply_policy zstd-better-compression 4096 "${never_extensions[@]}"
assert_policy zstd-better-compression 4096 "${never_extensions_csv}"
kopia snapshot create "${source_dir}" --json >/dev/null

reset_policy
apply_policy none 0
assert_policy none 0 ""

echo "Kopia ${version}: compression policy integration passed"

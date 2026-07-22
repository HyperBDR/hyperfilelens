#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

default_config="$("${ROOT}/tools/kopia/prepare.sh" --print-config)"
grep -F 'mode=build' <<<"${default_config}" >/dev/null
grep -F 'git_url=https://github.com/kopia/kopia.git' <<<"${default_config}" >/dev/null
grep -F 'git_ref=v0.23.1' <<<"${default_config}" >/dev/null
grep -F 'version=0.23.1' <<<"${default_config}" >/dev/null

environment_config="$(
	KOPIA_ARTIFACT_MODE=download KOPIA_GIT_REF=v0.23.1 \
		"${ROOT}/tools/kopia/prepare.sh" --print-config
)"
grep -F 'mode=download' <<<"${environment_config}" >/dev/null

cli_config="$(
	KOPIA_ARTIFACT_MODE=download \
		"${ROOT}/tools/kopia/prepare.sh" --kopia-mode build --kopia-ref v0.23.1 --print-config
)"
grep -F 'mode=build' <<<"${cli_config}" >/dev/null
grep -F 'version=0.23.1' <<<"${cli_config}" >/dev/null

mirror_config="$(
	"${ROOT}/tools/kopia/prepare.sh" \
		--github-download-mirror https://ghfast.top --print-config
)"
grep -F 'git_url=https://github.com/kopia/kopia.git' <<<"${mirror_config}" >/dev/null
grep -F 'github_download_mirror=https://ghfast.top' <<<"${mirror_config}" >/dev/null

# shellcheck source=../kopia/prepare.sh
source "${ROOT}/tools/kopia/prepare.sh"

GITHUB_DOWNLOAD_MIRROR=https://ghfast.top/
mirror_candidates="$(git_source_candidates 'https://github.com/kopia/kopia.git')"
[[ "${mirror_candidates}" == $'https://ghfast.top/https://github.com/kopia/kopia.git\nhttps://github.com/kopia/kopia.git' ]]
custom_candidates="$(git_source_candidates 'https://git.example.test/kopia.git')"
[[ "${custom_candidates}" == 'https://git.example.test/kopia.git' ]]

mirror_test_root="$(mktemp -d)"
trap 'rm -rf "${mirror_test_root}"' EXIT
fixture_repo="${mirror_test_root}/fixture"
git init -q "${fixture_repo}"
git -C "${fixture_repo}" config user.email test@hyperfilelens.local
git -C "${fixture_repo}" config user.name 'HyperFileLens Test'
printf '%s\n' 'module example.test/kopia-fixture' >"${fixture_repo}/go.mod"
git -C "${fixture_repo}" add go.mod
git -C "${fixture_repo}" commit -q -m fixture
git -C "${fixture_repo}" tag v0.23.1
fixture_commit="$(git -C "${fixture_repo}" rev-parse HEAD)"

KOPIA_BUILD_DIR="${mirror_test_root}/build"
KOPIA_SOURCE_DIR="${KOPIA_BUILD_DIR}/source"
KOPIA_GIT_URL=https://github.com/kopia/kopia.git
KOPIA_GIT_REF=v0.23.1
GITHUB_DOWNLOAD_MIRROR=https://ghfast.top
GITHUB_TOKEN=
OFFLINE=0
FORCE=0
git_call_log="${mirror_test_root}/git-calls.log"
mirror_git_url="${GITHUB_DOWNLOAD_MIRROR}/${KOPIA_GIT_URL}"

git_with_auth() {
	local -a args=("$@")
	local index
	printf '%s\n' "$*" >>"${git_call_log}"
	for index in "${!args[@]}"; do
		if [[ "${args[${index}]}" == "${mirror_git_url}" ]]; then
			return 1
		fi
		if [[ "${args[${index}]}" == "${KOPIA_GIT_URL}" ]]; then
			args[${index}]="${fixture_repo}"
		fi
	done
	command git "${args[@]}"
}

sync_source
mirror_call_count="$(awk -v url="${mirror_git_url}" '{ for (i = 1; i <= NF; i++) if ($i == url) count++ } END { print count + 0 }' "${git_call_log}")"
official_call_count="$(awk -v url="${KOPIA_GIT_URL}" '{ for (i = 1; i <= NF; i++) if ($i == url) count++ } END { print count + 0 }' "${git_call_log}")"
[[ "${mirror_call_count}" -eq 2 ]]
[[ "${official_call_count}" -eq 2 ]]
[[ "$(git -C "${KOPIA_SOURCE_DIR}" config --get remote.origin.url)" == "${KOPIA_GIT_URL}" ]]
[[ "${KOPIA_GIT_COMMIT}" == "${fixture_commit}" ]]

# Normalize caches created by the previous explicit mirror workaround without
# changing the canonical KOPIA_GIT_URL or requiring network access.
git -C "${KOPIA_SOURCE_DIR}" remote set-url origin "${mirror_git_url}"
OFFLINE=1
sync_source
[[ "$(git -C "${KOPIA_SOURCE_DIR}" config --get remote.origin.url)" == "${KOPIA_GIT_URL}" ]]

[[ ! -e "${ROOT}/tools/dependencies/versions/kopia.env" ]]
[[ ! -e "${ROOT}/tools/dependencies/fetch-kopia-deb.sh" ]]
if rg -n --glob '!build/**' --glob '!data/**' \
	--glob '!tools/quality/test-kopia-build-config.sh' -- \
	'--kopia-version|KOPIA_DEB|kopia_linux_amd64[.]deb|tools/dependencies/versions/kopia[.]env' \
	"${ROOT}" >/dev/null; then
	printf 'ERROR: obsolete Kopia version or deb configuration is still referenced\n' >&2
	exit 1
fi

grep -F 'URLStyleVirtualHosted = "virtual-hosted"' \
	"${ROOT}/tools/kopia/patches/0001-add-s3-url-style.patch" >/dev/null
grep -F 'BucketLookup: bucketLookup' \
	"${ROOT}/tools/kopia/patches/0001-add-s3-url-style.patch" >/dev/null

printf 'Kopia build configuration checks passed.\n'

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

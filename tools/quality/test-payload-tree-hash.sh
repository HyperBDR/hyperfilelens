#!/usr/bin/env bash
# Verify release payload tree hashes are stable across host locales.
set -euo pipefail
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

fixture="${tmp}/payload"
mkdir -p "${fixture}/media/agent-releases/0.1.4"
printf 'standard\n' >"${fixture}/media/agent-releases/0.1.4/hfl-agent-0.1.4-linux-amd64.tar.gz"
printf 'ubuntu-2004\n' >"${fixture}/media/agent-releases/0.1.4/hfl-agent-0.1.4-linux-amd64-ubuntu2004.tar.gz"
printf 'ubuntu-2204\n' >"${fixture}/media/agent-releases/0.1.4/hfl-agent-0.1.4-linux-amd64-ubuntu2204.tar.gz"
printf 'ubuntu-2404\n' >"${fixture}/media/agent-releases/0.1.4/hfl-agent-0.1.4-linux-amd64-ubuntu2404.tar.gz"

reference="$({
	cd "${fixture}"
	export LC_ALL=C
	find . -type f ! -path './__pycache__/*' ! -name '*.pyc' -print0 \
		| sort -z \
		| xargs -0 sha256sum \
		| sha256sum \
		| awk '{print $1}'
})"

test_locale="$(locale -a | awk 'tolower($0) ~ /^en_us([.]utf-?8)?$/ { print; exit }')"
[[ -n "${test_locale}" ]] || test_locale=C.UTF-8

for source in "${ROOT}/release/build.sh" "${ROOT}/deploy/installer/install.sh"; do
	function_file="${tmp}/$(basename "$(dirname "${source}")")-tree-sha256.sh"
	sed -n '/^tree_sha256()/,/^}/p' "${source}" >"${function_file}"
	grep -F 'export LC_ALL=C' "${function_file}" >/dev/null || {
		printf 'ERROR: tree_sha256 does not force C locale in %s\n' "${source}" >&2
		exit 1
	}
	actual="$(
		# shellcheck disable=SC1090
		source "${function_file}"
		LC_ALL="${test_locale}" tree_sha256 "${fixture}"
	)"
	[[ "${actual}" == "${reference}" ]] || {
		printf 'ERROR: locale-dependent tree hash in %s (%s != %s)\n' \
			"${source}" "${actual}" "${reference}" >&2
		exit 1
	}
done

printf 'Portable payload tree hash checks passed (%s caller locale).\n' "${test_locale}"

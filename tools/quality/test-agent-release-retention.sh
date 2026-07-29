#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

ROOT="${tmp}/install"
LOCAL_PLATFORM_AGENT_INSTALL_DIR="${tmp}/agent-install"
releases="${ROOT}/data/media/agent-releases"
mkdir -p "${releases}" "${LOCAL_PLATFORM_AGENT_INSTALL_DIR}"
printf 'main-1111111\n' >"${ROOT}/VERSION"
printf '0.1.0\n' >"${LOCAL_PLATFORM_AGENT_INSTALL_DIR}/INSTALLED_VERSION"
printf 'main-2222222\n' >"${ROOT}/data/.platform-gateway-agent-upgrade"

for version in main-1111111 main-2222222 main-3333333 main-4444444 main-5555555; do
	mkdir -p "${releases}/${version}"
	printf '%s\n' "${version}" >"${releases}/${version}/fixture"
done
touch -d '5 days ago' "${releases}/main-1111111"
touch -d '4 days ago' "${releases}/main-2222222"
touch -d '3 days ago' "${releases}/main-3333333"
touch -d '2 days ago' "${releases}/main-4444444"
touch -d '1 day ago' "${releases}/main-5555555"

for version in 0.1.0 0.1.1 0.1.2 0.1.3 0.1.4; do
	mkdir -p "${releases}/${version}"
	printf '%s\n' "${version}" >"${releases}/${version}/fixture"
done
mkdir -p "${releases}/unrecognized"
ln -s "${releases}/0.1.4" "${releases}/main-abcdef0-link"

read_version() { tr -d ' \t\r\n' <"${ROOT}/VERSION"; }
warn() { printf 'WARN: %s\n' "$*" >>"${tmp}/retention.log"; }
log() { printf 'INFO: %s\n' "$*" >>"${tmp}/retention.log"; }
die() { printf 'ERROR: %s\n' "$1" >&2; return "${2:-1}"; }
# shellcheck disable=SC1090
source <(sed -n '/^safe_normalize_dir()/,/^# --- Host \/ Docker ---/p' "${installer}" | sed '$d')
# shellcheck disable=SC1090
source <(sed -n '/^prune_agent_release_media()/,/^ensure_tls_certs()/p' "${installer}" | sed '$d')

prune_agent_release_media

for retained in \
	main-1111111 main-2222222 main-4444444 main-5555555 \
	0.1.0 0.1.2 0.1.3 0.1.4 unrecognized main-abcdef0-link; do
	[[ -e "${releases}/${retained}" || -L "${releases}/${retained}" ]]
done
for removed in main-3333333 0.1.1; do
	[[ ! -e "${releases}/${removed}" ]]
done
grep -F 'Retaining unrecognized or unsafe Agent release media entry unrecognized' \
	"${tmp}/retention.log" >/dev/null
grep -F 'Retaining unrecognized or unsafe Agent release media entry main-abcdef0-link' \
	"${tmp}/retention.log" >/dev/null

printf 'Agent release media retention checks passed.\n'

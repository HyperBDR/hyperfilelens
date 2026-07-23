#!/usr/bin/env bash
# Execute one Ubuntu-specific Agent bundle with its debs and networking disabled.
set -euo pipefail

[[ $# -eq 3 ]] || {
	printf 'Usage: %s INTERNAL_AGENT_BUNDLE VERSION UBUNTU_RELEASE\n' "$0" >&2
	exit 2
}
internal_bundle=$1
version=${2#v}
ubuntu_release=$3
case "${ubuntu_release}" in
20.04) flavor=ubuntu2004 ;;
24.04) flavor=ubuntu2404 ;;
*) printf 'ERROR: unsupported Ubuntu release: %s\n' "${ubuntu_release}" >&2; exit 2 ;;
esac
[[ -s "${internal_bundle}" ]] \
	|| { printf 'ERROR: internal Agent bundle is missing\n' >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { printf 'ERROR: docker is required\n' >&2; exit 2; }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
tar -xzf "${internal_bundle}" -C "${tmp}"
archive="${tmp}/payload/media/agent-releases/${version}/hfl-agent-${version}-linux-amd64-${flavor}.tar.gz"
[[ -s "${archive}" ]] \
	|| { printf 'ERROR: Ubuntu-specific Agent archive is missing: %s\n' "${archive}" >&2; exit 1; }
mkdir -p "${tmp}/agent"
tar -xzf "${archive}" -C "${tmp}/agent"
mapfile -t roots < <(find "${tmp}/agent" -mindepth 1 -maxdepth 1 -type d -print)
[[ "${#roots[@]}" -eq 1 ]] \
	|| { printf 'ERROR: Agent archive must contain one root directory\n' >&2; exit 1; }
root="${roots[0]}"
deps="${root}/deps/${flavor}/amd64"
compgen -G "${deps}/*.deb" >/dev/null \
	|| { printf 'ERROR: Ubuntu-specific Agent debs are missing\n' >&2; exit 1; }

image="ubuntu:${ubuntu_release}"
docker image inspect "${image}" >/dev/null 2>&1 || docker pull "${image}"
docker run --rm --pull=never --network none \
	-v "${root}:/agent:ro" \
	"${image}" bash -euo pipefail -c '
printf "#!/bin/sh\nexit 101\n" >/usr/sbin/policy-rc.d
chmod 0755 /usr/sbin/policy-rc.d
export DEBIAN_FRONTEND=noninteractive
dpkg -i /agent/deps/'"${flavor}"'/amd64/*.deb
[[ -z "$(dpkg --audit)" ]]
bash -n /agent/install.sh
/agent/bin/hfl-agent -version
/agent/bin/kopia --version
'
printf 'Offline Agent bundle verification passed for Ubuntu %s\n' "${ubuntu_release}"

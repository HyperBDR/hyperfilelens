#!/usr/bin/env bash
# Install one offline Docker CE dependency asset in its matching Ubuntu image.
set -euo pipefail

[[ $# -eq 2 ]] || {
	printf 'Usage: %s UBUNTU_RELEASE HOST_DEBS_ASSET\n' "$0" >&2
	exit 2
}
ubuntu_release=$1
asset=$2
case "${ubuntu_release}" in
20.04) release_id=2004 ;;
22.04) release_id=2204 ;;
24.04) release_id=2404 ;;
*) printf 'ERROR: unsupported Ubuntu release: %s\n' "${ubuntu_release}" >&2; exit 2 ;;
esac
[[ -s "${asset}" ]] || { printf 'ERROR: host dependency asset is missing\n' >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { printf 'ERROR: docker is required\n' >&2; exit 2; }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
tar -xf "${asset}" -C "${tmp}"
archive="${tmp}/payload/media/gateway-bootstrap/docker-debs-ubuntu${release_id}-amd64.tar.gz"
[[ -s "${archive}" ]] || { printf 'ERROR: nested Docker deb archive is missing\n' >&2; exit 1; }
mkdir -p "${tmp}/debs"
tar -xzf "${archive}" -C "${tmp}/debs"
compgen -G "${tmp}/debs/*.deb" >/dev/null \
	|| { printf 'ERROR: Docker deb archive contains no packages\n' >&2; exit 1; }

image="ubuntu:${ubuntu_release}"
docker image inspect "${image}" >/dev/null 2>&1 || docker pull "${image}"
docker run --rm --pull=never --network none \
	-v "${tmp}/debs:/offline-debs:ro" \
	"${image}" bash -euo pipefail -c '
printf "#!/bin/sh\nexit 101\n" >/usr/sbin/policy-rc.d
chmod 0755 /usr/sbin/policy-rc.d
export DEBIAN_FRONTEND=noninteractive
dpkg -i /offline-debs/*.deb
[[ -z "$(dpkg --audit)" ]]
docker --version
dockerd --version
containerd --version
docker compose version
'
printf 'Offline Docker dependency verification passed for Ubuntu %s\n' "${ubuntu_release}"

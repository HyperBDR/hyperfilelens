#!/usr/bin/env bash
# Offline Docker CE install for HyperFileLens Data Gateways (Ubuntu 24.04 amd64).
# Bundled under /media/gateway-bootstrap/ and invoked by gateway-bootstrap-linux.sh.
#
# Host-safe policy: only install packages from the bundled .deb archive. Never run
# apt-get --fix-broken or other apt operations that can remove or upgrade unrelated
# host packages (python, cloud-init, nfs-common, etc.) on customer-provided machines.
set -euo pipefail

HFL_GATEWAY_BOOTSTRAP_BASE="${HFL_GATEWAY_BOOTSTRAP_BASE:-${HFL_API_BASE:-}/media/gateway-bootstrap}"
DOCKER_DEBS_ARCHIVE="docker-debs-ubuntu2404-amd64.tar.gz"
MIN_ENGINE_VERSION="${HFL_DOCKER_MIN_ENGINE:-24.0.0}"

hfl_now() {
	date -u +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ
}

hfl_step() {
	printf '[%s] [STEP ] %s\n' "$(hfl_now)" "$1"
}

hfl_ok() {
	printf '[%s] [ OK  ] %s\n' "$(hfl_now)" "$1"
}

hfl_warn() {
	printf '[%s] [WARN ] %s\n' "$(hfl_now)" "$1" >&2
}

hfl_fail() {
	printf '[%s] [FAIL ] %s\n' "$(hfl_now)" "$1" >&2
	exit "${2:-1}"
}

CURL_TLS=(-k)
if [[ "${HFL_INSECURE_TLS:-1}" == "0" ]]; then
	CURL_TLS=()
fi

docker_engine_version() {
	docker version --format '{{.Server.Version}}' 2>/dev/null || true
}

docker_compose_version() {
	if docker compose version >/dev/null 2>&1; then
		docker compose version --short 2>/dev/null || docker compose version 2>/dev/null | awk '{print $NF}'
		return 0
	fi
	if command -v docker-compose >/dev/null 2>&1; then
		docker-compose version --short 2>/dev/null || true
		return 0
	fi
	printf ''
}

docker_version_ge() {
	local have="$1"
	local want="$2"
	[[ -n "${have}" && -n "${want}" ]] || return 1
	dpkg --compare-versions "${have}" ge "${want}"
}

docker_runtime_ready() {
	local min_version="${1:-24.0.0}"
	command -v docker >/dev/null 2>&1 || return 1
	docker info >/dev/null 2>&1 || return 1
	local engine compose
	engine="$(docker_engine_version)"
	[[ -n "${engine}" ]] || return 1
	docker_version_ge "${engine}" "${min_version}" || return 1
	compose="$(docker_compose_version)"
	[[ -n "${compose}" ]] || return 1
	return 0
}

assert_host_os() {
	local id version_id arch
	if [[ -r /etc/os-release ]]; then
		# shellcheck disable=SC1091
		. /etc/os-release
	fi
	arch="$(uname -m)"
	[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] \
		|| hfl_fail "Docker offline install requires Ubuntu 24.04 (current: ${ID:-unknown} ${VERSION_ID:-unknown})." 4
	[[ "${arch}" == "x86_64" || "${arch}" == "amd64" ]] \
		|| hfl_fail "Docker offline install requires amd64 (current: ${arch})." 4
}

run_quiet() {
	local log_file="$1"
	shift
	if [[ "${HFL_VERBOSE:-0}" == "1" ]]; then
		"$@"
	else
		"$@" >"${log_file}" 2>&1
	fi
}

if [[ "$(id -u)" -ne 0 ]]; then
	hfl_fail "Administrator privileges are required." 1
fi

if docker_runtime_ready "${MIN_ENGINE_VERSION}"; then
	hfl_ok "Using existing Docker (engine $(docker_engine_version), compose $(docker_compose_version))."
	exit 0
fi

if command -v docker >/dev/null 2>&1; then
	if [[ "${HFL_FORCE_DOCKER_INSTALL:-0}" != "1" ]]; then
		hfl_fail "Docker is already installed on this host but is not usable. Start or upgrade Docker on the host, or set HFL_FORCE_DOCKER_INSTALL=1 to install from the offline bundle." 3
	fi
	hfl_warn "HFL_FORCE_DOCKER_INSTALL=1: proceeding with offline Docker install."
fi

assert_host_os

if command -v dpkg >/dev/null 2>&1; then
	audit_out="$(dpkg --audit 2>/dev/null || true)"
	if [[ -n "${audit_out}" ]]; then
		hfl_warn "dpkg reports broken packages on this host (will not modify them automatically):"
		printf '%s\n' "${audit_out}" | sed 's/^/  /' >&2
		hfl_warn "Fix host apt state yourself before re-running if Docker install fails."
	fi
fi

if ! command -v curl >/dev/null 2>&1; then
	hfl_fail "curl is required to download Docker offline packages." 2
fi

base="${HFL_GATEWAY_BOOTSTRAP_BASE%/}"
if [[ -z "${base}" || "${base}" == "/media/gateway-bootstrap" ]]; then
	hfl_fail "HFL_GATEWAY_BOOTSTRAP_BASE or HFL_API_BASE must be set." 2
fi

work_dir="$(mktemp -d /tmp/hfl-docker-debs-XXXXXX)"
cleanup() { rm -rf "${work_dir}"; }
trap cleanup EXIT

archive_url="${base}/${DOCKER_DEBS_ARCHIVE}"
hfl_step "Downloading Docker CE offline bundle."
curl "${CURL_TLS[@]}" -fsSL "${archive_url}" -o "${work_dir}/${DOCKER_DEBS_ARCHIVE}"

tar -xzf "${work_dir}/${DOCKER_DEBS_ARCHIVE}" -C "${work_dir}"
deb_count="$(find "${work_dir}" -maxdepth 2 -name '*.deb' | wc -l | tr -d ' ')"
if [[ "${deb_count}" -lt 5 ]]; then
	hfl_fail "Docker offline bundle is incomplete (${deb_count} debs)." 3
fi

hfl_step "Installing Docker CE from offline packages (${deb_count} debs)."
mapfile -t deb_files < <(find "${work_dir}" -name '*.deb' -type f | sort)

# dpkg only — do not invoke apt-get on the host; apt may "correct dependencies" by
# removing unrelated packages when the host dpkg database is already broken.
ordered_debs=()
for prefix in \
	containerd.io \
	docker-ce-cli \
	docker-buildx-plugin \
	docker-compose-plugin \
	libip4tc2 libip6tc2 libxtables12 libmnl0 libnfnetlink0 \
	libnetfilter-conntrack3 libnftnl11 libjansson4 libbsd0 libedit2 libnftables1 \
	netbase iptables nftables \
	docker-ce; do
	for deb in "${deb_files[@]}"; do
		deb_base="$(basename "${deb}")"
		if [[ "${deb_base}" == "${prefix}_"* ]]; then
			ordered_debs+=("${deb}")
		fi
	done
done
for deb in "${deb_files[@]}"; do
	found=0
	for seen in "${ordered_debs[@]}"; do
		[[ "${deb}" == "${seen}" ]] && found=1 && break
	done
	[[ "${found}" -eq 0 ]] && ordered_debs+=("${deb}")
done

dpkg_log="${work_dir}/dpkg.log"
dpkg_ok=0
if run_quiet "${dpkg_log}" dpkg -i "${ordered_debs[@]}"; then
	dpkg_ok=1
else
	hfl_warn "Bundled dpkg install reported dependency gaps; retrying with --force-depends."
	if run_quiet "${dpkg_log}" dpkg --force-depends -i "${ordered_debs[@]}"; then
		dpkg_ok=1
	elif [[ "${HFL_VERBOSE:-0}" != "1" && -s "${dpkg_log}" ]]; then
		tail -n 8 "${dpkg_log}" | sed 's/^/  /' >&2
	fi
fi

if docker_runtime_ready "${MIN_ENGINE_VERSION}"; then
	hfl_ok "Docker CE ready (engine $(docker_engine_version), compose $(docker_compose_version))."
	exit 0
fi

if [[ "${dpkg_ok}" -eq 0 ]]; then
	hfl_fail "Docker offline package install failed without modifying unrelated host packages. Set HFL_VERBOSE=1 for full dpkg logs; repair host apt/dpkg state if needed, then re-run." 3
fi

if command -v systemctl >/dev/null 2>&1; then
	systemctl enable docker >/dev/null 2>&1 || true
	# iptables/nftables debs from the bundle can reset FORWARD policy; restart docker
	# so it rebuilds bridge rules for custom networks (dev SourceLens / HFL stacks).
	systemctl restart docker >/dev/null 2>&1 || systemctl start docker >/dev/null 2>&1 || true
	sleep 2
fi

docker_runtime_ready "${MIN_ENGINE_VERSION}" \
	|| hfl_fail "Docker post-install check failed (need engine >= ${MIN_ENGINE_VERSION} with compose plugin)." 5

hfl_ok "Docker CE installed (engine $(docker_engine_version), compose $(docker_compose_version))."

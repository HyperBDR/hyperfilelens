#!/usr/bin/env bash
# Validate the pinned TLS profile and install/upgrade preservation contracts.
set -euo pipefail
umask 077

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERT_SOURCE="${REPO_ROOT}/deploy/nginx/certs"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

(
	cd "${CERT_SOURCE}"
	sha256sum --strict --check SHA256SUMS
)
openssl verify -CAfile "${CERT_SOURCE}/root-ca.crt" "${CERT_SOURCE}/tls.crt" >/dev/null
for hostname in \
	localhost hfl.localhost hyperfilelens.localhost \
	tenant.hyperfilelens.localhost host.docker.internal \
	hfl.test tenant.hyperfilelens.test; do
	openssl verify -CAfile "${CERT_SOURCE}/root-ca.crt" \
		-verify_hostname "${hostname}" "${CERT_SOURCE}/tls.crt" >/dev/null
done
openssl verify -CAfile "${CERT_SOURCE}/root-ca.crt" \
	-verify_ip 127.0.0.1 "${CERT_SOURCE}/tls.crt" >/dev/null
openssl verify -CAfile "${CERT_SOURCE}/root-ca.crt" \
	-verify_ip ::1 "${CERT_SOURCE}/tls.crt" >/dev/null
if openssl verify -CAfile "${CERT_SOURCE}/root-ca.crt" \
	-verify_ip 47.237.161.194 "${CERT_SOURCE}/tls.crt" >/dev/null 2>&1; then
	printf 'ERROR: default TLS certificate must not contain the production IP\n' >&2
	exit 1
fi
[[ ! -e "${CERT_SOURCE}/root-ca.key" ]]

# Load only the TLS helpers. The production installer itself remains standalone.
die() { printf 'test installer failure: %s\n' "$1" >&2; exit "${2:-1}"; }
log() { :; }
step() { :; }
warn() { :; }
source <(
	sed -n '/^ensure_tls_certs()/,/^ensure_env_file()/p' \
		"${REPO_ROOT}/deploy/installer/install.sh" | sed '$d'
)
source <(
	sed -n '/^materialize_to_install_dir()/,/^init_install_root()/p' \
		"${REPO_ROOT}/deploy/installer/install.sh" | sed '$d'
)
safe_normalize_dir() { printf '%s' "${1%/}"; }
require_root_or_sudo() { :; }
run_as_root() { "$@"; }

source_fixture="${tmp}/source"
mkdir -p "${source_fixture}/deploy/nginx"
cp -a "${CERT_SOURCE}" "${source_fixture}/deploy/nginx/certs"
printf 'fixture\n' >"${source_fixture}/docker-compose.yml"
validate_default_tls_bundle "${source_fixture}/deploy/nginx/certs"

ROOT="${tmp}/fresh"
sync_default_tls_bundle "${source_fixture}/deploy/nginx/certs"
validate_tls_pair "${ROOT}/deploy/nginx/certs"
[[ "$(stat -c '%a' "${ROOT}/deploy/nginx/certs/tls.key")" == "600" ]]

INSTALL_DIR="${tmp}/materialized-fresh"
materialize_to_install_dir "${source_fixture}"
ROOT="${INSTALL_DIR}"
ensure_tls_certs
[[ "$(stat -c '%a' "${INSTALL_DIR}/deploy/nginx/certs/tls.key")" == "600" ]]

ROOT="${tmp}/custom"
mkdir -p \
	"${ROOT}/deploy/nginx/certs" \
	"${ROOT}/payload" \
	"${ROOT}/data" \
	"${ROOT}/backup" \
	"${ROOT}/upgrade_tmp"
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 30 \
	-keyout "${ROOT}/deploy/nginx/certs/tls.key" \
	-out "${ROOT}/deploy/nginx/certs/tls.crt" \
	-subj '/CN=custom.example.test' >/dev/null 2>&1
printf 'stale\n' >"${ROOT}/payload/stale-release-file"
printf 'preserved env\n' >"${ROOT}/.env"
printf 'preserved data\n' >"${ROOT}/data/marker"
printf 'preserved backup\n' >"${ROOT}/backup/marker"
printf 'preserved upgrade state\n' >"${ROOT}/upgrade_tmp/marker"
# Rsync's size+mtime quick check must not preserve stale release-controlled
# content. Match both attributes while deliberately changing the bytes.
printf 'outdate\n' >"${ROOT}/docker-compose.yml"
touch -r "${source_fixture}/docker-compose.yml" "${ROOT}/docker-compose.yml"
before="$(sha256sum "${ROOT}/deploy/nginx/certs/tls.crt" "${ROOT}/deploy/nginx/certs/tls.key")"
sync_default_tls_bundle "${source_fixture}/deploy/nginx/certs"
after="$(sha256sum "${ROOT}/deploy/nginx/certs/tls.crt" "${ROOT}/deploy/nginx/certs/tls.key")"
[[ "${before}" == "${after}" ]]
INSTALL_DIR="${ROOT}"
materialize_to_install_dir "${source_fixture}"
after="$(sha256sum "${ROOT}/deploy/nginx/certs/tls.crt" "${ROOT}/deploy/nginx/certs/tls.key")"
[[ "${before}" == "${after}" ]]
[[ ! -e "${ROOT}/payload/stale-release-file" ]]
[[ "$(<"${ROOT}/.env")" == "preserved env" ]]
[[ "$(<"${ROOT}/data/marker")" == "preserved data" ]]
[[ "$(<"${ROOT}/backup/marker")" == "preserved backup" ]]
[[ "$(<"${ROOT}/upgrade_tmp/marker")" == "preserved upgrade state" ]]
[[ "$(<"${ROOT}/docker-compose.yml")" == "fixture" ]]

ROOT="${tmp}/incomplete"
mkdir -p "${ROOT}/deploy/nginx/certs"
cp "${CERT_SOURCE}/tls.crt" "${ROOT}/deploy/nginx/certs/tls.crt"
if (sync_default_tls_bundle "${source_fixture}/deploy/nginx/certs") 2>/dev/null; then
	printf 'ERROR: an incomplete installed TLS pair must fail\n' >&2
	exit 1
fi
INSTALL_DIR="${ROOT}"
if (materialize_to_install_dir "${source_fixture}") 2>/dev/null; then
	printf 'ERROR: fresh materialization accepted an incomplete TLS pair\n' >&2
	exit 1
fi

# Release validation permits only the pinned server key and rejects a CA key.
release_fixture="${tmp}/release"
mkdir -p "${release_fixture}/deploy/nginx"
cp -a "${CERT_SOURCE}" "${release_fixture}/deploy/nginx/certs"
chmod 600 "${release_fixture}/deploy/nginx/certs/tls.key"
# shellcheck source=../../release/build.sh
source "${REPO_ROOT}/release/build.sh"
validate_release_security "${release_fixture}"
cp "${release_fixture}/deploy/nginx/certs/tls.key" \
	"${release_fixture}/deploy/nginx/certs/root-ca.key"
if (validate_release_security "${release_fixture}") 2>/dev/null; then
	printf 'ERROR: release validation accepted a root CA private key\n' >&2
	exit 1
fi

printf 'Default TLS certificate contracts passed.\n'

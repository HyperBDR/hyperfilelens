#!/usr/bin/env bash
# Exercise CI release assembly with tiny synthetic, non-Docker bundles.
set -euo pipefail
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d "${ROOT}/build/ci-assembly-test.XXXXXX")"
trap 'rm -rf "${tmp}"' EXIT
input="${tmp}/input"
fixtures="${tmp}/fixtures"
output="${tmp}/release"
mkdir -p "${input}" "${fixtures}"

make_gzip() {
	local output_path=$1 content=$2
	mkdir -p "$(dirname "${output_path}")"
	printf '%s\n' "${content}" | gzip -c >"${output_path}"
}

make_metadata() {
	local output_path=$1 component=$2 ref=$3 digest_char=$4
	mkdir -p "$(dirname "${output_path}")"
	printf '{"component":"%s","ref":"%s","digest":"sha256:%064d","platform":"linux/amd64"}\n' \
		"${component}" "${ref}" "${digest_char}" >"${output_path}"
}

hfl="${fixtures}/hfl"
make_gzip "${hfl}/images/00-hyperfilelens.tar.gz" hfl-images
make_metadata "${hfl}/metadata/hfl-backend.json" hfl-backend example/hfl-backend:1.2.3 1
make_metadata "${hfl}/metadata/hfl-frontend.json" hfl-frontend example/hfl-frontend:1.2.3 2
tar -C "${hfl}" -czf "${input}/_internal-hfl-images.tar.gz" images metadata

runtime="${fixtures}/runtime"
make_gzip "${runtime}/images/01-postgres-17.tar.gz" postgres
make_gzip "${runtime}/images/02-redis-alpine.tar.gz" redis
make_metadata "${runtime}/metadata/postgres.json" postgres hyperfilelens-postgres:17 3
make_metadata "${runtime}/metadata/redis.json" redis hyperfilelens-redis:alpine 4
tar -C "${runtime}" -czf "${input}/_internal-runtime-images.tar.gz" images metadata

sl="${fixtures}/sourcelens"
make_gzip "${sl}/images/10-sourcelens-app.tar.gz" sourcelens-app
make_gzip "${sl}/images/11-sourcelens-lensnode.tar.gz" sourcelens-lensnode
make_gzip "${sl}/images/12-nginx-stable-alpine.tar.gz" nginx
mkdir -p "${sl}/sourcelens/deploy/postgresql/initdb.d" \
	"${sl}/sourcelens/deploy/nginx/certs" \
	"${sl}/payload/media/gateway-bootstrap"
printf '#!/usr/bin/env bash\nexit 0\n' >"${sl}/sourcelens/install.sh"
printf '#!/usr/bin/env python3\n' >"${sl}/sourcelens/patch-env-runtime.py"
printf 'services: {}\n' >"${sl}/sourcelens/docker-compose.yml"
printf 'DJANGO_DEBUG=true\n' >"${sl}/sourcelens/.env.example"
printf 'fixture\n' >"${sl}/sourcelens/deploy/postgresql/initdb.d/fixture.sh"
cp "${sl}/images/11-sourcelens-lensnode.tar.gz" \
	"${sl}/payload/media/gateway-bootstrap/lensnode-image-linux-amd64.tar.gz"
cat >"${sl}/sourcelens/BUILD_INFO.json" <<'JSON'
{
  "enabled": true,
  "git_url": "https://github.com/HyperBDR/sourcelens.git",
  "git_ref": "v0.4.0",
  "git_commit": "0000000000000000000000000000000000000000",
  "git_commit_short": "0000000",
  "version": "0.4.0",
  "patch_sha256": "fixture",
  "network": "hyperfilelens-bridge",
  "install_dir": "/opt/hyperfilelens/sourcelens",
  "lensnode_image": "hyperfilelens-sourcelens-lensnode:latest",
  "images": {
    "backend": {"ref": "hyperfilelens-sourcelens-backend:1.2.3-sl0.4.0", "upstream_ref": "example/backend:v0.4.0", "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"},
    "frontend": {"ref": "hyperfilelens-sourcelens-frontend:1.2.3-sl0.4.0", "upstream_ref": "example/frontend:v0.4.0", "digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222"},
    "lensnode": {"ref": "hyperfilelens-sourcelens-lensnode:1.2.3-sl0.4.0", "upstream_ref": "example/lensnode:v0.4.0", "digest": "sha256:3333333333333333333333333333333333333333333333333333333333333333"},
    "nginx": {"ref": "hyperfilelens-sourcelens-nginx:stable-alpine", "digest": "sha256:4444444444444444444444444444444444444444444444444444444444444444"}
  }
}
JSON
tar -C "${sl}" -czf "${input}/_internal-sourcelens-bundle.tar.gz" images sourcelens payload

for release_id in 2004 2404; do
	host="${fixtures}/host-${release_id}"
	mkdir -p "${host}/payload/media/gateway-bootstrap"
	make_gzip \
		"${host}/payload/media/gateway-bootstrap/docker-debs-ubuntu${release_id}-amd64.tar.gz" \
		"synthetic ubuntu ${release_id} Docker deb bundle"
	tar -C "${host}" -czf "${input}/_internal-host-debs-ubuntu${release_id}.tar.gz" payload
done

for asset in linux-amd64 linux-arm64 darwin-amd64 darwin-arm64 windows-amd64; do
	agent="${fixtures}/agent-${asset}"
	mkdir -p "${agent}/payload/media/agent-releases/1.2.3" \
		"${agent}/payload/media/enroll-bootstrap"
	printf '%s\n' "${asset}" >"${agent}/payload/media/agent-releases/1.2.3/${asset}.fixture"
	if [[ "${asset}" == "linux-amd64" ]]; then
		printf 'ubuntu 20.04 fixture\n' \
			>"${agent}/payload/media/agent-releases/1.2.3/hfl-agent-1.2.3-linux-amd64-ubuntu2004.tar.gz"
		printf 'ubuntu 24.04 fixture\n' \
			>"${agent}/payload/media/agent-releases/1.2.3/hfl-agent-1.2.3-linux-amd64-ubuntu2404.tar.gz"
	fi
	printf '%s\n' "${asset}" >"${agent}/payload/media/enroll-bootstrap/${asset}.fixture"
	tar -C "${agent}" -czf "${input}/_internal-agent-${asset}.tar.gz" payload
done

HFL_CI_RELEASE_BUILD_DIR="${output}" \
	HFL_RELEASE_MAX_SINGLE_BYTES=1024 \
	HFL_RELEASE_PART_BYTES=4096 \
	"${ROOT}/release/ci/assemble-release.sh" \
		--input-dir "${input}" \
		--version 1.2.3 \
		--commit 0123456789abcdef0123456789abcdef01234567

(
	cd "${output}/dist"
	while IFS= read -r asset; do
		[[ -f "${asset}" ]]
	done <"${output}/release-assets.txt"
	if grep -F 'release-assets.txt' "${output}/release-assets.txt" >/dev/null; then
		printf 'ERROR: internal release asset list must not publish itself\n' >&2
		exit 1
	fi
	jq -e '.spdxVersion == "SPDX-2.3" and (.packages | length) == 7' \
		SBOM.spdx.json >/dev/null
	jq -e '(.files | length) == 3' SBOM.spdx.json >/dev/null
	sha256sum -c SHA256SUMS
	[[ -s hyperfilelens-root-ca.crt ]]
	first="$(find . -maxdepth 1 -type f -name 'hyperfilelens-*.tar.gz.part-000' -print -quit)"
	[[ -n "${first}" ]]
	archive="${first%.part-000}"
	cat "${archive}.part-"* >"${archive}"
	tar -tzf "${archive}" | grep -E '/sync-env\.py$' >/dev/null
	tar -tzf "${archive}" | grep -E '/apply-runtime-config\.py$' >/dev/null
	tar -tzf "${archive}" | grep -E '/deploy/nginx/certs/tls\.crt$' >/dev/null
	tar -tzf "${archive}" | grep -E '/deploy/nginx/certs/tls\.key$' >/dev/null
	tar -tzf "${archive}" | grep -E '/deploy/nginx/certs/root-ca\.crt$' >/dev/null
	key_mode="$(tar -tvzf "${archive}" | awk '$NF ~ /\/deploy\/nginx\/certs\/tls\.key$/ {mode=$1} END {print mode}')"
	[[ "${key_mode}" == "-rw-------" ]]
	tar -tzf "${archive}" | grep -E '/hfl-agent-1\.2\.3-linux-amd64-ubuntu2004\.tar\.gz$' >/dev/null
	tar -tzf "${archive}" | grep -E '/hfl-agent-1\.2\.3-linux-amd64-ubuntu2404\.tar\.gz$' >/dev/null
	"${ROOT}/release/ci/verify-release.sh" --archive "$(realpath "${archive}")"
)

printf 'Synthetic CI release assembly passed.\n'

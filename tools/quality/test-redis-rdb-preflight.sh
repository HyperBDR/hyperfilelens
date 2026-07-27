#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

ROOT="${tmp}/install"
mkdir -p "${ROOT}/data/redis"
printf 'fixture\n' >"${ROOT}/data/redis/dump.rdb"

step() { :; }
skip() { :; }
warn() { printf 'WARN: %s\n' "$*"; }
ok() { printf 'OK: %s\n' "$*"; }
die() { printf 'FAIL: %s\n' "$*" >&2; return 1; }

RDB_MEMORY=365
compose_in_root() {
	case "$*" in
	"ps -q redis") printf 'redis-container\n' ;;
	"exec -T redis redis-check-rdb /data/dump.rdb")
		printf 'RDB memory usage when created %s.00 Mb\n' "${RDB_MEMORY}"
		;;
	*) printf 'unexpected compose call: %s\n' "$*" >&2; return 1 ;;
	esac
}

source <(sed -n '/^preflight_redis_recovery()/,/^}/p' "${installer}")

preflight_redis_recovery
RDB_MEMORY=600
if (preflight_redis_recovery); then
	printf 'ERROR: oversized Redis RDB recovery estimate was accepted\n' >&2
	exit 1
fi

printf 'Redis RDB preflight checks passed.\n'

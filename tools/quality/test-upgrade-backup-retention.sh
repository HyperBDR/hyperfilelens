#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
installer="${ROOT_REPO}/deploy/installer/install.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

ROOT="${tmp}/install"
mkdir -p \
	"${ROOT}/data/postgresql" \
	"${ROOT}/data/sourcelens/postgresql" \
	"${ROOT}/data/redis" \
	"${ROOT}/data/sourcelens/redis" \
	"${ROOT}/data/logs" \
	"${ROOT}/data/sourcelens/logs" \
	"${ROOT}/data/sourcelens/workspace"
printf 'config\n' >"${ROOT}/.env"
printf 'exclude\n' >"${ROOT}/data/postgresql/PG_VERSION"
printf 'exclude\n' >"${ROOT}/data/sourcelens/postgresql/PG_VERSION"
printf 'exclude\n' >"${ROOT}/data/redis/dump.rdb"
printf 'exclude\n' >"${ROOT}/data/logs/api.log"
printf 'retain\n' >"${ROOT}/data/sourcelens/workspace/document.txt"

step() { :; }
warn() { :; }
log() { :; }
die() { printf 'ERROR: %s\n' "$1" >&2; return "${2:-1}"; }
read_env_value() { :; }
source <(sed -n '/^backup_env_and_data()/,/^apply_upgrade_files()/p' "${installer}" | sed '$d')

backup_env_and_data 20260723-010000
archive="${ROOT}/backup/hyperfilelens-backup-20260723-010000.tar.gz"
tar -tzf "${archive}" >"${tmp}/contents.txt"
grep -F 'data/sourcelens/workspace/document.txt' "${tmp}/contents.txt" >/dev/null
if grep -E 'data/(postgresql|redis|logs)|data/sourcelens/(postgresql|redis|logs)' \
	"${tmp}/contents.txt" >/dev/null; then
	printf 'ERROR: live database, cache, or log data entered the upgrade archive\n' >&2
	exit 1
fi

for stamp in 20260720-010000 20260721-010000 20260722-010000; do
	printf 'dump\n' >"${ROOT}/backup/hyperfilelens-postgresql-${stamp}.dump"
	printf 'globals\n' >"${ROOT}/backup/hyperfilelens-postgresql-globals-${stamp}.sql"
done
HFL_BACKUP_RETENTION_COUNT=2 \
HFL_BACKUP_RETENTION_DAYS=3650 \
HFL_BACKUP_RETENTION_BYTES=10737418240 \
	prune_upgrade_backups

[[ ! -e "${ROOT}/backup/hyperfilelens-postgresql-20260720-010000.dump" ]]
[[ ! -e "${ROOT}/backup/hyperfilelens-postgresql-20260721-010000.dump" ]]
[[ -e "${ROOT}/backup/hyperfilelens-postgresql-20260722-010000.dump" ]]
[[ -e "${ROOT}/backup/hyperfilelens-backup-20260723-010000.tar.gz" ]]
printf 'Upgrade backup retention checks passed.\n'

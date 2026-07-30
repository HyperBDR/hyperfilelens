#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=../sourcelens/common.sh
source "${ROOT}/tools/sourcelens/common.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
call_log="${tmp}/calls.log"
original_git="$(declare -f sourcelens_git)"
original_git_network="$(declare -f sourcelens_git_network)"

sourcelens_log() { :; }
sourcelens_git() {
	printf 'local|%s\n' "$*" >>"${call_log}"
}
sourcelens_git_network() {
	printf 'network|%s\n' "$*" >>"${call_log}"
}

SOURCELENS_OFFLINE=0
sourcelens_sync_submodules
[[ "$(sed -n '1p' "${call_log}")" == 'local|submodule sync --recursive' ]]
[[ "$(sed -n '2p' "${call_log}")" == 'network|submodule update --init --recursive --force' ]]

: >"${call_log}"
SOURCELENS_OFFLINE=1
sourcelens_sync_submodules
[[ "$(sed -n '1p' "${call_log}")" == 'local|submodule sync --recursive' ]]
[[ "$(sed -n '2p' "${call_log}")" == 'local|submodule update --init --recursive --force --no-fetch' ]]

eval "${original_git}"
eval "${original_git_network}"

module_repo="${tmp}/module"
super_repo="${tmp}/super"
source_cache="${tmp}/source"

git init -q "${module_repo}"
git -C "${module_repo}" config user.email test@hyperfilelens.local
git -C "${module_repo}" config user.name 'HyperFileLens Test'
printf '%s\n' \
	'[project]' \
	'name = "agentcore-task-fixture"' \
	'version = "0.0.1"' >"${module_repo}/pyproject.toml"
git -C "${module_repo}" add pyproject.toml
git -C "${module_repo}" commit -q -m fixture

git init -q "${super_repo}"
git -C "${super_repo}" config user.email test@hyperfilelens.local
git -C "${super_repo}" config user.name 'HyperFileLens Test'
git -C "${super_repo}" -c protocol.file.allow=always \
	submodule add -q "${module_repo}" backend/agentcore/agentcore-task
git -C "${super_repo}" commit -q -am fixture

git clone -q "${super_repo}" "${source_cache}"
git -C "${source_cache}" -c protocol.file.allow=always \
	submodule update --init --recursive
module_path="${source_cache}/backend/agentcore/agentcore-task"
expected_commit="$(git -C "${module_path}" rev-parse HEAD)"
rm "${module_path}/pyproject.toml"
[[ ! -e "${module_path}/pyproject.toml" ]]
[[ "$(git -C "${module_path}" rev-parse HEAD)" == "${expected_commit}" ]]

(
	cd "${source_cache}"
	SOURCELENS_OFFLINE=1
	sourcelens_sync_submodules
)

[[ -f "${module_path}/pyproject.toml" ]]
grep -F 'name = "agentcore-task-fixture"' "${module_path}/pyproject.toml" >/dev/null
[[ "$(git -C "${module_path}" rev-parse HEAD)" == "${expected_commit}" ]]
git -C "${module_path}" diff --quiet

printf 'SourceLens submodule recovery checks passed.\n'

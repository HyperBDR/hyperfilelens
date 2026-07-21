#!/usr/bin/env bash
# Exercise the production shared-host guard with deterministic Docker fixtures.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin" "${tmp}/state"

cat >"${tmp}/bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "$1 $2 ${3:-}" in
"ps -aq --no-trunc") printf '%s\n' owned-hfl owned-legacy owned-gateway foreign-hfl foreign-sl ;;
"network ls -q") printf '%s\n' owned-network owned-gateway-network foreign-network foreign-project-collision ;;
"volume ls -q") printf '%s\n' owned-volume foreign-volume foreign-volume-collision ;;
"inspect "*) cat "${HFL_TEST_STATE_DIR}/containers.json" ;;
"network inspect "*) cat "${HFL_TEST_STATE_DIR}/networks.json" ;;
"volume inspect "*) cat "${HFL_TEST_STATE_DIR}/volumes.json" ;;
*) printf 'unexpected fake docker invocation: %s\n' "$*" >&2; exit 1 ;;
esac
SH
chmod +x "${tmp}/bin/docker"

cat >"${tmp}/state/containers.json" <<'JSON'
[
  {"Id":"owned-hfl","Name":"/hyperfilelens-api-1","Config":{"Labels":{"com.docker.compose.project":"hyperfilelens","com.docker.compose.project.working_dir":"/opt/hyperfilelens"}},"State":{"Status":"running","StartedAt":"owned"},"Mounts":[{"Type":"volume","Name":"hyperfilelens_cache"}]},
  {"Id":"owned-legacy","Name":"/sourcelens-api-1","Config":{"Labels":{"com.docker.compose.project":"sourcelens","com.docker.compose.project.config_files":"/opt/hyperfilelens/sourcelens/docker-compose.yml"}},"State":{"Status":"running","StartedAt":"legacy"}},
  {"Id":"owned-gateway","Name":"/hyperfilelens-gateway-lensnode-1","Config":{"Labels":{"com.docker.compose.project":"hyperfilelens-gateway","com.hyperfilelens.managed":"true","com.hyperfilelens.component":"gateway-lensnode"}},"State":{"Status":"running","StartedAt":"gateway"}},
  {"Id":"foreign-hfl","Name":"/foreign-hfl","Config":{"Labels":{"com.docker.compose.project":"hyperfilelens","com.docker.compose.project.working_dir":"/srv/other-hfl"}},"State":{"Status":"running","StartedAt":"foreign-hfl"}},
  {"Id":"foreign-sl","Name":"/foreign-sl","Config":{"Labels":{"com.docker.compose.project":"sourcelens","com.docker.compose.project.working_dir":"/srv/sourcelens"}},"State":{"Status":"running","StartedAt":"foreign-sl"}}
]
JSON
cat >"${tmp}/state/networks.json" <<'JSON'
[
  {"Id":"owned-network","Name":"hyperfilelens_default","Driver":"bridge","Scope":"local","Labels":{"com.docker.compose.project":"hyperfilelens"},"Containers":{"owned-hfl":{"Name":"hyperfilelens-api-1"}}},
  {"Id":"owned-gateway-network","Name":"hyperfilelens-gateway_default","Driver":"bridge","Scope":"local","Labels":{"com.docker.compose.project":"hyperfilelens-gateway"},"Containers":{"owned-gateway":{"Name":"hyperfilelens-gateway-lensnode-1"}}},
  {"Id":"foreign-network","Name":"customer_default","Driver":"bridge","Scope":"local","Labels":{"com.docker.compose.project":"customer"},"Containers":{"foreign-sl":{"Name":"foreign-sl"}}},
  {"Id":"foreign-project-collision","Name":"hyperfilelens-sourcelens_default","Driver":"bridge","Scope":"local","Labels":{"com.docker.compose.project":"hyperfilelens-sourcelens"},"Containers":{"foreign-sl":{"Name":"foreign-sl"}}}
]
JSON
cat >"${tmp}/state/volumes.json" <<'JSON'
[
  {"Name":"hyperfilelens_cache","Driver":"local","Mountpoint":"/var/lib/docker/volumes/hyperfilelens_cache/_data","Labels":{"com.docker.compose.project":"hyperfilelens"},"Scope":"local"},
  {"Name":"customer_data","Driver":"local","Mountpoint":"/var/lib/docker/volumes/customer_data/_data","Labels":{"com.docker.compose.project":"customer"},"Scope":"local"},
  {"Name":"foreign_hfl_data","Driver":"local","Mountpoint":"/var/lib/docker/volumes/foreign_hfl_data/_data","Labels":{"com.docker.compose.project":"hyperfilelens"},"Scope":"local"}
]
JSON

# Load only the two guard functions; the production script itself must remain standalone.
source <(sed -n '/^capture_unrelated_state()/,/^capture_unrelated_state "${work}/p' \
	"${ROOT}/.github/scripts/remote-deploy.sh" | sed '$d')
PATH="${tmp}/bin:${PATH}"
export PATH HFL_TEST_STATE_DIR="${tmp}/state"
INSTALL_DIR=/opt/hyperfilelens

capture_unrelated_state "${tmp}/before.json"
grep -F '"foreign-hfl"' "${tmp}/before.json" >/dev/null
grep -F '"foreign-sl"' "${tmp}/before.json" >/dev/null
grep -F '"customer_default"' "${tmp}/before.json" >/dev/null
grep -F '"hyperfilelens-sourcelens_default"' "${tmp}/before.json" >/dev/null
grep -F '"customer_data"' "${tmp}/before.json" >/dev/null
grep -F '"foreign_hfl_data"' "${tmp}/before.json" >/dev/null
if grep -E 'owned-hfl|owned-legacy|owned-gateway|hyperfilelens_default|hyperfilelens-gateway_default|hyperfilelens_cache' "${tmp}/before.json" >/dev/null; then
	printf 'ERROR: shared-host guard included HFL-owned resources in the sentinel state\n' >&2
	exit 1
fi

verify_unrelated_state "${tmp}/before.json" "${tmp}/same.json"
sed -i 's/"Id":"foreign-network"/"Id":"changed-network"/' "${tmp}/state/networks.json"
if verify_unrelated_state "${tmp}/before.json" "${tmp}/changed.json" 2>/dev/null; then
	printf 'ERROR: shared-host guard did not detect an unrelated network change\n' >&2
	exit 1
fi

printf 'Shared-host Docker guard checks passed.\n'

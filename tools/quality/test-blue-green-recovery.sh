#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1090
source "${ROOT_REPO}/deploy/installer/install.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
ROOT="${tmp}/install"
mkdir -p "${ROOT}"
printf 'APP_VERSION=1.0.0\n' >"${ROOT}/.env"

calls=()
sourcelens_present=0
compose_in_root() { calls+=("compose:$*"); }
compose_color() { calls+=("color:$*"); }
render_active_upstreams() { calls+=("render:$*"); }
reload_stable_nginx() { calls+=("reload"); }
write_active_color() { calls+=("active:$*"); }
wait_for_public_endpoints() { calls+=("public-health"); }
wait_for_color_health() { calls+=("color-health:$*"); }
ensure_blue_green_state() { calls+=("ensure-state"); }
read_active_color() { printf 'blue'; }
sourcelens_installed() { [[ "${sourcelens_present}" == "1" ]]; }
sourcelens_compose() { calls+=("sourcelens:$*"); }
wait_for_sourcelens_health() {
	calls+=("sourcelens-health")
	[[ "${sourcelens_health_ok:-1}" == "1" ]]
}
ok() { :; }
warn() { :; }

pin_gateway_version_if_missing 1.0.0
grep -Fx 'HFL_GATEWAY_VERSION=1.0.0' "${ROOT}/.env" >/dev/null
pin_gateway_version_if_missing 2.0.0
grep -Fx 'HFL_GATEWAY_VERSION=1.0.0' "${ROOT}/.env" >/dev/null

calls=()
start_hfl_stack
[[ " ${calls[*]} " == *" color:blue up -d --no-build api-blue web-blue "* ]]
[[ " ${calls[*]} " == *" color-health:blue "* ]]
[[ " ${calls[*]} " == *" compose:up -d --no-build nginx reload "* ]]

UPGRADE_HFL_WAS_RUNNING=1
UPGRADE_SOURCELENS_WAS_RUNNING=0
UPGRADE_PREVIOUS_COLOR=blue
UPGRADE_TARGET_COLOR=green
UPGRADE_HFL_COMMITTED=0
recover_upgrade_services
[[ " ${calls[*]} " == *" render:blue "* ]]
[[ " ${calls[*]} " == *" active:blue "* ]]
[[ " ${calls[*]} " != *" active:green "* ]]

calls=()
UPGRADE_HFL_COMMITTED=1
recover_upgrade_services
[[ " ${calls[*]} " == *" render:green "* ]]
[[ " ${calls[*]} " == *" active:green "* ]]

calls=()
UPGRADE_HFL_CUTOVER_ATTEMPTED=1
restore_previous_hfl_color blue green
[[ " ${calls[*]} " == *" render:blue "* ]]
[[ " ${calls[*]} " == *" compose:exec -T api-blue python manage.py ws_recovery_gate reattach "* ]]
[[ " ${calls[*]} " == *" compose:stop api-green web-green "* ]]
[[ " ${calls[*]} " == *" active:blue "* ]]

calls=()
UPGRADE_HFL_CUTOVER_ATTEMPTED=0
restore_previous_hfl_color legacy green
[[ " ${calls[*]} " == *" render:legacy green "* ]]
[[ " ${calls[*]} " == *" compose:stop api-green "* ]]
[[ " ${calls[*]} " != *" compose:stop api-green web-green "* ]]

calls=()
UPGRADE_HFL_WAS_RUNNING=0
UPGRADE_SOURCELENS_WAS_RUNNING=1
sourcelens_present=1
SOURCELENS_UPGRADE_STARTED=0
recover_upgrade_services
[[ " ${calls[*]} " == *" sourcelens:start "* ]]
[[ " ${calls[*]} " != *" sourcelens:up -d --no-build "* ]]

calls=()
SOURCELENS_UPGRADE_STARTED=1
recover_upgrade_services
[[ " ${calls[*]} " == *" sourcelens:up -d --no-build "* ]]

calls=()
SOURCELENS_MAINTENANCE_ARMED=1
sourcelens_health_ok=1
recover_upgrade_services
[[ " ${calls[*]} " == *" sourcelens-health "* ]]

calls=()
sourcelens_health_ok=0
if recover_upgrade_services; then
	printf 'ERROR: unhealthy SourceLens recovery must fail closed\n' >&2
	exit 1
fi
[[ " ${calls[*]} " == *" sourcelens-health "* ]]

printf 'Blue/green recovery state checks passed.\n'

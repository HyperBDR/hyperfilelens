#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bootstrap="${ROOT}/deploy/bootstrap/gateway-bootstrap-linux.sh"

# Gateway bootstrap must stay Agent-shaped: local gates, then enrollment helper.
# Console / SourceLens probes belong in hfl-enroll preflight after the helper download.
if grep -E 'Checking console connectivity|Checking SourceLens health|hfl_sourcelens_health_retry' \
	"${bootstrap}" >/dev/null; then
	printf 'ERROR: gateway bootstrap must not probe console/SourceLens before downloading hfl-enroll\n' >&2
	exit 1
fi

grep -F 'HyperFileLens enrollment helper' "${bootstrap}" >/dev/null
grep -F 'gateway-install' "${bootstrap}" >/dev/null
grep -F 'requires a systemd-based Linux distribution' "${bootstrap}" >/dev/null
grep -F 'systemctl show-environment' "${bootstrap}" >/dev/null

# Ensure helper download appears before gateway-install invocation.
helper_line="$(grep -n 'HyperFileLens enrollment helper' "${bootstrap}" | head -1 | cut -d: -f1)"
install_line="$(grep -n 'gateway-install' "${bootstrap}" | tail -1 | cut -d: -f1)"
if [[ -z "${helper_line}" || -z "${install_line}" || "${helper_line}" -ge "${install_line}" ]]; then
	printf 'ERROR: gateway bootstrap must download hfl-enroll before invoking gateway-install\n' >&2
	exit 1
fi

printf 'Gateway bootstrap preflight order validation passed\n'

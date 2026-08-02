#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUPERVISOR="${ROOT}/deploy/docker/dev-process-supervisor.py"
PYTHON_BIN="${PYTHON_BIN:-python}"
tmp="$(mktemp -d)"
supervisor_pid=""

cleanup() {
	if [[ -n "${supervisor_pid}" ]]; then
		kill -TERM "${supervisor_pid}" 2>/dev/null || true
		wait "${supervisor_pid}" 2>/dev/null || true
	fi
	rm -rf "${tmp}"
}
trap cleanup EXIT

mkdir -p "${tmp}/watch"

set +e
"${PYTHON_BIN}" "${SUPERVISOR}" \
	--watch "${tmp}/watch" \
	--max-restarts 1 \
	--stable-seconds 60 \
	--base-delay 0 \
	-- sh -c 'exit 7' >"${tmp}/failure.log" 2>&1
status=$?
set -e
[[ "${status}" -eq 7 ]]
grep -F 'child failed too often' "${tmp}/failure.log" >/dev/null

"${PYTHON_BIN}" "${SUPERVISOR}" \
	--watch "${tmp}/watch" \
	--max-restarts 2 \
	--stable-seconds 60 \
	--base-delay 0.01 \
	-- sh -c "echo started >> '${tmp}/starts'; exec sleep 30" \
	>"${tmp}/reload.log" 2>&1 &
supervisor_pid=$!

for _ in $(seq 1 50); do
	[[ -f "${tmp}/starts" ]] && break
	sleep 0.1
done
[[ "$(wc -l <"${tmp}/starts")" -eq 1 ]]
touch "${tmp}/watch/reload.py"
for _ in $(seq 1 50); do
	[[ "$(wc -l <"${tmp}/starts")" -ge 2 ]] && break
	sleep 0.1
done
[[ "$(wc -l <"${tmp}/starts")" -ge 2 ]]

kill -TERM "${supervisor_pid}"
wait "${supervisor_pid}" || true
supervisor_pid=""

printf 'Development process supervisor checks passed.\n'

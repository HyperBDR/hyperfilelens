#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
renderer="${ROOT}/deploy/docker/website-runtime-config.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

valid="${tmp}/valid.js"
HFL_WEBSITE_CONFIG_OUTPUT="${valid}" \
	HFL_WEBSITE_APP_URL="https://app.hyperfilelens.com" \
	sh "${renderer}"
grep -Fx "window.__HFL_WEBSITE_CONFIG__ = Object.freeze({ appUrl: 'https://app.hyperfilelens.com' })" \
	"${valid}" >/dev/null

direct="${tmp}/direct.js"
output="$(HFL_WEBSITE_CONFIG_OUTPUT="${direct}" \
	HFL_WEBSITE_APP_URL="not a public origin" sh "${renderer}" 2>&1)"
grep -F 'WARNING: invalid app URL' <<<"${output}" >/dev/null
grep -Fx "window.__HFL_WEBSITE_CONFIG__ = Object.freeze({ appUrl: '' })" \
	"${direct}" >/dev/null

grep -F "directAppOrigin()" \
	"${ROOT}/website/.vitepress/theme/HomeLanding.vue" >/dev/null
if grep -R -F 'https://app.hyperfilelens.com/login' "${ROOT}/website" \
	--exclude-dir=node_modules --exclude-dir=.vitepress >/dev/null; then
	printf 'ERROR: Website login CTA must use runtime configuration\n' >&2
	exit 1
fi

printf 'Website runtime URL configuration checks passed.\n'

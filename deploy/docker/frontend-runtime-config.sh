#!/bin/sh
# Generate site-specific public runtime configuration before Nginx starts.
set -eu

website_output=${HFL_WEBSITE_CONFIG_OUTPUT:-/usr/share/nginx/website/website-runtime-config.js}
tenant_output=${HFL_TENANT_CONFIG_OUTPUT:-/usr/share/nginx/runtime/tenant-app-runtime-config.js}
admin_output=${HFL_ADMIN_CONFIG_OUTPUT:-/usr/share/nginx/runtime/admin-app-runtime-config.js}
app_url=${HFL_WEBSITE_APP_URL:-}
ga_measurement_id=${HFL_GA_MEASUREMENT_ID:-}

if [ -n "${app_url}" ] && ! printf '%s' "${app_url}" \
  | grep -Eq '^[Hh][Tt][Tt][Pp][Ss]?://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?/?$'; then
  printf '%s\n' '[frontend-config] WARNING: invalid app URL; using the browser host and port 11443 fallback' >&2
  app_url=
fi

if [ -n "${ga_measurement_id}" ] && ! printf '%s' "${ga_measurement_id}" \
  | grep -Eq '^G-[A-Z0-9]+$'; then
  printf '%s\n' '[frontend-config] WARNING: invalid GA4 measurement ID; analytics is disabled' >&2
  ga_measurement_id=
fi

write_config() {
  output=$1
  content=$2
  temporary="${output}.tmp.$$"
  mkdir -p "$(dirname "${output}")"
  umask 022
  printf '%s\n' "${content}" > "${temporary}"
  mv -f "${temporary}" "${output}"
}

write_config "${website_output}" \
  "window.__HFL_WEBSITE_CONFIG__ = Object.freeze({ appUrl: '${app_url%/}', gaMeasurementId: '${ga_measurement_id}' })"
write_config "${tenant_output}" \
  "window.__HFL_APP_CONFIG__ = Object.freeze({ gaMeasurementId: '${ga_measurement_id}' })"
# Platform Operations and Django Admin must never emit SaaS analytics.
write_config "${admin_output}" \
  "window.__HFL_APP_CONFIG__ = Object.freeze({ gaMeasurementId: '' })"

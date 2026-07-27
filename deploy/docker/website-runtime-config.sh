#!/bin/sh
set -eu

output=${HFL_WEBSITE_CONFIG_OUTPUT:-/usr/share/nginx/website/website-runtime-config.js}
temporary="${output}.tmp"
app_url=${HFL_WEBSITE_APP_URL:-}

if [ -n "${app_url}" ] && ! printf '%s' "${app_url}" \
  | grep -Eq '^https?://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?/?$'; then
  printf '%s\n' '[website-config] WARNING: invalid app URL; using the browser host and port 11443 fallback' >&2
  app_url=
fi

umask 022
printf "window.__HFL_WEBSITE_CONFIG__ = Object.freeze({ appUrl: '%s' })\n" "${app_url%/}" > "${temporary}"
mv -f "${temporary}" "${output}"

#!/usr/bin/env bash
# Validate non-blocking public URL and Turnstile deployment configuration merging.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
remote_deploy="${ROOT}/.github/scripts/remote-deploy.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

python_body="${tmp}/merge-optional-config.py"
sed -n '/python3 - "${INSTALL_DIR}\/\.env" "${RUNTIME_ENV_FILE}" "${PUBLIC_URL}" "${DIRECT_HOST}" <<'"'"'PY'"'"'$/,/^PY$/p' \
	"${remote_deploy}" | sed '1d;$d' >"${python_body}"
[[ -s "${python_body}" ]]
python3 -m py_compile "${python_body}"

env_file="${tmp}/valid.env"
runtime_file="${tmp}/valid-runtime.env"
cat >"${env_file}" <<'ENV'
FRONTEND_URL=https://47.237.161.194:11443
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,47.237.161.194
CSRF_TRUSTED_ORIGINS=https://127.0.0.1:11443
LENS_GATEWAY_BASE_URL=https://47.237.161.194:11443/sourcelens
HFL_ADMIN_PUBLIC_URL=
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=false
TURNSTILE_ENABLED=true
TURNSTILE_SITE_KEY=old-site
TURNSTILE_SECRET_KEY=old-secret
ENV
cat >"${runtime_file}" <<'ENV'
TURNSTILE_ENABLED=true
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true
TURNSTILE_SITE_KEY=new-site
TURNSTILE_SECRET_KEY=new-secret
ENV

python3 "${python_body}" "${env_file}" "${runtime_file}" \
	"https://hyperfilelens.com" "47.237.161.194"
grep -Fx 'FRONTEND_URL=https://hyperfilelens.com' "${env_file}" >/dev/null
grep -Fx 'LENS_GATEWAY_BASE_URL=https://hyperfilelens.com/sourcelens' "${env_file}" >/dev/null
grep -Fx 'HFL_ADMIN_PUBLIC_URL=https://47.237.161.194:11444' "${env_file}" >/dev/null
grep -Fx 'HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true' "${env_file}" >/dev/null
grep -E '^DJANGO_ALLOWED_HOSTS=.*47\.237\.161\.194.*hyperfilelens\.com' "${env_file}" >/dev/null
grep -E '^CSRF_TRUSTED_ORIGINS=.*https://hyperfilelens\.com' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_ENABLED=true' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_SITE_KEY=new-site' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_SECRET_KEY=new-secret' "${env_file}" >/dev/null
[[ "$(stat -c '%a' "${env_file}")" == "600" ]]

invalid_env="${tmp}/invalid.env"
invalid_runtime="${tmp}/invalid-runtime.env"
cp "${env_file}" "${invalid_env}"
cat >"${invalid_runtime}" <<'ENV'
TURNSTILE_ENABLED=true
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=invalid
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=invalid secret
ENV
python3 "${python_body}" "${invalid_env}" "${invalid_runtime}" \
	"not a public URL" "47.237.161.194"
grep -Fx 'FRONTEND_URL=https://hyperfilelens.com' "${invalid_env}" >/dev/null
grep -Fx 'TURNSTILE_SITE_KEY=new-site' "${invalid_env}" >/dev/null
grep -Fx 'TURNSTILE_SECRET_KEY=new-secret' "${invalid_env}" >/dev/null
grep -Fx 'HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true' "${invalid_env}" >/dev/null

python3 "${python_body}" "${invalid_env}" "${invalid_runtime}" \
	"https://[invalid" "47.237.161.194"
grep -Fx 'FRONTEND_URL=https://hyperfilelens.com' "${invalid_env}" >/dev/null

printf 'Optional deployment configuration contracts passed.\n'

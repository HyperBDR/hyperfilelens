#!/usr/bin/env bash
# Validate pre-start public URL and runtime feature deployment configuration.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
helper="${ROOT}/deploy/installer/apply-runtime-config.py"
installer="${ROOT}/deploy/installer/install.sh"
remote_deploy="${ROOT}/.github/scripts/remote-deploy.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

python3 -m py_compile "${helper}"

env_file="${tmp}/valid.env"
runtime_file="${tmp}/valid-runtime.env"
cat >"${env_file}" <<'ENV'
FRONTEND_URL=https://47.237.161.194:11443
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,47.237.161.194
CSRF_TRUSTED_ORIGINS=https://127.0.0.1:11443
CORS_ALLOWED_ORIGINS=
LENS_GATEWAY_BASE_URL=https://47.237.161.194:11443/sourcelens
HFL_ADMIN_PUBLIC_URL=
HFL_INSECURE_TLS=1
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=false
TURNSTILE_ENABLED=true
TURNSTILE_SITE_KEY=old-site
TURNSTILE_SECRET_KEY=old-secret
ENV
cat >"${runtime_file}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=0
TURNSTILE_ENABLED=true
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true
TURNSTILE_SITE_KEY=new-site
TURNSTILE_SECRET_KEY=new-secret
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=mailer@example.com
SMTP_PASSWORD=pa$$ word'with\slashes
SMTP_SECURITY=ssl
EMAIL_FROM=HyperFileLens <mailer@example.com>
ENV

runtime_output="$(python3 "${helper}" \
	--env-file "${env_file}" \
	--runtime-env-file "${runtime_file}" \
	--public-url "https://hyperfilelens.com" \
	--direct-host "47.237.161.194")"
if grep -F "pa\$\$ word" <<<"${runtime_output}" >/dev/null; then
	printf 'ERROR: runtime configuration output exposed the SMTP password\n' >&2
	exit 1
fi
grep -Fx 'FRONTEND_URL=https://hyperfilelens.com' "${env_file}" >/dev/null
grep -Fx 'LENS_GATEWAY_BASE_URL=https://hyperfilelens.com/sourcelens' "${env_file}" >/dev/null
grep -Fx 'HFL_ADMIN_PUBLIC_URL=https://47.237.161.194:11444' "${env_file}" >/dev/null
grep -Fx 'HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true' "${env_file}" >/dev/null
grep -Fx 'HFL_INSECURE_TLS=0' "${env_file}" >/dev/null
grep -E '^DJANGO_ALLOWED_HOSTS=.*47\.237\.161\.194.*hyperfilelens\.com' "${env_file}" >/dev/null
grep -E '^CSRF_TRUSTED_ORIGINS=.*https://47\.237\.161\.194:11443.*https://hyperfilelens\.com' "${env_file}" >/dev/null
grep -E '^CORS_ALLOWED_ORIGINS=.*https://47\.237\.161\.194:11443.*https://hyperfilelens\.com' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_ENABLED=true' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_SITE_KEY=new-site' "${env_file}" >/dev/null
grep -Fx 'TURNSTILE_SECRET_KEY=new-secret' "${env_file}" >/dev/null
grep -Fx 'HFL_EMAIL_SIGNUP_ENABLED=false' "${env_file}" >/dev/null
grep -Fx 'EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend' "${env_file}" >/dev/null
grep -Fx 'EMAIL_HOST=smtp.example.com' "${env_file}" >/dev/null
grep -Fx 'EMAIL_PORT=465' "${env_file}" >/dev/null
grep -Fx 'EMAIL_HOST_USER=mailer@example.com' "${env_file}" >/dev/null
grep -Fx 'EMAIL_USE_TLS=false' "${env_file}" >/dev/null
grep -Fx 'EMAIL_USE_SSL=true' "${env_file}" >/dev/null
grep -Fx 'DEFAULT_FROM_EMAIL=HyperFileLens <mailer@example.com>' "${env_file}" >/dev/null
python3 - "${env_file}" <<'PY'
import pathlib
import sys

password_line = next(
    line for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
    if line.startswith("EMAIL_HOST_PASSWORD=")
)
assert password_line == 'EMAIL_HOST_PASSWORD="pa$$$$ word\'with\\\\slashes"'
PY
[[ "$(stat -c '%a' "${env_file}")" == "600" ]]

invalid_env="${tmp}/invalid.env"
invalid_runtime="${tmp}/invalid-runtime.env"
cp "${env_file}" "${invalid_env}"
cat >"${invalid_runtime}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=0
TURNSTILE_ENABLED=true
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=invalid
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=invalid secret
ENV
python3 "${helper}" \
	--env-file "${invalid_env}" \
	--runtime-env-file "${invalid_runtime}" \
	--public-url "not a public URL" \
	--direct-host "47.237.161.194"
grep -Fx 'FRONTEND_URL=https://hyperfilelens.com' "${invalid_env}" >/dev/null
grep -Fx 'TURNSTILE_SITE_KEY=new-site' "${invalid_env}" >/dev/null
grep -Fx 'TURNSTILE_SECRET_KEY=new-secret' "${invalid_env}" >/dev/null
grep -Fx 'HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true' "${invalid_env}" >/dev/null

preserved_env="${tmp}/preserved.env"
empty_smtp_runtime="${tmp}/empty-smtp-runtime.env"
cp "${env_file}" "${preserved_env}"
cat >"${empty_smtp_runtime}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=0
TURNSTILE_ENABLED=true
HFL_PLATFORM_GATEWAY_AUTO_DEPLOY=true
TURNSTILE_SITE_KEY=new-site
TURNSTILE_SECRET_KEY=new-secret
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_SECURITY=
EMAIL_FROM=
ENV
python3 "${helper}" \
	--env-file "${preserved_env}" \
	--runtime-env-file "${empty_smtp_runtime}" >/dev/null
grep -Fx 'EMAIL_HOST=smtp.example.com' "${preserved_env}" >/dev/null
grep -F 'EMAIL_HOST_PASSWORD="pa$$$$ word' "${preserved_env}" >/dev/null

partial_env="${tmp}/partial.env"
partial_runtime="${tmp}/partial-runtime.env"
cp "${env_file}" "${partial_env}"
cat >"${partial_runtime}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=0
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=mailer@example.com
SMTP_PASSWORD=
SMTP_SECURITY=ssl
EMAIL_FROM=HyperFileLens <mailer@example.com>
ENV
before_partial="$(sha256sum "${partial_env}" | awk '{print $1}')"
if python3 "${helper}" --env-file "${partial_env}" \
	--runtime-env-file "${partial_runtime}" >/dev/null 2>&1; then
	printf 'ERROR: partial SMTP deployment configuration must fail\n' >&2
	exit 1
fi
after_partial="$(sha256sum "${partial_env}" | awk '{print $1}')"
[[ "${before_partial}" == "${after_partial}" ]]

insecure_env="${tmp}/insecure.env"
insecure_runtime="${tmp}/insecure-runtime.env"
cp "${env_file}" "${insecure_env}"
cat >"${insecure_runtime}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=1
ENV
python3 "${helper}" --env-file "${insecure_env}" \
	--runtime-env-file "${insecure_runtime}" >/dev/null
grep -Fx 'HFL_INSECURE_TLS=1' "${insecure_env}" >/dev/null

invalid_tls_env="${tmp}/invalid-tls.env"
invalid_tls_runtime="${tmp}/invalid-tls-runtime.env"
cp "${env_file}" "${invalid_tls_env}"
cat >"${invalid_tls_runtime}" <<'ENV'
HFL_EMAIL_SIGNUP_ENABLED=false
HFL_INSECURE_TLS=2
ENV
before_invalid_tls="$(sha256sum "${invalid_tls_env}" | awk '{print $1}')"
if python3 "${helper}" --env-file "${invalid_tls_env}" \
	--runtime-env-file "${invalid_tls_runtime}" >/dev/null 2>&1; then
	printf 'ERROR: runtime configuration accepted invalid HFL_INSECURE_TLS\n' >&2
	exit 1
fi
after_invalid_tls="$(sha256sum "${invalid_tls_env}" | awk '{print $1}')"
[[ "${before_invalid_tls}" == "${after_invalid_tls}" ]]

ln -s "${runtime_file}" "${tmp}/runtime-link.env"
if python3 "${helper}" --env-file "${invalid_env}" \
	--runtime-env-file "${tmp}/runtime-link.env" >/dev/null 2>&1; then
	printf 'ERROR: runtime configuration symlinks must be rejected\n' >&2
	exit 1
fi

install_body="$(sed -n '/^cmd_install()/,/^cmd_start()/p' "${installer}")"
upgrade_body="$(sed -n '/^cmd_upgrade()/,/^main()/p' "${installer}")"
python3 - "${install_body}" "${upgrade_body}" <<'PY'
import sys

install, upgrade = sys.argv[1:]
assert install.index("ensure_env_file") < install.index("apply_runtime_configuration")
assert install.index("apply_runtime_configuration") < install.index("load_images_from_manifest")
assert install.index("apply_runtime_configuration") < install.index("install_bundled_sourcelens")
assert upgrade.index("apply_upgrade_files") < upgrade.index("apply_runtime_configuration")
assert upgrade.index("apply_runtime_configuration") < upgrade.index("install_bundled_sourcelens")
assert upgrade.index("apply_runtime_configuration") < upgrade.index("compose_in_root up -d postgres redis")
PY

grep -F 'bash "${package_root}/install.sh" "${install_args[@]}"' \
	"${remote_deploy}" >/dev/null
grep -F 'RUNTIME_ENV_FILE=""' "${remote_deploy}" >/dev/null
if grep -F -- '--force-recreate' "${remote_deploy}" >/dev/null; then
	printf 'ERROR: remote deployment must not recreate services after installation\n' >&2
	exit 1
fi

printf 'Pre-start deployment configuration contracts passed.\n'

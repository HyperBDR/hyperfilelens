#!/usr/bin/env bash
# Perform a non-blocking public health check only when the configured URL is globally routable.
set -euo pipefail

write_summary() {
	[[ -n "${GITHUB_STEP_SUMMARY:-}" ]] || return 0
	printf '%s\n\n%s\n' "$1" "$2" >>"${GITHUB_STEP_SUMMARY}"
}

finish_nonblocking() {
	local status=$1
	trap - EXIT
	if [[ "${status}" -ne 0 ]]; then
		set +e
		printf '::warning title=Public endpoint check::Check execution failed with status %s; core deployment and host-local health remain authoritative.\n' \
			"${status}"
		write_summary '### Public endpoint check' \
			"Warning: external availability check execution failed with status ${status}. Core deployment and host-local checks passed." \
			|| true
	fi
	exit 0
}
trap 'finish_nonblocking "$?"' EXIT

if [[ -z "${APP_PUBLIC_URL:-}" ]]; then
	printf '%s\n' '::notice title=Public endpoint check::Public URL is not configured; host-local health remains authoritative.'
	write_summary '### Public endpoint check' \
		'Skipped: the target public URL is empty. Core deployment and host-local checks passed.'
	exit 0
fi

classification="$(python3 - "${APP_PUBLIC_URL}" <<'PY'
import ipaddress
import sys
import urllib.parse

value = sys.argv[1]
try:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must include an HTTP(S) scheme and hostname")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost":
        print("private")
    else:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            print("public")
        else:
            print("public" if address.is_global else "private")
except (TypeError, ValueError):
    print("invalid")
PY
)"

case "${classification}" in
private)
	printf '%s\n' '::notice title=Public endpoint check::Private endpoint detected; GitHub-hosted connectivity check was skipped.'
	write_summary '### Public endpoint check' \
		"Skipped: \`${APP_PUBLIC_URL}\` is private or non-global. Core deployment and host-local checks passed."
	;;
invalid)
	printf '::warning title=Public endpoint check::Configured public URL is invalid: %s\n' "${APP_PUBLIC_URL}"
	write_summary '### Public endpoint check' \
		"Warning: \`${APP_PUBLIC_URL}\` is not a valid HTTP(S) URL. Core deployment and host-local checks passed."
	;;
public)
	endpoint="${APP_PUBLIC_URL%/}/health/ready"
	if ! curl -fsS --connect-timeout 10 --max-time 30 --retry 2 "${endpoint}" >/dev/null; then
		printf '::warning title=Public endpoint check::Public endpoint is not ready: %s\n' "${endpoint}"
		write_summary '### Public endpoint check' \
			"Warning: \`${endpoint}\` is not ready. Core deployment and host-local checks passed."
	else
		write_summary '### Public endpoint check' "Passed: \`${endpoint}\`"
	fi
	;;
*)
	printf 'ERROR: unexpected public URL classification: %s\n' "${classification}" >&2
	exit 2
	;;
esac

exit 0

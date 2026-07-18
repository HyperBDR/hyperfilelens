#!/bin/sh
# HyperFileLens frontend log rotation.
#
# Modes:
#   (default)     Hourly loop for frontend container (flock on shared data/logs).
#   --daemon      Fork loop into background (nginx docker-entrypoint.d).
#   install-host  Optional host cron fallback (online dev only; not for offline release).
#
# Examples:
#   logrotate-loop.sh --daemon
#   sudo logrotate-loop.sh install-host --log-dir /opt/hyperfilelens/data/logs
set -eu

INTERVAL="${LOGROTATE_INTERVAL_SECONDS:-3600}"
CONF="${LOGROTATE_CONF:-/etc/logrotate.d/hyperfilelens}"
STATE="${LOGROTATE_STATE:-/var/log/hyperfilelens/.logrotate.status}"
LOCK="${LOGROTATE_LOCK:-/var/log/hyperfilelens/.logrotate.lock}"

log() { printf '[logrotate] %s\n' "$*" >&2; }
die() { printf '[logrotate] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
	cat <<'USAGE'
Usage:
  logrotate-loop.sh [--daemon]              Run hourly loop (frontend container)
  logrotate-loop.sh install-host --log-dir PATH
                                            Install /etc/logrotate.d + hourly cron on host
                                            (optional; release/offline uses frontend image instead)

Environment (loop mode):
  LOGROTATE_INTERVAL_SECONDS  Default 3600
  LOGROTATE_CONF              Default /etc/logrotate.d/hyperfilelens
  LOGROTATE_STATE             Default /var/log/hyperfilelens/.logrotate.status
  LOGROTATE_LOCK              Default /var/log/hyperfilelens/.logrotate.lock
USAGE
}

run_as_root() {
	if [ "$(id -u)" -eq 0 ]; then
		"$@"
	else
		sudo "$@"
	fi
}

install_host() {
	log_dir=""
	while [ $# -gt 0 ]; do
		case "$1" in
		--log-dir)
			shift
			log_dir="${1:-}"
			[ -n "${log_dir}" ] || die "--log-dir requires a path"
			shift
			;;
		*)
			die "unknown option: $1"
			;;
		esac
	done

	[ -n "${log_dir}" ] || {
		usage
		exit 2
	}
	case "${log_dir}" in
	/*) ;;
	*) die "--log-dir must be an absolute path: ${log_dir}" ;;
	esac

	mkdir -p "${log_dir}"
	log_dir="$(cd "${log_dir}" && pwd)"

	host_conf="/etc/logrotate.d/hyperfilelens"
	host_cron="/etc/cron.d/hyperfilelens-logrotate"
	host_state="/var/lib/logrotate/hyperfilelens.status"

	if ! command -v logrotate >/dev/null 2>&1; then
		log "installing logrotate package (requires network)..."
		run_as_root env DEBIAN_FRONTEND=noninteractive apt-get update -qq
		run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends logrotate
	fi

	log "writing ${host_conf} for ${log_dir}/*.log"
	run_as_root tee "${host_conf}" >/dev/null <<EOF
# HyperFileLens server logs (host fallback — production uses frontend container loop)
${log_dir}/*.log {
    daily
    size 500M
    missingok
    rotate 30
    notifempty
    copytruncate
    create 0640 root root
}
EOF
	run_as_root chmod 0644 "${host_conf}"

	run_as_root tee "${host_cron}" >/dev/null <<EOF
0 * * * * root test -x /usr/sbin/logrotate && /usr/sbin/logrotate -s ${host_state} ${host_conf} >/dev/null 2>&1
EOF
	run_as_root chmod 0644 "${host_cron}"

	run_as_root mkdir -p "$(dirname "${host_state}")"
	run_as_root logrotate -d "${host_conf}" >/dev/null 2>&1 || log "dry-run reported issues (config installed)"
	log "host logrotate ready log_dir=${log_dir}"
}

run_loop() {
	mkdir -p /var/log/hyperfilelens

	if [ ! -f "${CONF}" ]; then
		log "ERROR: missing ${CONF}"
		exit 1
	fi

	if ! command -v flock >/dev/null 2>&1; then
		log "ERROR: flock not found (required for multi-frontend log rotation)"
		exit 1
	fi

	exec 200>"${LOCK}"

	log "started interval=${INTERVAL}s conf=${CONF} state=${STATE} lock=${LOCK}"
	while true; do
		if flock -n 200; then
			if logrotate -s "${STATE}" "${CONF}"; then
				log "ok"
			else
				log "logrotate exited $? (continuing)"
			fi
			flock -u 200
		else
			log "skip (lock held by another frontend replica)"
		fi
		sleep "${INTERVAL}"
	done
}

case "${1:-}" in
-h | --help | help)
	usage
	exit 0
	;;
--daemon)
	shift
	"$0" "$@" &
	exit 0
	;;
install-host)
	shift
	install_host "$@"
	;;
"")
	run_loop
	;;
*)
	die "unknown command: $1 (try --help)"
	;;
esac

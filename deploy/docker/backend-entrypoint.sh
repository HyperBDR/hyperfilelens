#!/usr/bin/env sh
set -eu

cd /opt/backend

export PYTHONPATH=/opt/backend
export DJANGO_SETTINGS_MODULE=project.settings

ensure_log_dir() {
  if [ -n "${LOG_FILE:-}" ]; then
    dir="$(dirname "${LOG_FILE}")"
    mkdir -p "${dir}"
    touch "${LOG_FILE}" || true
  fi
}

wait_for_postgres() {
  host="${POSTGRES_HOST:-postgres}"
  port="${POSTGRES_PORT:-5432}"
  echo "[entrypoint] waiting for postgres at ${host}:${port}"
  until python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('${host}', int('${port}'))); s.close()" 2>/dev/null; do
    sleep 2
  done
  echo "[entrypoint] postgres is reachable"
}

run_migrations_and_register() {
  echo "[entrypoint] migrate"
  python manage.py migrate --noinput
  echo "[entrypoint] collectstatic (Django Admin assets only; SPA uses /assets/)"
  python manage.py collectstatic --noinput --clear || python manage.py collectstatic --noinput
  echo "[entrypoint] register periodic tasks"
  python manage.py register_periodic_tasks || true
  if [ "${SEED_INITIAL_DATA:-0}" = "1" ]; then
    echo "[entrypoint] seed initial data"
    python manage.py seed_initial_data \
      --org-name "${SEED_ORG_NAME:-HyperFileLens}" \
      --admin-email "${SEED_ADMIN_EMAIL:-admin@hyperfilelens.com}" \
      --admin-password "${SEED_ADMIN_PASSWORD:-Admin@123}" || true
  fi
}

# Gunicorn (:8000) + Daphne (:8001) in one container; this shell stays PID 1 for SIGTERM.
run_api_stack() {
  API_WORKERS="${API_WORKERS:-4}"
  WS_BIND_HOST="${WS_BIND_HOST:-0.0.0.0}"
  WS_BIND_PORT="${WS_BIND_PORT:-8001}"
  DAPHNE_PID=""
  GUNICORN_PID=""

  api_stack_cleanup() {
    if [ -n "${DAPHNE_PID}" ]; then
      kill -TERM "${DAPHNE_PID}" 2>/dev/null || true
      wait "${DAPHNE_PID}" 2>/dev/null || true
    fi
    if [ -n "${GUNICORN_PID}" ]; then
      kill -TERM "${GUNICORN_PID}" 2>/dev/null || true
      wait "${GUNICORN_PID}" 2>/dev/null || true
    fi
  }

  trap api_stack_cleanup INT TERM

  echo "[entrypoint] start daphne on ${WS_BIND_HOST}:${WS_BIND_PORT}"
  daphne -b "${WS_BIND_HOST}" -p "${WS_BIND_PORT}" project.asgi_ws:application &
  DAPHNE_PID=$!

  echo "[entrypoint] start gunicorn (${API_WORKERS} workers) on 0.0.0.0:8000"
  GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-180}"
  gunicorn -w "${API_WORKERS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    project.asgi_http:application &
  GUNICORN_PID=$!

  wait "${GUNICORN_PID}"
  EXIT=$?
  api_stack_cleanup
  exit "${EXIT}"
}

require_watchfiles() {
  command -v watchfiles >/dev/null 2>&1 || {
    echo "[entrypoint] watchfiles is required for development commands" >&2
    exit 2
  }
}

run_api_dev() {
  ensure_log_dir
  wait_for_postgres
  require_watchfiles
  echo "[entrypoint] watch backend source and restart HTTP/WebSocket API"
  exec watchfiles --filter python "/entrypoint.sh api" /opt/backend
}

run_worker_dev() {
  ensure_log_dir
  wait_for_postgres
  run_migrations_and_register
  require_watchfiles
  echo "[entrypoint] watch backend source and restart celery worker"
  exec watchfiles --filter python \
    "celery -A common worker --loglevel=INFO -Q backend,node.lifecycle,node.ingest" \
    /opt/backend
}

run_scheduler_dev() {
  ensure_log_dir
  wait_for_postgres
  require_watchfiles
  echo "[entrypoint] watch backend source and restart celery scheduler"
  exec watchfiles --filter python \
    "celery -A common beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=INFO" \
    /opt/backend
}

case "${1:-api}" in
  migrate)
    # Ad-hoc only: docker compose run --rm worker migrate
    ensure_log_dir
    wait_for_postgres
    run_migrations_and_register
    echo "[entrypoint] migrations complete"
    exit 0
    ;;
  api)
    ensure_log_dir
    wait_for_postgres
    run_api_stack
    ;;
  api-dev)
    run_api_dev
    ;;
  worker)
    ensure_log_dir
    wait_for_postgres
    run_migrations_and_register
    echo "[entrypoint] start celery worker"
    exec celery -A common worker --loglevel=INFO \
      --concurrency="${CELERY_WORKER_CONCURRENCY:-1}" \
      -Q backend,node.lifecycle,node.ingest
    ;;
  worker-dev)
    run_worker_dev
    ;;
  scheduler)
    ensure_log_dir
    wait_for_postgres
    echo "[entrypoint] start celery scheduler (DatabaseScheduler)"
    exec celery -A common beat \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler \
      --loglevel=INFO
    ;;
  scheduler-dev)
    run_scheduler_dev
    ;;
  *)
    exec "$@"
    ;;
esac

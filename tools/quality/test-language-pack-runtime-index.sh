#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# shellcheck source=../../deploy/installer/install.sh
source "${ROOT_REPO}/deploy/installer/install.sh"

ROOT="${tmp}/runtime"
ensure_data_dirs

python3 - "${ROOT}/data/lang-packs/installed.json" <<'PY'
import json
import pathlib
import stat
import sys

index_path = pathlib.Path(sys.argv[1])
assert json.loads(index_path.read_text(encoding="utf-8")) == {
    "schema": 1,
    "packs": [],
}
assert stat.S_IMODE(index_path.stat().st_mode) == 0o644
PY

mkdir -p "${ROOT}/data/lang-packs/fr"
cat >"${ROOT}/data/lang-packs/fr/manifest.json" <<'JSON'
{
  "schema": 1,
  "id": "fr",
  "display_name": "French",
  "version": "1.0.0",
  "frontend_code": "fr",
  "backend_code": "fr"
}
JSON
printf '%s\n' '{"broken":true}' >"${ROOT}/data/lang-packs/installed.json"
chmod 0600 "${ROOT}/data/lang-packs/installed.json"

ensure_data_dirs

python3 - "${ROOT}/data/lang-packs/installed.json" <<'PY'
import json
import pathlib
import stat
import sys

index_path = pathlib.Path(sys.argv[1])
assert json.loads(index_path.read_text(encoding="utf-8")) == {
    "schema": 1,
    "packs": [
        {
            "id": "fr",
            "display_name": "French",
            "version": "1.0.0",
            "frontend_code": "fr",
            "backend_code": "fr",
        }
    ],
}
assert stat.S_IMODE(index_path.stat().st_mode) == 0o644
PY

for compose_file in docker-compose.yml deploy/docker-compose.yml; do
	grep -F 'https://127.0.0.1:11443/locales/installed.json' \
		"${ROOT_REPO}/${compose_file}" >/dev/null
done
grep -F "printf '%s\\n' '{\"schema\":1,\"packs\":[]}'" \
	"${ROOT_REPO}/dev/stack.sh" >/dev/null

printf 'Language-pack runtime index checks passed.\n'

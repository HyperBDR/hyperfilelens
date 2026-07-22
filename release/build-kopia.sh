#!/usr/bin/env bash
# Release-facing wrapper for the canonical Kopia artifact preparation entrypoint.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${ROOT}/tools/kopia/prepare.sh" "$@"

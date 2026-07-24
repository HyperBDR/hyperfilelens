#!/usr/bin/env bash
# Install host-side tools required by dev/stack.sh on macOS.
set -euo pipefail

[[ "$(uname -s)" == "Darwin" ]] || {
	printf 'ERROR: this bootstrap is only for macOS development hosts\n' >&2
	exit 2
}
command -v brew >/dev/null 2>&1 || {
	printf 'ERROR: Homebrew is required: https://brew.sh\n' >&2
	exit 2
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
brew bundle --file "${ROOT}/dev/Brewfile"

cat <<'EOF'
macOS development tools are ready.

Docker is intentionally not installed or changed. Start Docker Desktop, or
start Colima with linux/amd64 emulation, then run:

  ./dev/stack.sh doctor
  ./dev/stack.sh up
EOF

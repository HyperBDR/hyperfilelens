#!/usr/bin/env bash
# Verify that an older failed Main run cannot become authoritative after main advances.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

git init --bare --quiet "${tmp}/remote.git"
git init --quiet "${tmp}/seed"
git -C "${tmp}/seed" config user.name 'HyperFileLens CI'
git -C "${tmp}/seed" config user.email 'ci@hyperfilelens.invalid'
printf 'first\n' >"${tmp}/seed/state.txt"
git -C "${tmp}/seed" add state.txt
git -C "${tmp}/seed" commit --quiet -m first
git -C "${tmp}/seed" branch -M main
git -C "${tmp}/seed" remote add origin "${tmp}/remote.git"
git -C "${tmp}/seed" push --quiet -u origin main
git --git-dir="${tmp}/remote.git" symbolic-ref HEAD refs/heads/main
git clone --quiet "${tmp}/remote.git" "${tmp}/work"

first_commit="$(git -C "${tmp}/work" rev-parse HEAD)"
[[ "$(cd "${tmp}/work" && "${ROOT}/.github/scripts/check-main-freshness.sh" "${first_commit}")" \
	== "current" ]]

printf 'second\n' >>"${tmp}/seed/state.txt"
git -C "${tmp}/seed" add state.txt
git -C "${tmp}/seed" commit --quiet -m second
git -C "${tmp}/seed" push --quiet origin main
second_commit="$(git -C "${tmp}/seed" rev-parse HEAD)"

[[ "$(cd "${tmp}/work" && "${ROOT}/.github/scripts/check-main-freshness.sh" "${first_commit}")" \
	== "superseded" ]]
[[ "$(cd "${tmp}/work" && "${ROOT}/.github/scripts/check-main-freshness.sh" "${second_commit}")" \
	== "current" ]]

if (cd "${tmp}/work" && "${ROOT}/.github/scripts/check-main-freshness.sh" invalid) \
	>/dev/null 2>&1; then
	printf 'ERROR: invalid Main commit identity was accepted\n' >&2
	exit 1
fi

printf 'Main release freshness contracts passed.\n'

#!/usr/bin/env bash
set -euo pipefail

ROOT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=../lib/version.sh
source "${ROOT_REPO}/tools/lib/version.sh"

artifact_id="$(normalize_artifact_id main-123abcd)"
[[ "${artifact_id}" == "main-123abcd" ]]
[[ "$(artifact_channel "${artifact_id}")" == "main" ]]
[[ "$(release_package_basename_for_version "${artifact_id}" 123abcd)" \
	== "hyperfilelens-main-123abcd.tar.gz" ]]
if (release_package_basename_for_version main-123abcd 7654321) >/dev/null 2>&1; then
	printf 'ERROR: mismatched Main identifier and commit were accepted\n' >&2
	exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
die() { printf 'ERROR: %s\n' "$1" >&2; return "${2:-1}"; }
source <(sed -n '/^read_version_from_dir()/,/^random_hex()/p' \
	"${ROOT_REPO}/deploy/installer/install.sh" | sed '$d')

main_root="${tmp}/hyperfilelens-main-123abcd"
mkdir -p "${main_root}"
printf '%s\n' main-123abcd >"${main_root}/VERSION"
cat >"${main_root}/MANIFEST.json" <<'JSON'
{
  "schema_version": 2,
  "product": "hyperfilelens",
  "channel": "main",
  "artifact_id": "main-123abcd",
  "git_commit": "123abcd000000000000000000000000000000000"
}
JSON
validate_package_identity "${main_root}"
[[ "$(read_version_from_dir "${main_root}")" == "main-123abcd" ]]
[[ "$(read_channel_from_dir "${main_root}")" == "main" ]]

release_root="${tmp}/hyperfilelens-1.2.3"
mkdir -p "${release_root}"
printf '%s\n' 1.2.3 >"${release_root}/VERSION"
cat >"${release_root}/MANIFEST.json" <<'JSON'
{
  "schema_version": 2,
  "product": "hyperfilelens",
  "channel": "release",
  "artifact_id": "v1.2.3",
  "version": "1.2.3",
  "git_commit": "123abcd000000000000000000000000000000000"
}
JSON
validate_package_identity "${release_root}"

python3 - "${main_root}/MANIFEST.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["artifact_id"] = "main-7654321"
path.write_text(json.dumps(manifest), encoding="utf-8")
PY
if validate_package_identity "${main_root}" >/dev/null 2>&1; then
	printf 'ERROR: Main manifest with mismatched identity was accepted\n' >&2
	exit 1
fi

workflow="${ROOT_REPO}/.github/workflows/artifact_pipeline.yml"
main_workflow="${ROOT_REPO}/.github/workflows/test.yml"
release_workflow="${ROOT_REPO}/.github/workflows/release.yml"
production_workflow="${ROOT_REPO}/.github/workflows/production_deploy.yml"
deploy_workflow="${ROOT_REPO}/.github/workflows/deploy_target.yml"
remote_deploy="${ROOT_REPO}/.github/scripts/remote-deploy.sh"
export_sourcelens="${ROOT_REPO}/release/ci/export-sourcelens-bundle.sh"

grep -F 'TAG="main-${GITHUB_SHA:0:7}"' "${workflow}" >/dev/null
grep -F 'needs.prepare.outputs.channel == '\''release'\''' "${workflow}" >/dev/null
grep -F 'Main artifact ID collision:' "${workflow}" >/dev/null
grep -F 'gh release delete "$ARTIFACT_ID" --cleanup-tag --yes' "${workflow}" >/dev/null
grep -F 'channel: main' "${main_workflow}" >/dev/null
grep -F 'refs/heads/main' "${main_workflow}" >/dev/null
grep -F 'vars.TEST_DEPLOY_ENABLED' "${main_workflow}" >/dev/null
grep -F 'target: test' "${workflow}" >/dev/null
grep -F "needs.prepare.outputs.build_required == 'false'" "${workflow}" >/dev/null
grep -F 'test:main|preprod:release|prod:release' "${deploy_workflow}" >/dev/null
grep -F 'channel: release' "${release_workflow}" >/dev/null
grep -F 'workflow_dispatch:' "${production_workflow}" >/dev/null
grep -F 'target: prod' "${production_workflow}" >/dev/null
if grep -F 'target: prod' "${workflow}" >/dev/null; then
	printf 'ERROR: automatic artifact workflow contains a production target\n' >&2
	exit 1
fi
grep -F -- '--allow-main-build' "${remote_deploy}" >/dev/null
grep -F -- '--channel "${{ inputs.channel }}"' "${deploy_workflow}" >/dev/null
grep -F 'normalize_artifact_id "${hfl_version}"' "${export_sourcelens}" >/dev/null

printf 'Main channel build and deployment contracts passed.\n'

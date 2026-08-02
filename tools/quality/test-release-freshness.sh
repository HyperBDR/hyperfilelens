#!/usr/bin/env bash
# Validate stable published-release ordering independently of workflow completion order.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/bin"

cat >"${tmp}/bin/gh" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "api" && "${2:-}" == *"/releases?per_page=100" ]] || exit 2
[[ "${HFL_RELEASE_API_FAIL:-0}" != "1" ]] || exit 1
tr ' ' '\n' <<<"${HFL_PUBLISHED_RELEASE_TAGS:-}"
MOCK
chmod +x "${tmp}/bin/gh"

run_check() {
	PATH="${tmp}/bin:${PATH}" \
		GITHUB_REPOSITORY=HyperBDR/hyperfilelens \
		HFL_RELEASE_FRESHNESS_RETRY_DELAY_SECONDS=0 \
		HFL_PUBLISHED_RELEASE_TAGS="${HFL_PUBLISHED_RELEASE_TAGS:-}" \
		HFL_RELEASE_API_FAIL="${HFL_RELEASE_API_FAIL:-0}" \
		"${ROOT}/.github/scripts/check-release-freshness.sh" "$1"
}

export HFL_PUBLISHED_RELEASE_TAGS='v0.1.9 v0.2.0 v0.10.0 ignored'
[[ "$(run_check v0.10.0)" == "current" ]]
[[ "$(run_check v0.2.0)" == "superseded" ]]
if run_check v0.3.0 >/dev/null 2>&1; then
	printf 'ERROR: unpublished stable release was accepted\n' >&2
	exit 1
fi
if run_check invalid >/dev/null 2>&1; then
	printf 'ERROR: invalid stable release tag was accepted\n' >&2
	exit 1
fi

export HFL_RELEASE_API_FAIL=1
if run_check v0.10.0 >/dev/null 2>&1; then
	printf 'ERROR: failed release API lookup was accepted\n' >&2
	exit 1
fi

artifact_workflow="${ROOT}/.github/workflows/artifact_pipeline.yml"
deploy_workflow="${ROOT}/.github/workflows/deploy_target.yml"
python3 - "${artifact_workflow}" "${deploy_workflow}" <<'PY'
import pathlib
import sys

artifact = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
deploy = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
preprod = artifact[
    artifact.index("  deploy-preprod:") : artifact.index("  cleanup-main-builds:")
]
if "needs.publish-release.outputs.deployable == 'true'" not in preprod:
    raise SystemExit("PREPROD deployment must require the release freshness output")
if "make_latest=legacy" not in artifact:
    raise SystemExit("stable releases must use GitHub's SemVer-compatible Latest policy")
if '--json apiUrl --jq \'.apiUrl\'' not in artifact:
    raise SystemExit("formal publishing must resolve the draft Release API URL")
if "releases/tags/${ARTIFACT_ID}" in artifact:
    raise SystemExit("formal publishing must not use the draft-incompatible tag endpoint")

guard = deploy.index("- name: Guard Current PREPROD Release")
credentials = deploy.index("- name: Install SSH Credentials")
revalidate = deploy.index("- name: Revalidate Current PREPROD Release")
install = deploy.index("- name: Download and Install Release")
for label, block in (
    ("initial", deploy[guard:credentials]),
    ("pre-install", deploy[revalidate:install]),
):
    if "inputs.target == 'preprod' && inputs.channel == 'release'" not in block:
        raise SystemExit(f"{label} PREPROD release guard has the wrong scope")
    if 'check-release-freshness.sh "$ARTIFACT_ID"' not in block:
        raise SystemExit(f"{label} PREPROD release freshness check is missing")
PY

printf 'Stable published-release freshness contracts passed.\n'

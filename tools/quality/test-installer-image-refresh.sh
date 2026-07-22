#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

package_root="${tmp}/package"
fake_bin="${tmp}/bin"
marker="${tmp}/docker-load-called"
mkdir -p "${package_root}/images" "${fake_bin}"
printf 'verified image archive fixture\n' >"${package_root}/images/hfl.tar.gz"
archive_sha="$(sha256sum "${package_root}/images/hfl.tar.gz" | awk '{print $1}')"

write_manifest() {
	local revision=$1
	python3 - "${package_root}/MANIFEST.json" "${archive_sha}" "${revision}" <<'PY'
import json
import pathlib
import sys

path, archive_sha, revision = sys.argv[1:4]
pathlib.Path(path).write_text(
    json.dumps(
        {
            "git_commit": revision,
            "images": [
                {
                    "file": "images/hfl.tar.gz",
                    "refs": [
                        "hyperfilelens-backend:0.1.5",
                        "hyperfilelens-frontend:0.1.5",
                    ],
                    "role": "hyperfilelens",
                    "sha256": archive_sha,
                }
            ],
        }
    ),
    encoding="utf-8",
)
PY
}

cat >"${fake_bin}/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
"load -i")
	: >"${HFL_TEST_LOAD_MARKER}"
	printf 'Loaded image fixture\n'
	;;
"image inspect")
	revision="${HFL_TEST_OLD_REVISION}"
	[[ -f "${HFL_TEST_LOAD_MARKER}" ]] && revision="${HFL_TEST_NEW_REVISION}"
	printf '[{"Config":{"Labels":{"org.opencontainers.image.revision":"%s"}}}]\n' "${revision}"
	;;
*)
	printf 'unexpected fake docker invocation: %s\n' "$*" >&2
	exit 2
	;;
esac
SH
chmod 755 "${fake_bin}/docker"

new_revision="$(printf 'a%.0s' {1..40})"
old_revision="$(printf 'b%.0s' {1..40})"
export HFL_TEST_LOAD_MARKER="${marker}"
export HFL_TEST_NEW_REVISION="${new_revision}"
export HFL_TEST_OLD_REVISION="${old_revision}"
export PATH="${fake_bin}:${PATH}"

write_manifest "${new_revision}"
source "${ROOT}/deploy/installer/install.sh"
load_images_from_manifest 0 "${package_root}"
[[ -f "${marker}" ]] || {
	printf 'ERROR: installer skipped the verified archive when stale tags existed\n' >&2
	exit 1
}

rm -f "${marker}"
write_manifest "${old_revision}"
if load_images_from_manifest 0 "${package_root}" 2>"${tmp}/mismatch.log"; then
	printf 'ERROR: installer accepted an image revision that differed from the release\n' >&2
	exit 1
fi
grep -F 'does not match release' "${tmp}/mismatch.log" >/dev/null

printf 'Installer image refresh contracts passed.\n'

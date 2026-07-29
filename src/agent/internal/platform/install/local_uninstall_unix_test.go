//go:build !windows

package install

import (
	"os"
	"os/exec"
	"strings"
	"testing"
)

func TestWriteUnixUninstallScriptIncludesLogFile(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/run-uninstall.sh"
	err := writeUnixUninstallScript(
		"/opt/hyperfilelens-agent",
		"/var/lib/hyperfilelens-agent",
		"/var/lib/hyperfilelens-agent/logs",
		false,
		UninstallCompletion{
			APIBaseURL: "https://control.example",
			Path:       "/api/v1/node/agent-uninstall/completion/",
			Token:      "signed-test-token",
		},
		path,
	)
	if err != nil {
		t.Fatalf("writeUnixUninstallScript: %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read script: %v", err)
	}
	body := string(raw)
	if !strings.Contains(body, "/var/lib/hyperfilelens-agent/logs/uninstall.log") {
		t.Fatalf("script missing uninstall log path:\n%s", body)
	}
	if !strings.Contains(body, `log "detached uninstall script started`) {
		t.Fatalf("script missing start log line:\n%s", body)
	}
	if !strings.Contains(body, `log "detached uninstall script finished"`) {
		t.Fatalf("script missing finish log line:\n%s", body)
	}
	if !strings.Contains(body, `removed install directory tree $INSTALL_DIR (including backup artifacts)`) {
		t.Fatalf("script should remove install dir tree including backup:\n%s", body)
	}
	if !strings.Contains(body, `script="$INSTALL_DIR/libexec/gateway-lifecycle.sh"`) {
		t.Fatalf("script should prefer the Agent-owned Gateway lifecycle helper:\n%s", body)
	}
	if !strings.Contains(body, `local env_file="$DATA_DIR/agent.env"`) {
		t.Fatalf("script should read Gateway credentials from the resolved data directory:\n%s", body)
	}
	if !strings.Contains(body, `removed gateway resource policy $RESOURCE_DROPIN`) {
		t.Fatalf("script should remove the Data Gateway systemd resource policy:\n%s", body)
	}
	if !strings.Contains(body, `gateway sidecar uninstall failed; keeping the Agent installed for retry`) {
		t.Fatalf("script should fail closed when LensNode removal fails:\n%s", body)
	}
	for _, want := range []string{
		`gateway_sidecar_uninstall_failed`,
		`"lensnode_sidecar"`,
		`managed_mount_cleanup_failed`,
		`"managed_nas_mounts"`,
		`agent_uninstall_failed`,
		`"agent_installation"`,
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("script should report structured cleanup residue %q:\n%s", want, body)
		}
	}
	if strings.Contains(body, `gateway sidecar uninstall reported errors; continuing agent uninstall`) {
		t.Fatalf("script must not remove the Agent after LensNode removal fails:\n%s", body)
	}
	if !strings.Contains(body, `unmount_agent_mounts "$DATA_DIR"`) {
		t.Fatalf("script must unmount Agent-managed NAS shares:\n%s", body)
	}
	if !strings.Contains(body, `for attempt in 1 2 3 4 5 6`) {
		t.Fatalf("script must retry the signed completion callback:\n%s", body)
	}
	if !strings.Contains(body, `rm -f -- "$0"`) {
		t.Fatalf("script must remove its callback-token runner after completion:\n%s", body)
	}
	if !strings.Contains(body, `verify_uninstall_artifacts`) ||
		!strings.Contains(body, `post-uninstall verification failed; Strict Cleanup remains retryable`) {
		t.Fatalf("script must verify service, files, and data before reporting success:\n%s", body)
	}
	if !strings.Contains(body, `Agent-managed NAS mount cleanup failed; preserving Agent files and data for manual retry`) {
		t.Fatalf("script must stop removal when managed mounts remain:\n%s", body)
	}
	unmountAt := strings.Index(body, `unmount_agent_mounts "$DATA_DIR"`)
	stopAt := strings.Index(body, `systemctl stop "$SERVICE_NAME"`)
	removeAt := strings.Index(body, `for target in "$INSTALL_DIR/hfl-agent"`)
	if unmountAt < 0 || stopAt < 0 || removeAt < 0 || unmountAt > stopAt || stopAt > removeAt {
		t.Fatalf("script must unmount managed shares before stopping and removing the Agent:\n%s", body)
	}
	if !strings.Contains(body, `report_uninstall_completion "$rc"`) {
		t.Fatalf("script must report the signed completion result:\n%s", body)
	}
	if !strings.Contains(body, `CALLBACK_TOKEN="signed-test-token"`) {
		t.Fatalf("script must embed the one-time completion token:\n%s", body)
	}
	if !strings.Contains(body, `if [[ -e "$DATA_DIR" ]]; then
            log "data directory $DATA_DIR remains after removal"
            AGENT_ARTIFACTS_FAILED=1
            exit 1`) {
		t.Fatalf("script must verify data directory removal:\n%s", body)
	}
	if out, err := exec.Command("bash", "-n", path).CombinedOutput(); err != nil {
		t.Fatalf("generated uninstall script is not valid bash: %v\n%s", err, out)
	}
}

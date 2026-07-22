//go:build !windows

package install

import (
	"os"
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
	if strings.Contains(body, `gateway sidecar uninstall reported errors; continuing agent uninstall`) {
		t.Fatalf("script must not remove the Agent after LensNode removal fails:\n%s", body)
	}
}

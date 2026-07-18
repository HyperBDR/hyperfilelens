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
}

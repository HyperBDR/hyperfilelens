package install

import (
	"os"
	"strings"
	"testing"
)

func TestAppendUninstallLogCreatesFile(t *testing.T) {
	dir := t.TempDir()
	if err := AppendUninstallLog(dir, "scheduled detached uninstall"); err != nil {
		t.Fatalf("AppendUninstallLog: %v", err)
	}
	raw, err := os.ReadFile(UninstallLogPath(dir))
	if err != nil {
		t.Fatalf("read uninstall log: %v", err)
	}
	body := string(raw)
	if !strings.Contains(body, "scheduled detached uninstall") {
		t.Fatalf("log body %q missing message", body)
	}
	if !strings.Contains(body, "Z") {
		t.Fatalf("log body %q should contain UTC Z suffix", body)
	}
}

func TestUninstallLogPath(t *testing.T) {
	got := UninstallLogPath("/var/lib/hyperfilelens-agent/logs")
	want := "/var/lib/hyperfilelens-agent/logs/uninstall.log"
	if got != want {
		t.Fatalf("UninstallLogPath() = %q, want %q", got, want)
	}
}

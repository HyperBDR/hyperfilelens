package install

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestInterruptedLifecycleSucceededPendingUpgrade(t *testing.T) {
	dataDir := t.TempDir()
	pending := LifecycleUpgradeDir(dataDir)
	if err := os.MkdirAll(pending, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(pending, "package.tar.gz"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	started := time.Now().UTC()
	ok, result := InterruptedLifecycleSucceeded("agent.upgrade", &started, dataDir, "")
	if ok || result != nil {
		t.Fatalf("pending upgrade should stay running, ok=%v result=%v", ok, result)
	}
	if !InterruptedLifecycleStillRunning("agent.upgrade", dataDir) {
		t.Fatal("expected pending upgrade to still be running")
	}
}

func TestInterruptedLifecycleSucceededUpgradeLog(t *testing.T) {
	dataDir := t.TempDir()
	logDir := filepath.Join(dataDir, "logs")
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		t.Fatal(err)
	}
	started := time.Date(2026, 6, 15, 9, 8, 57, 0, time.UTC)
	logLine := "2026-06-15T09:09:03Z install.sh upgrade succeeded\n"
	if err := os.WriteFile(UpgradeLogPath(logDir), []byte(logLine), 0o644); err != nil {
		t.Fatal(err)
	}
	ok, _ := InterruptedLifecycleSucceeded("agent.upgrade", &started, dataDir, logDir)
	if !ok {
		t.Fatal("expected upgrade log success to repair as succeeded")
	}
}

func TestInterruptedLifecycleSucceededDetachedUpgradeLog(t *testing.T) {
	dataDir := t.TempDir()
	logDir := filepath.Join(dataDir, "logs")
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		t.Fatal(err)
	}
	started := time.Date(2026, 7, 2, 10, 54, 40, 0, time.UTC)
	log := `[2026-07-02T10:54:40.205Z] [INFO ] Scheduled detached upgrade (archive=/var/lib/hyperfilelens-agent/lifecycle/upgrade/package.tar.gz).
[2026-07-02T10:55:32.000Z] [ OK  ] Upgrade completed successfully.
`
	if err := os.WriteFile(UpgradeLogPath(logDir), []byte(log), 0o644); err != nil {
		t.Fatal(err)
	}
	ok, result := InterruptedLifecycleSucceeded("agent.upgrade", &started, dataDir, logDir)
	if !ok {
		t.Fatal("expected detached upgrade log success to repair as succeeded")
	}
	if result == nil || result["repaired_after_restart"] != true {
		t.Fatalf("expected detached repair result, got %#v", result)
	}
}

func TestInterruptedLifecycleSucceededUpgradeLogWindows(t *testing.T) {
	dataDir := t.TempDir()
	logDir := filepath.Join(dataDir, "logs")
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		t.Fatal(err)
	}
	started := time.Date(2026, 6, 29, 3, 53, 41, 0, time.UTC)
	logLine := "2026-06-29T03:53:55.857Z install.ps1 upgrade succeeded\n"
	if err := os.WriteFile(UpgradeLogPath(logDir), []byte(logLine), 0o644); err != nil {
		t.Fatal(err)
	}
	ok, _ := InterruptedLifecycleSucceeded("agent.upgrade", &started, dataDir, logDir)
	if !ok {
		t.Fatal("expected Windows upgrade log success to repair as succeeded")
	}
}

func TestInterruptedLifecycleSucceededIgnoresOldLog(t *testing.T) {
	dataDir := t.TempDir()
	logDir := filepath.Join(dataDir, "logs")
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		t.Fatal(err)
	}
	started := time.Date(2026, 6, 15, 10, 0, 0, 0, time.UTC)
	logLine := "2026-06-15T09:09:03Z install.sh upgrade succeeded\n"
	if err := os.WriteFile(UpgradeLogPath(logDir), []byte(logLine), 0o644); err != nil {
		t.Fatal(err)
	}
	ok, _ := InterruptedLifecycleSucceeded("agent.upgrade", &started, dataDir, logDir)
	if ok {
		t.Fatal("expected old log line to be ignored")
	}
}

func TestParseLogLineTimestampBracketed(t *testing.T) {
	line := "[2026-07-02T10:55:32.000Z] [ OK  ] Upgrade completed successfully."
	ts := parseLogLineTimestamp(line)
	if ts == nil {
		t.Fatal("expected bracketed timestamp to parse")
	}
	want := time.Date(2026, 7, 2, 10, 55, 32, 0, time.UTC)
	if !ts.Equal(want) {
		t.Fatalf("timestamp = %s, want %s", ts, want)
	}
}

func TestInterruptedLifecycleSucceededNonLifecycleKind(t *testing.T) {
	started := time.Now().UTC()
	ok, _ := InterruptedLifecycleSucceeded("backup", &started, t.TempDir(), "")
	if ok {
		t.Fatal("expected non-lifecycle kind to remain failed")
	}
}

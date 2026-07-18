package vfs

import (
	"runtime"
	"testing"
)

func TestDefaultAgentDataDir(t *testing.T) {
	got := DefaultAgentDataDir()
	switch runtime.GOOS {
	case "windows":
		if got == "" {
			t.Fatal("expected non-empty Windows default")
		}
	default:
		if got != "/var/lib/hyperfilelens-agent" {
			t.Fatalf("DefaultAgentDataDir() = %q, want /var/lib/hyperfilelens-agent", got)
		}
	}
}

func TestAgentDataDirMatchesDefault(t *testing.T) {
	if AgentDataDir("/opt/hyperfilelens-agent/hfl-agent") != DefaultAgentDataDir() {
		t.Fatal("AgentDataDir should match DefaultAgentDataDir")
	}
}

func TestUnixPaths(t *testing.T) {
	if UnixInstallDir() != "/opt/hyperfilelens-agent" {
		t.Fatalf("UnixInstallDir() = %q", UnixInstallDir())
	}
	if UnixDataDir() != "/var/lib/hyperfilelens-agent" {
		t.Fatalf("UnixDataDir() = %q", UnixDataDir())
	}
}

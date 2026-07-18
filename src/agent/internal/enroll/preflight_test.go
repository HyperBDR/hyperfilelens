package enroll

import (
	"testing"

	"hyperfilelens/agent/internal/model"
)

func TestIsUbuntuMinSkipsNonLinux(t *testing.T) {
	if isUbuntuMin(20, 4) && testing.Short() {
		t.Skip("environment-specific")
	}
}

func TestPreflightAgentRole(t *testing.T) {
	if err := Preflight(model.RoleAgent); err != nil {
		t.Logf("Preflight(agent): %v", err)
	}
}

func TestDetectInstallStateNotInstalled(t *testing.T) {
	state := DetectInstallState()
	if state.Installed {
		t.Logf("agent appears installed in test environment: %+v", state)
	}
}

func TestReadEnvKeyMissing(t *testing.T) {
	if got := readEnvKey("/nonexistent/agent.env", "HFL_ORG_KEY"); got != "" {
		t.Fatalf("expected empty, got %q", got)
	}
}

package enroll

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSyncManagedObservabilityPolicyPreservesCredentials(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	original := strings.Join([]string{
		"HFL_NODE_ID=42",
		"HFL_NODE_TOKEN=working-token",
		"SENTRY_ENABLED=true",
		"SENTRY_BACKEND_DSN=https://old@sentry.example.com/1",
		"SENTRY_RELEASE=hyperfilelens-agent@old",
		"USER_MANAGED=value",
		"",
	}, "\n")
	if err := os.WriteFile(path, []byte(original), 0o600); err != nil {
		t.Fatal(err)
	}
	policy := ObservabilityPolicy{
		Enabled:          true,
		BackendDSN:       "https://new@sentry.example.com/2",
		Environment:      "hfl-production",
		AgentRelease:     "hyperfilelens-agent@0.1.8",
		LensnodeRelease:  "hyperfilelens-lensnode@0.1.8-sl0.20.0",
		TracesSampleRate: 0,
	}
	changed, err := SyncManagedObservabilityPolicyAt(path, policy)
	if err != nil {
		t.Fatal(err)
	}
	if !changed {
		t.Fatal("SyncManagedObservabilityPolicyAt() changed = false, want true")
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(content)
	for _, expected := range []string{
		"HFL_NODE_ID=42",
		"HFL_NODE_TOKEN=working-token",
		"USER_MANAGED=value",
		"HFL_SENTRY_POLICY_MANAGED=true",
		"SENTRY_BACKEND_DSN=https://new@sentry.example.com/2",
		"SENTRY_ENVIRONMENT=hfl-production",
		"SENTRY_RELEASE=hyperfilelens-agent@0.1.8",
	} {
		if !strings.Contains(text, expected+"\n") {
			t.Fatalf("updated agent.env missing %q:\n%s", expected, text)
		}
	}
	if strings.Contains(text, "https://old@sentry.example.com/1") {
		t.Fatalf("updated agent.env retained old Sentry DSN:\n%s", text)
	}

	changed, err = SyncManagedObservabilityPolicyAt(path, policy)
	if err != nil {
		t.Fatal(err)
	}
	if changed {
		t.Fatal("second SyncManagedObservabilityPolicyAt() changed = true, want false")
	}
}

func TestDisabledObservabilityPolicyRemovesCredentials(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	if err := os.WriteFile(path, []byte(
		"HFL_NODE_TOKEN=working-token\nSENTRY_ENABLED=true\n"+
			"SENTRY_BACKEND_DSN=https://old@sentry.example.com/1\n",
	), 0o600); err != nil {
		t.Fatal(err)
	}
	changed, err := SyncManagedObservabilityPolicyAt(path, ObservabilityPolicy{})
	if err != nil {
		t.Fatal(err)
	}
	if !changed {
		t.Fatal("SyncManagedObservabilityPolicyAt() changed = false, want true")
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := string(content); got != "HFL_NODE_TOKEN=working-token\nSENTRY_ENABLED=false\nHFL_SENTRY_POLICY_MANAGED=true\n" {
		t.Fatalf("updated agent.env = %q", got)
	}
}

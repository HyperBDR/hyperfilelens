package enroll

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSyncManagedSentryEnvPreservesCredentialsAndReplacesManagedValues(t *testing.T) {
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
	t.Setenv("SENTRY_ENABLED", "true")
	t.Setenv("SENTRY_BACKEND_DSN", "https://new@sentry.example.com/2")
	t.Setenv("SENTRY_ENVIRONMENT", "hfl-production")
	t.Setenv("SENTRY_RELEASE", "hyperfilelens-agent@0.1.8")
	t.Setenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")
	t.Setenv("HFL_SENTRY_LENSNODE_RELEASE", "hyperfilelens-lensnode@0.1.8-sl0.20.0")

	changed, err := syncManagedSentryEnv(path)
	if err != nil {
		t.Fatal(err)
	}
	if !changed {
		t.Fatal("syncManagedSentryEnv() changed = false, want true")
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

	changed, err = syncManagedSentryEnv(path)
	if err != nil {
		t.Fatal(err)
	}
	if changed {
		t.Fatal("second syncManagedSentryEnv() changed = true, want false")
	}
}

func TestSyncManagedSentryEnvDisablesAndRemovesCredentials(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	if err := os.WriteFile(path, []byte(
		"HFL_NODE_TOKEN=working-token\nSENTRY_ENABLED=true\n"+
			"SENTRY_BACKEND_DSN=https://old@sentry.example.com/1\n",
	), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("SENTRY_ENABLED", "false")

	changed, err := syncManagedSentryEnv(path)
	if err != nil {
		t.Fatal(err)
	}
	if !changed {
		t.Fatal("syncManagedSentryEnv() changed = false, want true")
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := string(content); got != "HFL_NODE_TOKEN=working-token\nSENTRY_ENABLED=false\n" {
		t.Fatalf("updated agent.env = %q", got)
	}
}

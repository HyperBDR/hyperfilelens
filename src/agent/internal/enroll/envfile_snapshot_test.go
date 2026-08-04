package enroll

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestEnrollmentEnvSnapshotRestoresExistingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	original := []byte("HFL_NODE_CREDENTIAL=original\n")
	if err := os.WriteFile(path, original, 0o600); err != nil {
		t.Fatal(err)
	}
	snapshot, err := captureEnrollmentEnvAt(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := writePrivateEnvAtomically(path, []byte("HFL_NODE_TOKEN=temporary\n")); err != nil {
		t.Fatal(err)
	}

	if err := snapshot.restore(); err != nil {
		t.Fatal(err)
	}
	restored, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(restored) != string(original) {
		t.Fatalf("restored agent.env = %q, want %q", restored, original)
	}
}

func TestEnrollmentEnvSnapshotRemovesNewFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	snapshot, err := captureEnrollmentEnvAt(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("temporary\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	if err := snapshot.restore(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("restored absent agent.env still exists: %v", err)
	}
}

func TestEnrollmentEnvSnapshotKeepsNewCredentialDuringRollback(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	original := []byte("HFL_API_BASE=https://console.example\nHFL_NODE_CREDENTIAL=old-secret\n")
	if err := writePrivateEnvAtomically(path, original); err != nil {
		t.Fatal(err)
	}
	snapshot, err := captureEnrollmentEnvAt(path)
	if err != nil {
		t.Fatal(err)
	}
	snapshot = snapshot.withNodeCredential("new-secret")
	snapshot = snapshot.withInstallationID("hfli_stable")
	if err := snapshot.restore(); err != nil {
		t.Fatal(err)
	}
	restored, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(restored)
	if !strings.Contains(text, "HFL_API_BASE=https://console.example") {
		t.Fatalf("rollback lost original configuration: %q", text)
	}
	if !strings.Contains(text, "HFL_NODE_CREDENTIAL=new-secret") || strings.Contains(text, "old-secret") {
		t.Fatalf("rollback did not preserve the issued credential: %q", text)
	}
	if !strings.Contains(text, "HFL_INSTALLATION_ID=hfli_stable") {
		t.Fatalf("rollback did not preserve the current installation identity: %q", text)
	}
}

func TestSyncEnrollmentConsoleSettingsPreservesDurableCredential(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	original := strings.Join([]string{
		"HFL_WSS_URL=wss://old.example/ws",
		"HFL_API_BASE=https://old.example",
		"HFL_ORG_KEY=org_old",
		"HFL_NODE_TOKEN=legacy-shared-token",
		"HFL_NODE_CREDENTIAL=hfln_durable",
		"HFL_NODE_ID=42",
		"HFL_DATA_DIR=/var/lib/hyperfilelens-agent",
		"HFL_NODE_ROLE=agent",
	}, "\n") + "\n"
	if err := os.WriteFile(path, []byte(original), 0o600); err != nil {
		t.Fatal(err)
	}

	err := syncEnrollmentConsoleSettingsAt(path, Config{
		WSSURL:         "wss://new.example/ws",
		APIBase:        "https://new.example",
		OrgKey:         "org_new",
		NodeToken:      "hfls_temporary_session",
		NodeRole:       "agent",
		InstallationID: "hfli_stable",
		InsecureTLS:    true,
	})
	if err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	for _, want := range []string{
		"HFL_WSS_URL=wss://new.example/ws",
		"HFL_API_BASE=https://new.example",
		"HFL_ORG_KEY=org_new",
		"HFL_INSTALLATION_ID=hfli_stable",
		"HFL_NODE_CREDENTIAL=hfln_durable",
		"HFL_NODE_TOKEN=legacy-shared-token",
		"HFL_NODE_ID=42",
	} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q in %q", want, text)
		}
	}
	if strings.Contains(text, "hfls_temporary_session") {
		t.Fatalf("session secret was written to disk: %q", text)
	}
}

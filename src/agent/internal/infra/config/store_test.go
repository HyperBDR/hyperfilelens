package config

import (
	"os"
	"path/filepath"
	"testing"

	"hyperfilelens/agent/internal/model"
)

func TestStoreReloadFromEnvFile(t *testing.T) {
	dir := t.TempDir()
	envPath := filepath.Join(dir, agentEnvFileName)
	if err := WriteEnvFile(envPath, map[string]string{
		"HFL_WSS_URL": "wss://first.example/ws/node/agent/",
		"HFL_NODE_ROLE": "agent",
	}); err != nil {
		t.Fatal(err)
	}

	s := &Store{
		base:     &model.AgentConfig{},
		envPath:  envPath,
		jsonPath: filepath.Join(dir, configJSONName),
	}
	if err := s.reloadLocked(); err != nil {
		t.Fatal(err)
	}
	if got := s.Current().WSSURL; got != "wss://first.example/ws/node/agent/" {
		t.Fatalf("wss_url = %q", got)
	}

	if err := WriteEnvFile(envPath, map[string]string{
		"HFL_WSS_URL": "wss://second.example/ws/node/agent/",
		"HFL_NODE_ROLE": "proxy",
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.Reload(t.Context()); err != nil {
		t.Fatal(err)
	}
	cfg := s.Current()
	if cfg.WSSURL != "wss://second.example/ws/node/agent/" {
		t.Fatalf("wss_url after reload = %q", cfg.WSSURL)
	}
	if cfg.Role != model.RoleProxy {
		t.Fatalf("role after reload = %q", cfg.Role)
	}
}

func TestParseEnvFileRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent.env")
	values := map[string]string{
		"HFL_WSS_URL": "wss://x/ws/",
		"HFL_NODE_TOKEN": "secret-token",
	}
	if err := WriteEnvFile(path, values); err != nil {
		t.Fatal(err)
	}
	got, err := ParseEnvFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if got["HFL_WSS_URL"] != values["HFL_WSS_URL"] {
		t.Fatalf("got %q", got["HFL_WSS_URL"])
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("mode = %o", info.Mode().Perm())
	}
}

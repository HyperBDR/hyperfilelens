package remote

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"hyperfilelens/agent/internal/model"
)

func TestHTTPRegisterNodeIncludesPlatformInventory(t *testing.T) {
	var payload map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/node/nodes/heartbeat/" {
			t.Errorf("unexpected request path %q", r.URL.Path)
		}
		if got := r.Header.Get("X-Org-Key"); got != "test-org" {
			t.Errorf("X-Org-Key=%q", got)
		}
		if got := r.Header.Get("X-Node-Token"); got != "test-token" {
			t.Errorf("X-Node-Token=%q", got)
		}
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Errorf("decode request: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"node_id":42}`))
	}))
	defer server.Close()

	cfg := &model.AgentConfig{
		APIBaseURL: server.URL,
		OrgKey:     "test-org",
		NodeToken:  "test-token",
		Role:       model.RoleAgent,
	}
	nodeID, err := httpRegisterNode(
		context.Background(), cfg, server.URL, cfg.OrgKey, cfg.NodeToken, "1.2.3",
	)
	if err != nil {
		t.Fatal(err)
	}
	if nodeID != "42" {
		t.Fatalf("nodeID=%q", nodeID)
	}

	metadata, ok := payload["metadata"].(map[string]any)
	if !ok {
		t.Fatalf("metadata=%T", payload["metadata"])
	}
	inventory, ok := metadata["inventory"].(map[string]any)
	if !ok {
		t.Fatalf("inventory=%T", metadata["inventory"])
	}
	for _, key := range []string{
		"os_family", "os_name", "os_version", "kernel_version", "arch", "service_manager",
	} {
		if _, exists := inventory[key]; !exists {
			t.Errorf("inventory is missing %q", key)
		}
	}
	if got := inventory["agent_version"]; got != "1.2.3" {
		t.Errorf("agent_version=%v", got)
	}
}

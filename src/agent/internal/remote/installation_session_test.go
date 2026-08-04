package remote

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"hyperfilelens/agent/internal/model"
)

func TestReleaseInstallationSession(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete || r.URL.Path != "/api/v1/node/enrollment/session" {
			t.Fatalf("unexpected request %s %s", r.Method, r.URL.Path)
		}
		if r.Header.Get("X-Org-Key") != "org-a" || r.Header.Get("X-Node-Token") != "session-a" {
			t.Fatal("release request did not include session credentials")
		}
		if r.URL.Query().Get("installation_id") != "host-a" || r.URL.Query().Get("role") != "agent" {
			t.Fatalf("query=%v", r.URL.Query())
		}
		var payload map[string]string
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatal(err)
		}
		if payload["installation_id"] != "host-a" || payload["role"] != "agent" {
			t.Fatalf("payload=%v", payload)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	err := ReleaseInstallationSession(context.Background(), &model.AgentConfig{
		APIBaseURL: server.URL,
		OrgKey:     "org-a",
		NodeToken:  "session-a",
		Role:       model.RoleAgent,
	}, "host-a")
	if err != nil {
		t.Fatal(err)
	}
}

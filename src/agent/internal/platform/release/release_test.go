package release

import (
	"testing"

	"hyperfilelens/agent/internal/model"
)

func TestReleaseQueryValuesReportsLinuxOSVersion(t *testing.T) {
	t.Parallel()
	cfg := &model.AgentConfig{
		OrgKey:    "org_test",
		NodeToken: "token",
		Role:      model.RoleGateway,
	}

	linux := releaseQueryValues(cfg, "linux", "amd64", "https://console.example", "20.04")
	if got := linux.Get("os_version"); got != "20.04" {
		t.Fatalf("linux os_version = %q, want 20.04", got)
	}

	darwin := releaseQueryValues(cfg, "darwin", "amd64", "https://console.example", "14.5")
	if got := darwin.Get("os_version"); got != "" {
		t.Fatalf("darwin os_version = %q, want empty", got)
	}
}

package release

import (
	"bytes"
	"errors"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
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

func TestReleaseRequestErrorDoesNotExposeSignedQuery(t *testing.T) {
	t.Parallel()
	err := &url.Error{
		Op:  "Get",
		URL: "https://console.example/release?token=secret-value",
		Err: errors.New("connection refused"),
	}

	message := sanitizeReleaseRequestError(err).Error()
	if strings.Contains(message, "secret-value") || strings.Contains(message, "token=") {
		t.Fatalf("request error exposed enrollment secret: %s", message)
	}
}

func TestReleaseResponseBodyRedactsEnrollmentSecret(t *testing.T) {
	t.Parallel()
	message := redactReleaseSecret(
		"request /release?token=secret-value was denied",
		"secret-value",
	)
	if strings.Contains(message, "secret-value") {
		t.Fatalf("response error exposed enrollment secret: %s", message)
	}
}

func TestFetchArtifactRejectsOversizedResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(bytes.Repeat([]byte("x"), releaseResponseLimit+1))
	}))
	defer server.Close()

	_, err := FetchArtifact(t.Context(), &model.AgentConfig{
		APIBaseURL: server.URL,
		OrgKey:     "org-a",
		NodeToken:  "token-a",
		Role:       model.RoleAgent,
	})
	if err == nil || !strings.Contains(err.Error(), "response exceeds") {
		t.Fatalf("FetchArtifact error = %v", err)
	}
}

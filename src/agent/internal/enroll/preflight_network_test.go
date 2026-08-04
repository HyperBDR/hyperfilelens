package enroll

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestWebsocketDialAddressUsesDefaultPorts(t *testing.T) {
	t.Parallel()
	tests := map[string]string{
		"wss://hyperfilelens.com/ws/node/agent/":     "hyperfilelens.com:443",
		"ws://console.example/ws/node/agent/":        "console.example:80",
		"wss://console.example:11443/ws/node/agent/": "console.example:11443",
		"wss://[2001:db8::1]/ws/node/agent/":         "[2001:db8::1]:443",
	}
	for raw, want := range tests {
		raw, want := raw, want
		t.Run(raw, func(t *testing.T) {
			t.Parallel()
			parsed, err := url.Parse(raw)
			if err != nil {
				t.Fatal(err)
			}
			if got := websocketDialAddress(parsed); got != want {
				t.Fatalf("websocketDialAddress(%q) = %q, want %q", raw, got, want)
			}
		})
	}
}

func TestCheckWSSReachableAcceptsAuthenticationRejection(t *testing.T) {
	t.Parallel()
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		http.Error(writer, "authentication required", http.StatusForbidden)
	}))
	defer server.Close()

	result := checkWSSReachable(
		context.Background(),
		"ws"+strings.TrimPrefix(server.URL, "http")+"/ws/node/agent/",
	)

	if !result.OK {
		t.Fatalf("authentication rejection should prove route reachability: %+v", result)
	}
}

func TestCheckWSSReachableRejectsMissingRoute(t *testing.T) {
	t.Parallel()
	server := httptest.NewServer(http.NotFoundHandler())
	defer server.Close()

	result := checkWSSReachable(
		context.Background(),
		"ws"+strings.TrimPrefix(server.URL, "http")+"/missing/",
	)

	if result.OK || !strings.Contains(result.Detail, "returned 404") {
		t.Fatalf("missing WebSocket route was not rejected: %+v", result)
	}
}

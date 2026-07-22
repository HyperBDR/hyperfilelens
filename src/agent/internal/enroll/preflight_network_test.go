package enroll

import (
	"net/url"
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

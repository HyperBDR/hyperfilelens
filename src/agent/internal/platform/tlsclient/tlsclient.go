package tlsclient

import (
	"crypto/tls"
	"net/http"
	"os"
	"strings"
)

// InsecureTLSEnabled mirrors bootstrap/enroll tooling: default skip verify unless HFL_INSECURE_TLS=0.
func InsecureTLSEnabled() bool {
	v := strings.TrimSpace(os.Getenv("HFL_INSECURE_TLS"))
	if v == "" {
		return true
	}
	return v != "0"
}

// Transport clones Go's default HTTP transport so proxy and connection-pool
// behavior are preserved when custom TLS policy is required.
func Transport() *http.Transport {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.TLSClientConfig = Config()
	return transport
}

// Config returns TLS settings for outbound HTTPS/WSS clients.
func Config() *tls.Config {
	cfg := &tls.Config{
		CurvePreferences: []tls.CurveID{tls.X25519, tls.CurveP256, tls.CurveP384, tls.CurveP521},
	}
	if InsecureTLSEnabled() {
		cfg.InsecureSkipVerify = true //nolint:gosec // dev/self-signed control plane
	}
	return cfg
}

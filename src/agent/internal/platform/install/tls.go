package install

import (
	"net/http"
	"os"
	"time"

	"hyperfilelens/agent/internal/platform/tlsclient"
)

const downloadResponseHeaderTimeout = 2 * time.Minute

func downloadHTTPClient() *http.Client {
	transport := tlsclient.Transport()
	transport.ResponseHeaderTimeout = downloadResponseHeaderTimeout
	if os.Getenv("HFL_INSECURE_TLS") == "0" {
		transport.TLSClientConfig = nil
	}
	// Do not set Client.Timeout: large offline bundles may legitimately take
	// longer than an hour. Request cancellation remains controlled by ctx.
	return &http.Client{Transport: transport}
}

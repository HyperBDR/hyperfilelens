package install

import (
	"net/http"
	"sync"

	"hyperfilelens/agent/internal/platform/tlsclient"
)

var (
	insecureOnce sync.Once
	insecureTr   *http.Transport
)

func insecureTransport() *http.Transport {
	insecureOnce.Do(func() {
		insecureTr = &http.Transport{
			TLSClientConfig: tlsclient.Config(),
		}
	})
	return insecureTr
}

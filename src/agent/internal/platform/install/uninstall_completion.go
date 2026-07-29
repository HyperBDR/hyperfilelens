package install

import (
	"fmt"
	"net/url"
	"strings"
)

// UninstallCompletion configures the signed callback used by a detached runner.
type UninstallCompletion struct {
	APIBaseURL   string
	Path         string
	Token        string
	InsecureTLS  bool
	ForceCleanup bool
}

// CallbackURL returns a validated absolute completion endpoint.
func (c UninstallCompletion) CallbackURL() (string, error) {
	base := strings.TrimRight(strings.TrimSpace(c.APIBaseURL), "/")
	path := "/" + strings.TrimLeft(strings.TrimSpace(c.Path), "/")
	token := strings.TrimSpace(c.Token)
	if base == "" || strings.TrimSpace(c.Path) == "" || token == "" {
		return "", fmt.Errorf("uninstall completion endpoint and token are required")
	}
	parsed, err := url.Parse(base + path)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return "", fmt.Errorf("invalid uninstall completion endpoint")
	}
	if parsed.Scheme != "https" && parsed.Scheme != "http" {
		return "", fmt.Errorf("unsupported uninstall completion endpoint scheme")
	}
	return parsed.String(), nil
}

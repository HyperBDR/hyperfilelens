package release

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"runtime"
	"strings"
	"time"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/hostinfo"
	"hyperfilelens/agent/internal/platform/tlsclient"
)

const (
	releaseRequestTimeout = 45 * time.Second
	releaseMaxAttempts    = 5
	releaseRetryDelay     = 5 * time.Second
)

// RetryHook is called before sleeping between release API retries.
type RetryHook func(attempt, maxAttempts int, err error)

// FetchDownloadURL resolves a signed agent package URL from the enrollment release API.
func FetchDownloadURL(ctx context.Context, cfg *model.AgentConfig) (downloadURL, version string, err error) {
	return FetchDownloadURLWithRetry(ctx, cfg, nil)
}

// FetchDownloadURLWithRetry resolves a release URL, retrying transient console errors.
func FetchDownloadURLWithRetry(ctx context.Context, cfg *model.AgentConfig, onRetry RetryHook) (downloadURL, version string, err error) {
	var lastErr error
	for attempt := 1; attempt <= releaseMaxAttempts; attempt++ {
		downloadURL, version, err = fetchDownloadURLOnce(ctx, cfg)
		if err == nil {
			return downloadURL, version, nil
		}
		lastErr = err
		if attempt >= releaseMaxAttempts || !IsRetryableReleaseError(err) {
			return "", "", err
		}
		if onRetry != nil {
			onRetry(attempt, releaseMaxAttempts, err)
		}
		select {
		case <-ctx.Done():
			return "", "", ctx.Err()
		case <-time.After(releaseRetryDelay):
		}
	}
	return "", "", lastErr
}

func fetchDownloadURLOnce(ctx context.Context, cfg *model.AgentConfig) (downloadURL, version string, err error) {
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBaseURL), "/")
	if base == "" {
		return "", "", fmt.Errorf("HFL_API_BASE not configured")
	}
	if strings.TrimSpace(cfg.OrgKey) == "" || strings.TrimSpace(cfg.NodeToken) == "" {
		return "", "", fmt.Errorf("HFL_ORG_KEY and HFL_NODE_TOKEN required for artifact download")
	}
	platform := runtime.GOOS
	arch := "amd64"
	if runtime.GOARCH == "arm64" {
		arch = "arm64"
	}
	osVersion := ""
	if platform == "linux" {
		osVersion = strings.TrimSpace(hostinfo.Collect(ctx).OSVersion)
	}
	q := releaseQueryValues(cfg, platform, arch, base, osVersion)
	reqURL := base + "/api/v1/node/enrollment/agent/release?" + q.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return "", "", err
	}
	client := &http.Client{Timeout: releaseRequestTimeout}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{
			TLSClientConfig: tlsclient.Config(),
		}
	}
	resp, err := client.Do(req)
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", "", fmt.Errorf("release API HTTP %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	var parsed map[string]any
	if err := json.Unmarshal(body, &parsed); err != nil {
		return "", "", err
	}
	data := parsed
	if nested, ok := parsed["data"].(map[string]any); ok {
		data = nested
	}
	dl, _ := data["download_url"].(string)
	ver, _ := data["version"].(string)
	if dl == "" {
		return "", "", fmt.Errorf("release API missing download_url")
	}
	return dl, ver, nil
}

func releaseQueryValues(
	cfg *model.AgentConfig,
	platform string,
	arch string,
	apiBase string,
	osVersion string,
) url.Values {
	q := url.Values{
		"org":      {cfg.OrgKey},
		"role":     {string(cfg.Role)},
		"token":    {cfg.NodeToken},
		"platform": {platform},
		"arch":     {arch},
		"api_base": {apiBase},
	}
	if platform == "linux" && strings.TrimSpace(osVersion) != "" {
		q.Set("os_version", strings.TrimSpace(osVersion))
	}
	return q
}

// IsRetryableReleaseError reports whether FetchDownloadURLWithRetry should try again.
func IsRetryableReleaseError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
		return true
	}
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	msg := strings.ToLower(err.Error())
	switch {
	case strings.Contains(msg, "504 gateway time-out"),
		strings.Contains(msg, "502 bad gateway"),
		strings.Contains(msg, "503 service unavailable"),
		strings.Contains(msg, "429 too many requests"),
		strings.Contains(msg, "connection reset"),
		strings.Contains(msg, "connection refused"),
		strings.Contains(msg, "i/o timeout"),
		strings.Contains(msg, "context deadline exceeded"):
		return true
	default:
		return false
	}
}

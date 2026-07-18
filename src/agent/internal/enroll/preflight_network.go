package enroll

import (
	"context"
	"crypto/tls"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"hyperfilelens/agent/internal/platform/tlsclient"
)

func resolveWSSURL(cfg Config) string {
	if wss := strings.TrimSpace(cfg.WSSURL); wss != "" {
		return wss
	}
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBase), "/")
	if base == "" {
		return ""
	}
	parsed, err := url.Parse(base)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return ""
	}
	scheme := "wss"
	if parsed.Scheme == "http" {
		scheme = "ws"
	}
	return scheme + "://" + parsed.Host + "/ws/node/agent/"
}

type reachResult struct {
	OK         bool
	Warning    bool
	Title      string
	Detail     string
	FailDetail string
}

func checkConsoleReachable(ctx context.Context, apiBase string) reachResult {
	base := strings.TrimRight(strings.TrimSpace(apiBase), "/")
	healthURL := base + "/api/v1/node/health"
	if base == "" {
		return reachResult{
			Warning: true,
			Title:   "Console API reachability inconclusive",
			Detail:  "no console URL configured",
		}
	}

	reqCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, healthURL, nil)
	if err != nil {
		return reachResult{
			Warning: true,
			Title:   "Console API reachability inconclusive",
			Detail:  healthURL,
		}
	}

	client := &http.Client{Timeout: 8 * time.Second}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{TLSClientConfig: tlsclient.Config()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return reachResult{
			Warning: true,
			Title:   "Console API is unreachable",
			Detail:  fmt.Sprintf("GET %s — %s", healthURL, shortenErr(err)),
		}
	}
	resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 500 {
		return reachResult{
			OK:     true,
			Title:  "Console API is reachable",
			Detail: fmt.Sprintf("GET %s → %d", healthURL, resp.StatusCode),
		}
	}
	return reachResult{
		Warning: true,
		Title:   "Console API unreachable",
		Detail:  fmt.Sprintf("GET %s → %d", healthURL, resp.StatusCode),
	}
}

func checkWSSReachable(ctx context.Context, wssURL string) reachResult {
	wssURL = strings.TrimSpace(wssURL)
	if wssURL == "" {
		return reachResult{
			Warning: true,
			Title:   "WebSocket reachability inconclusive",
			Detail:  "control plane URL not configured",
		}
	}

	parsed, err := url.Parse(wssURL)
	if err != nil || parsed.Host == "" {
		return reachResult{
			Warning: true,
			Title:   "WebSocket reachability inconclusive",
			Detail:  wssURL,
		}
	}

	endpoint := parsed.Scheme + "://" + parsed.Host
	dialCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
	defer cancel()

	host := parsed.Host
	dialer := net.Dialer{Timeout: 8 * time.Second}

	switch parsed.Scheme {
	case "wss":
		tlsConfig := tlsclient.Config()
		if tlsConfig == nil {
			tlsConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		conn, err := tls.DialWithDialer(&dialer, "tcp", host, tlsConfig)
		if err != nil {
			return reachResult{
				Warning: true,
				Title:   "WebSocket endpoint unreachable",
				Detail:  fmt.Sprintf("%s — %s", endpoint, shortenErr(err)),
			}
		}
		_ = conn.Close()
		return reachResult{
			OK:     true,
			Title:  "Control plane WebSocket endpoint reachable",
			Detail: endpoint,
		}
	case "ws":
		conn, err := dialer.DialContext(dialCtx, "tcp", host)
		if err != nil {
			return reachResult{
				Warning: true,
				Title:   "WebSocket endpoint unreachable",
				Detail:  fmt.Sprintf("%s — %s", endpoint, shortenErr(err)),
			}
		}
		_ = conn.Close()
		return reachResult{
			OK:     true,
			Title:  "Control plane WebSocket endpoint reachable",
			Detail: endpoint,
		}
	default:
		return reachResult{
			Warning: true,
			Title:   "WebSocket reachability inconclusive",
			Detail:  wssURL,
		}
	}
}

const maxClockSkew = 5 * time.Minute

type clockCheckResult struct {
	OK      bool
	Warning bool
	Title   string
	Detail  string
}

func checkClockSync(ctx context.Context, apiBase string) clockCheckResult {
	base := strings.TrimRight(strings.TrimSpace(apiBase), "/")
	if base == "" {
		return clockCheckResult{
			Warning: true,
			Title:   "System clock could not be verified",
			Detail:  "no console URL configured",
		}
	}

	reqCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
	defer cancel()
	healthURL := base + "/api/v1/node/health"
	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, healthURL, nil)
	if err != nil {
		return clockCheckResult{
			Warning: true,
			Title:   "System clock could not be verified",
			Detail:  healthURL,
		}
	}

	client := &http.Client{Timeout: 8 * time.Second}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{TLSClientConfig: tlsclient.Config()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return clockCheckResult{
			Warning: true,
			Title:   "System clock could not be verified",
			Detail:  "console unreachable",
		}
	}
	defer resp.Body.Close()

	dateHeader := resp.Header.Get("Date")
	if dateHeader == "" {
		return clockCheckResult{
			OK:     true,
			Title:  "System clock assumed correct",
			Detail: "console did not return Date header",
		}
	}
	serverTime, err := http.ParseTime(dateHeader)
	if err != nil {
		return clockCheckResult{
			Warning: true,
			Title:   "System clock could not be verified",
			Detail:  "invalid Date header from console",
		}
	}

	skew := time.Since(serverTime)
	if skew < 0 {
		skew = -skew
	}
	skewLabel := skew.Round(time.Second).String()
	if skew > maxClockSkew {
		return clockCheckResult{
			Warning: true,
			Title:   "System clock may be out of sync",
			Detail:  "skew " + skewLabel,
		}
	}
	return clockCheckResult{
		OK:     true,
		Title:  "System clock synchronized",
		Detail: "skew " + skewLabel,
	}
}

func shortenErr(err error) string {
	if err == nil {
		return "unknown error"
	}
	msg := strings.TrimSpace(err.Error())
	if len(msg) > 120 {
		return msg[:117] + "..."
	}
	return msg
}

func logReachResult(r reachResult) {
	switch {
	case r.OK:
		logOKDetail(r.Title, r.Detail)
	case r.Warning:
		logWarnDetail(r.Title, r.Detail)
	default:
		logFailDetail(r.Title, r.Detail, 2)
	}
}

func logClockResult(r clockCheckResult) {
	switch {
	case r.OK:
		logOKDetail(r.Title, r.Detail)
	case r.Warning:
		logWarnDetail(r.Title, r.Detail)
	}
}

package enrollmentclient

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"hyperfilelens/agent/internal/model"
)

// WaitNodeOnline waits until the control plane confirms a routable WebSocket.
func WaitNodeOnline(
	ctx context.Context,
	cfg *model.AgentConfig,
	nodeID string,
	timeout time.Duration,
) error {
	deadline := time.Now().Add(timeout)
	var lastStatus string
	for {
		online, status, err := fetchNodeOnline(ctx, cfg, nodeID)
		if err == nil && online {
			return nil
		}
		if status != "" {
			lastStatus = status
		}
		if time.Now().After(deadline) {
			if lastStatus == "" {
				lastStatus = "unknown"
			}
			return fmt.Errorf("node did not become online within %s (last status: %s)", timeout, lastStatus)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}
}

func fetchNodeOnline(ctx context.Context, cfg *model.AgentConfig, nodeID string) (bool, string, error) {
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBaseURL), "/")
	endpoint := base + "/api/v1/node/enrollment/node-status?node_id=" + url.QueryEscape(nodeID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return false, "", err
	}
	req.Header.Set("X-Org-Key", cfg.OrgKey)
	req.Header.Set("X-Node-Token", cfg.NodeToken)
	resp, err := enrollmentHTTPClient(10 * time.Second).Do(req)
	if err != nil {
		return false, "", err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return false, "", fmt.Errorf("node status HTTP %s: %s", resp.Status, strings.TrimSpace(string(raw)))
	}
	var payload struct {
		Status   string `json:"status"`
		Routable bool   `json:"routable"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		return false, "", err
	}
	return payload.Routable && payload.Status == "online", payload.Status, nil
}

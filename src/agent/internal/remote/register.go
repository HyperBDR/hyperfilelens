package remote

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"hyperfilelens/agent/internal/infra/config"
	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/hostinfo"
	"hyperfilelens/agent/internal/platform/tlsclient"
	"hyperfilelens/agent/internal/selfupdate"
)

// NodeRegistrar persists a control-plane node id after HTTP enrollment.
type NodeRegistrar interface {
	SetNodeID(ctx context.Context, nodeID string) error
}

// EnsureNodeRegistered fills HFL_NODE_ID via HTTP heartbeat when missing but credentials exist.
func EnsureNodeRegistered(ctx context.Context, provider config.Provider, reg NodeRegistrar) error {
	if provider == nil {
		return nil
	}
	cfg := provider.Current()
	if strings.TrimSpace(cfg.NodeID) != "" {
		return nil
	}
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBaseURL), "/")
	org := strings.TrimSpace(cfg.OrgKey)
	token := strings.TrimSpace(cfg.NodeToken)
	if base == "" || org == "" || token == "" {
		return fmt.Errorf("node_id missing; set HFL_NODE_ID or configure HFL_API_BASE, HFL_ORG_KEY, HFL_NODE_TOKEN")
	}

	nodeID, err := httpRegisterNode(ctx, cfg, base, org, token, selfupdate.Version)
	if err != nil {
		return err
	}
	if reg == nil {
		return fmt.Errorf("node_id %q from heartbeat but no registrar to persist", nodeID)
	}
	return reg.SetNodeID(ctx, nodeID)
}

// RegisterNodeHTTP registers this host via enrollment heartbeat and returns node_id.
func RegisterNodeHTTP(ctx context.Context, cfg *model.AgentConfig, agentVersion string) (string, error) {
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBaseURL), "/")
	org := strings.TrimSpace(cfg.OrgKey)
	token := strings.TrimSpace(cfg.NodeToken)
	if base == "" || org == "" || token == "" {
		return "", fmt.Errorf("HFL_API_BASE, HFL_ORG_KEY, and HFL_NODE_TOKEN required")
	}
	if strings.TrimSpace(agentVersion) == "" {
		agentVersion = selfupdate.Version
	}
	return httpRegisterNode(ctx, cfg, base, org, token, agentVersion)
}

func httpRegisterNode(
	ctx context.Context,
	cfg *model.AgentConfig,
	base, org, token, agentVersion string,
) (string, error) {
	hostname, _ := os.Hostname()
	platform := hostinfo.Collect(ctx)
	inventory := platform.Inventory()
	inventory["hostname"] = hostname
	inventory["agent_version"] = agentVersion
	body := map[string]any{
		"name":    hostname,
		"role":    string(cfg.Role),
		"version": agentVersion,
		"os_name": platform.Description(),
		"metadata": map[string]any{
			"hostname":      hostname,
			"inventory":     inventory,
			"install":       "hfl-enroll",
			"agent_version": agentVersion,
			"platform":      platform.OSFamily,
			"arch":          platform.Arch,
		},
	}
	if id := strings.TrimSpace(cfg.NodeID); id != "" {
		if n, err := strconv.ParseInt(id, 10, 64); err == nil {
			body["node_id"] = n
		}
	}
	payload, err := json.Marshal(body)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		base+"/api/v1/node/nodes/heartbeat/",
		bytes.NewReader(payload),
	)
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Org-Key", org)
	req.Header.Set("X-Node-Token", token)

	client := &http.Client{Timeout: 30 * time.Second}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{TLSClientConfig: tlsclient.Config()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("heartbeat HTTP %s: %s", resp.Status, strings.TrimSpace(string(raw)))
	}

	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return "", fmt.Errorf("heartbeat response: %w", err)
	}
	data := parsed
	if nested, ok := parsed["data"].(map[string]any); ok {
		data = nested
	}
	switch v := data["node_id"].(type) {
	case float64:
		return fmt.Sprintf("%.0f", v), nil
	case json.Number:
		return v.String(), nil
	case string:
		if strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v), nil
		}
	}
	return "", fmt.Errorf("heartbeat missing node_id")
}

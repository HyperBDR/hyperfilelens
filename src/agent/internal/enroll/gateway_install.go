package enroll

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/tlsclient"
)

// LensSidecarConfig holds SourceLens LensNode credentials for gateway sidecar install.
type LensSidecarConfig struct {
	LensBaseURL       string
	LensnodeUUID      string
	LensnodeToken     string
	LensnodeName      string
	WorkspaceRoot     string
}

// RunGatewayInstall installs the HFL agent and SourceLens LensNode sidecar for role=gateway.
func RunGatewayInstall(ctx context.Context, opts InstallOptions) error {
	cfg, err := LoadConfigFromEnv()
	if err != nil {
		logFail(err.Error(), 2)
	}
	if cfg.NodeRole != model.RoleGateway {
		logFail("gateway-install requires HFL_NODE_ROLE=gateway (use the Data Gateway enrollment link)", 2)
	}
	if runtime.GOOS != "linux" {
		logFail("gateway-install is Linux-only", 2)
	}

	if err := RunInstall(ctx, opts); err != nil {
		return err
	}

	logStep("Continuing Data Gateway setup (AI engine).")

	nodeID := strings.TrimSpace(ReadNodeID(EnvFilePath()))
	if nodeID == "" {
		logFail("Agent registered but node_id is missing from agent.env", 5)
	}

	logStep("Fetching LensNode configuration from the console.")
	lensCfg, err := FetchGatewayLensConfig(ctx, cfg, nodeID)
	if err != nil {
		_ = ReportGatewayInstallStatus(ctx, cfg, nodeID, "failed", err.Error())
		logFail("LensNode configuration is unavailable: "+err.Error(), 6)
	}

	logStep("Installing AI engine.")
	if err := ensureGatewayDocker(ctx, cfg); err != nil {
		_ = ReportGatewayInstallStatus(ctx, cfg, nodeID, "failed", err.Error())
		logFail("Docker setup failed: "+err.Error(), 7)
	}
	if lensSidecarHealthy() && os.Getenv("HFL_FORCE_SIDECAR_INSTALL") != "1" {
		logOK("AI engine is already running.")
		_ = ReportGatewayInstallStatus(ctx, cfg, nodeID, "success", "")
		info := summaryFromState(cfg.APIBase, nodeID, "", serviceState(ctx))
		printGatewayInstallSuccess(info, lensCfg)
		return nil
	}
	if err := InstallLensSidecar(ctx, cfg, lensCfg); err != nil {
		_ = ReportGatewayInstallStatus(ctx, cfg, nodeID, "failed", err.Error())
		logFail("AI engine install failed: "+err.Error(), 7)
	}
	_ = ReportGatewayInstallStatus(ctx, cfg, nodeID, "success", "")
	logOK("AI engine was installed successfully.")

	info := summaryFromState(cfg.APIBase, nodeID, "", serviceState(ctx))
	printGatewayInstallSuccess(info, lensCfg)
	return nil
}

// FetchGatewayLensConfig retrieves LensNode credentials for an enrolled gateway.
func FetchGatewayLensConfig(ctx context.Context, cfg Config, nodeID string) (LensSidecarConfig, error) {
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBase), "/")
	org := strings.TrimSpace(cfg.OrgKey)
	token := strings.TrimSpace(cfg.NodeToken)
	if base == "" || org == "" || token == "" || strings.TrimSpace(nodeID) == "" {
		return LensSidecarConfig{}, fmt.Errorf("missing API credentials or node_id")
	}

	url := fmt.Sprintf("%s/api/v1/node/enrollment/gateway-lens-config?node_id=%s", base, nodeID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return LensSidecarConfig{}, err
	}
	req.Header.Set("X-Org-Key", org)
	req.Header.Set("X-Node-Token", token)

	client := &http.Client{Timeout: 30 * time.Second}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{TLSClientConfig: tlsclient.Config()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return LensSidecarConfig{}, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 8192))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return LensSidecarConfig{}, fmt.Errorf("HTTP %s: %s", resp.Status, strings.TrimSpace(string(raw)))
	}

	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return LensSidecarConfig{}, fmt.Errorf("parse response: %w", err)
	}
	data := parsed
	if nested, ok := parsed["data"].(map[string]any); ok {
		data = nested
	}
	lensRaw, ok := data["lens"].(map[string]any)
	if !ok {
		return LensSidecarConfig{}, fmt.Errorf("response missing lens block")
	}

	cfgOut := LensSidecarConfig{
		LensBaseURL:       stringField(lensRaw, "lens_base_url"),
		LensnodeUUID:      stringField(lensRaw, "lensnode_uuid"),
		LensnodeToken:     stringField(lensRaw, "lensnode_token"),
		LensnodeName:      stringField(lensRaw, "lensnode_name"),
		WorkspaceRoot:     stringField(lensRaw, "workspace_root"),
	}
	if cfgOut.LensBaseURL == "" || cfgOut.LensnodeToken == "" || cfgOut.LensnodeUUID == "" {
		return LensSidecarConfig{}, fmt.Errorf("incomplete lens configuration from console")
	}
	if cfgOut.WorkspaceRoot == "" {
		cfgOut.WorkspaceRoot = "/workspace"
	}
	return cfgOut, nil
}

// ReportGatewayInstallStatus notifies the console when gateway-install succeeds or fails.
func ReportGatewayInstallStatus(ctx context.Context, cfg Config, nodeID, status, message string) error {
	base := strings.TrimRight(strings.TrimSpace(cfg.APIBase), "/")
	org := strings.TrimSpace(cfg.OrgKey)
	token := strings.TrimSpace(cfg.NodeToken)
	nodeID = strings.TrimSpace(nodeID)
	status = strings.TrimSpace(strings.ToLower(status))
	if base == "" || org == "" || token == "" || nodeID == "" || status == "" {
		return fmt.Errorf("missing credentials for install status report")
	}

	body, err := json.Marshal(map[string]string{
		"node_id":       nodeID,
		"status":        status,
		"error_message": strings.TrimSpace(message),
	})
	if err != nil {
		return err
	}

	url := base + "/api/v1/node/enrollment/gateway-install-status"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Org-Key", org)
	req.Header.Set("X-Node-Token", token)

	client := &http.Client{Timeout: 15 * time.Second}
	if tlsclient.InsecureTLSEnabled() {
		client.Transport = &http.Transport{TLSClientConfig: tlsclient.Config()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return fmt.Errorf("HTTP %s: %s", resp.Status, strings.TrimSpace(string(raw)))
	}
	return nil
}

func stringField(m map[string]any, key string) string {
	v, ok := m[key]
	if !ok || v == nil {
		return ""
	}
	switch s := v.(type) {
	case string:
		return strings.TrimSpace(s)
	default:
		return strings.TrimSpace(fmt.Sprint(v))
	}
}

func printGatewayInstallSuccess(info SummaryInfo, lens LensSidecarConfig) {
	printSummaryBlock(info)
	printNextStep("Data gateway and AI engine are ready. Return to Insights → Data Gateways to add knowledge sources.")
	if lens.WorkspaceRoot != "" {
		printResult("Workspace root: " + lens.WorkspaceRoot)
	}
}

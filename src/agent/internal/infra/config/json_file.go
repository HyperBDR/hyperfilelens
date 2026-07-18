package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const configJSONName = "config.json"

// JSONOverlay holds optional structured overrides (merged after agent.env on reload).
type JSONOverlay struct {
	WSSURL     string `json:"wss_url,omitempty"`
	APIBaseURL string `json:"api_base_url,omitempty"`
	OrgKey     string `json:"org_key,omitempty"`
	NodeID     string `json:"node_id,omitempty"`
	NodeToken  string `json:"node_token,omitempty"`
	DataDir    string `json:"data_dir,omitempty"`
	LogDir     string `json:"log_dir,omitempty"`
	KopiaPath  string `json:"kopia_path,omitempty"`
	Role       string `json:"role,omitempty"`
}

func jsonConfigPath(dataDir string) string {
	return filepath.Join(dataDir, configJSONName)
}

func readJSONOverlay(path string) (JSONOverlay, error) {
	var overlay JSONOverlay
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return overlay, nil
		}
		return overlay, err
	}
	if err := json.Unmarshal(b, &overlay); err != nil {
		return overlay, err
	}
	return overlay, nil
}

func writeJSONOverlay(path string, overlay JSONOverlay) error {
	b, err := json.MarshalIndent(overlay, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o600)
}

func overlayToEnvMap(o JSONOverlay) map[string]string {
	out := map[string]string{}
	put := func(env, val string) {
		if val != "" {
			out[env] = val
		}
	}
	put("HFL_WSS_URL", o.WSSURL)
	put("HFL_API_BASE", o.APIBaseURL)
	put("HFL_ORG_KEY", o.OrgKey)
	put("HFL_NODE_ID", o.NodeID)
	put("HFL_NODE_TOKEN", o.NodeToken)
	put("HFL_DATA_DIR", o.DataDir)
	put("HFL_LOG_DIR", o.LogDir)
	put("HFL_KOPIA_PATH", o.KopiaPath)
	put("HFL_NODE_ROLE", o.Role)
	return out
}

func envMapToOverlay(values map[string]string) JSONOverlay {
	var o JSONOverlay
	if values == nil {
		return o
	}
	o.WSSURL = values["HFL_WSS_URL"]
	o.APIBaseURL = values["HFL_API_BASE"]
	o.OrgKey = values["HFL_ORG_KEY"]
	o.NodeID = values["HFL_NODE_ID"]
	o.NodeToken = values["HFL_NODE_TOKEN"]
	o.DataDir = values["HFL_DATA_DIR"]
	o.LogDir = values["HFL_LOG_DIR"]
	o.KopiaPath = values["HFL_KOPIA_PATH"]
	o.Role = values["HFL_NODE_ROLE"]
	return o
}

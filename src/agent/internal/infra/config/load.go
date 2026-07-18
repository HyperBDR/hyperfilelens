package config

import (
	"os"
	"path/filepath"
	"strings"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/vfs"
)

// Overrides are non-empty CLI values applied once at startup (not re-read on reload).
type Overrides struct {
	WSSURL     string
	APIBaseURL string
	OrgKey     string
	NodeID     string
	NodeToken  string
	DataDir    string
	LogDir     string
	KopiaPath  string
	Role       model.Role
}

// LoadOptions configures the initial Store bootstrap.
type LoadOptions struct {
	Overrides Overrides
}

// ResolveDataDir picks the agent state directory before config files are known.
func ResolveDataDir(o Overrides) (string, error) {
	if s := strings.TrimSpace(o.DataDir); s != "" {
		return filepath.Clean(s), nil
	}
	if s := strings.TrimSpace(os.Getenv("HFL_DATA_DIR")); s != "" {
		return filepath.Clean(s), nil
	}
	if home := strings.TrimSpace(os.Getenv("HFL_AGENT_HOME")); home != "" {
		return filepath.Clean(home), nil
	}
	return vfs.DefaultAgentDataDir(), nil
}

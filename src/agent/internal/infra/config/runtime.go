package config

import (
	"os"
	"path/filepath"
	"strings"

	"hyperfilelens/agent/internal/model"
)

// BootstrapAgentHome loads "<home>/agent.env" into the environment (without overriding existing vars),
// then sets HFL_DATA_DIR to home when still unset. Single-root portable layout.
func BootstrapAgentHome() error {
	home := strings.TrimSpace(os.Getenv("HFL_AGENT_HOME"))
	if home == "" {
		return nil
	}
	home = filepath.Clean(home)
	if err := LoadEnvFile(filepath.Join(home, "agent.env")); err != nil {
		return err
	}
	if strings.TrimSpace(os.Getenv("HFL_DATA_DIR")) == "" {
		return os.Setenv("HFL_DATA_DIR", home)
	}
	return nil
}

// RuntimeFromEnv builds a config snapshot from HFL_* environment variables.
func RuntimeFromEnv() *model.AgentConfig {
	return &model.AgentConfig{
		WSSURL:     strings.TrimSpace(os.Getenv("HFL_WSS_URL")),
		APIBaseURL: firstNonEmpty(strings.TrimSpace(os.Getenv("HFL_API_BASE")), strings.TrimSpace(os.Getenv("HFL_CONTROL_PLANE_API"))),
		OrgKey:     strings.TrimSpace(os.Getenv("HFL_ORG_KEY")),
		NodeID:     strings.TrimSpace(os.Getenv("HFL_NODE_ID")),
		NodeToken:  strings.TrimSpace(os.Getenv("HFL_NODE_TOKEN")),
		DataDir:    strings.TrimSpace(os.Getenv("HFL_DATA_DIR")),
		LogDir:     strings.TrimSpace(os.Getenv("HFL_LOG_DIR")),
		KopiaPath:  strings.TrimSpace(os.Getenv("HFL_KOPIA_PATH")),
		Role:       roleFromEnv(),
	}
}

func roleFromEnv() model.Role {
	s := strings.TrimSpace(os.Getenv("HFL_NODE_ROLE"))
	if s == "" {
		return ""
	}
	r, err := model.ParseRole(s)
	if err != nil {
		return ""
	}
	return r
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

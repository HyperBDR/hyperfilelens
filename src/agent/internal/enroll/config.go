package enroll

import (
	"fmt"
	"os"
	"strings"

	"hyperfilelens/agent/internal/model"
)

// Config holds enrollment credentials from HFL_* environment variables.
type Config struct {
	OrgKey     string
	NodeRole   model.Role
	NodeToken  string
	APIBase    string
	WSSURL     string
	InsecureTLS bool
}

// LoadConfigFromEnv reads enrollment settings injected by bootstrap stubs.
func LoadConfigFromEnv() (Config, error) {
	roleRaw := strings.TrimSpace(os.Getenv("HFL_NODE_ROLE"))
	if roleRaw == "" {
		roleRaw = "agent"
	}
	role, err := model.ParseRole(roleRaw)
	if err != nil {
		return Config{}, err
	}
	cfg := Config{
		OrgKey:      strings.TrimSpace(os.Getenv("HFL_ORG_KEY")),
		NodeRole:    role,
		NodeToken:   strings.TrimSpace(os.Getenv("HFL_NODE_TOKEN")),
		APIBase:     strings.TrimRight(strings.TrimSpace(os.Getenv("HFL_API_BASE")), "/"),
		WSSURL:      strings.TrimSpace(os.Getenv("HFL_WSS_URL")),
		InsecureTLS: os.Getenv("HFL_INSECURE_TLS") != "0",
	}
	if cfg.OrgKey == "" || cfg.NodeToken == "" || cfg.APIBase == "" {
		return Config{}, fmt.Errorf("HFL_ORG_KEY, HFL_NODE_TOKEN, and HFL_API_BASE are required")
	}
	if !cfg.InsecureTLS {
		_ = os.Setenv("HFL_INSECURE_TLS", "0")
	} else {
		_ = os.Setenv("HFL_INSECURE_TLS", "1")
	}
	return cfg, nil
}

// AgentConfig converts to model.AgentConfig for release/register APIs.
func (c Config) AgentConfig() *model.AgentConfig {
	envPath := EnvFilePath()
	return &model.AgentConfig{
		WSSURL:     c.WSSURL,
		APIBaseURL: c.APIBase,
		OrgKey:     c.OrgKey,
		NodeToken:  c.NodeToken,
		NodeID:     ReadNodeID(envPath),
		Role:       c.NodeRole,
		DataDir:    dataDirForAgent(),
	}
}

// EnvFilePath returns the platform default agent.env path.
func EnvFilePath() string {
	if os.Getenv("ProgramFiles") != "" || os.Getenv("OS") == "Windows_NT" {
		pd := os.Getenv("ProgramData")
		if pd == "" {
			pd = `C:\ProgramData`
		}
		return pd + `\HyperFileLens\Agent\agent.env`
	}
	return dataDirForAgent() + "/agent.env"
}

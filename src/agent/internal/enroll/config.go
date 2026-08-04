package enroll

import (
	"fmt"
	"os"
	"strings"

	"hyperfilelens/agent/internal/model"
)

// Config holds enrollment credentials from HFL_* environment variables.
type Config struct {
	OrgKey         string
	NodeRole       model.Role
	NodeToken      string
	InstallationID string
	GatewayScope   string
	APIBase        string
	WSSURL         string
	InsecureTLS    bool
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
		OrgKey:         strings.TrimSpace(os.Getenv("HFL_ORG_KEY")),
		NodeRole:       role,
		NodeToken:      firstNonEmptyValue(os.Getenv("HFL_NODE_CREDENTIAL"), os.Getenv("HFL_NODE_TOKEN")),
		InstallationID: strings.TrimSpace(os.Getenv("HFL_INSTALLATION_ID")),
		GatewayScope:   strings.TrimSpace(os.Getenv("HFL_GATEWAY_SCOPE")),
		APIBase:        strings.TrimRight(strings.TrimSpace(os.Getenv("HFL_API_BASE")), "/"),
		WSSURL:         strings.TrimSpace(os.Getenv("HFL_WSS_URL")),
		InsecureTLS:    os.Getenv("HFL_INSECURE_TLS") != "0",
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

func firstNonEmptyValue(values ...string) string {
	for _, value := range values {
		if value = strings.TrimSpace(value); value != "" {
			return value
		}
	}
	return ""
}

// LoadInstalledCommandEnv supplies local lifecycle commands from agent.env.
func LoadInstalledCommandEnv() {
	envPath := EnvFilePath()
	for _, key := range []string{
		"HFL_WSS_URL",
		"HFL_API_BASE",
		"HFL_ORG_KEY",
		"HFL_NODE_ROLE",
		"HFL_NODE_CREDENTIAL",
		"HFL_NODE_TOKEN",
		"HFL_INSTALLATION_ID",
		"HFL_INSECURE_TLS",
		"HFL_GATEWAY_SCOPE",
	} {
		if strings.TrimSpace(os.Getenv(key)) != "" {
			continue
		}
		if value := readEnvKey(envPath, key); value != "" {
			_ = os.Setenv(key, value)
		}
	}
}

// AgentConfig converts to model.AgentConfig for release/register APIs.
func (c Config) AgentConfig() *model.AgentConfig {
	envPath := EnvFilePath()
	return &model.AgentConfig{
		WSSURL:         c.WSSURL,
		APIBaseURL:     c.APIBase,
		OrgKey:         c.OrgKey,
		NodeToken:      c.NodeToken,
		InstallationID: c.InstallationID,
		NodeID:         ReadNodeID(envPath),
		Role:           c.NodeRole,
		DataDir:        dataDirForAgent(),
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

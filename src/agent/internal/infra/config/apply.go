package config

import (
	"strings"

	"hyperfilelens/agent/internal/model"
)

func cloneConfig(src *model.AgentConfig) *model.AgentConfig {
	if src == nil {
		return &model.AgentConfig{}
	}
	cp := *src
	return &cp
}

func applyEnvMap(cfg *model.AgentConfig, values map[string]string) {
	if cfg == nil || len(values) == 0 {
		return
	}
	for env, val := range values {
		val = strings.TrimSpace(val)
		if val == "" {
			continue
		}
		f, ok := fieldByEnv(env)
		if !ok {
			continue
		}
		switch f.Key {
		case "wss_url":
			cfg.WSSURL = val
		case "api_base_url":
			cfg.APIBaseURL = val
		case "org_key":
			cfg.OrgKey = val
		case "node_id":
			cfg.NodeID = val
		case "node_token":
			cfg.NodeToken = val
		case "data_dir":
			cfg.DataDir = val
		case "log_dir":
			cfg.LogDir = val
		case "kopia_path":
			cfg.KopiaPath = val
		case "role":
			if r, err := model.ParseRole(val); err == nil {
				cfg.Role = r
			}
		}
	}
}

func applyOverrides(cfg *model.AgentConfig, o Overrides) {
	if cfg == nil {
		return
	}
	if s := strings.TrimSpace(o.WSSURL); s != "" {
		cfg.WSSURL = s
	}
	if s := strings.TrimSpace(o.APIBaseURL); s != "" {
		cfg.APIBaseURL = s
	}
	if s := strings.TrimSpace(o.OrgKey); s != "" {
		cfg.OrgKey = s
	}
	if s := strings.TrimSpace(o.NodeID); s != "" {
		cfg.NodeID = s
	}
	if s := strings.TrimSpace(o.NodeToken); s != "" {
		cfg.NodeToken = s
	}
	if s := strings.TrimSpace(o.DataDir); s != "" {
		cfg.DataDir = s
	}
	if s := strings.TrimSpace(o.LogDir); s != "" {
		cfg.LogDir = s
	}
	if s := strings.TrimSpace(o.KopiaPath); s != "" {
		cfg.KopiaPath = s
	}
	if o.Role != "" {
		if r, err := model.ParseRole(string(o.Role)); err == nil {
			cfg.Role = r
		}
	}
}

func configToEnvMap(cfg *model.AgentConfig) map[string]string {
	if cfg == nil {
		return nil
	}
	out := map[string]string{}
	set := func(key, val string) {
		env := envByKey(key)
		if env == "" || strings.TrimSpace(val) == "" {
			return
		}
		out[env] = strings.TrimSpace(val)
	}
	set("wss_url", cfg.WSSURL)
	set("api_base_url", cfg.APIBaseURL)
	set("org_key", cfg.OrgKey)
	set("node_id", cfg.NodeID)
	set("node_token", cfg.NodeToken)
	set("data_dir", cfg.DataDir)
	set("log_dir", cfg.LogDir)
	set("kopia_path", cfg.KopiaPath)
	if cfg.Role != "" {
		set("role", string(cfg.Role))
	}
	return out
}

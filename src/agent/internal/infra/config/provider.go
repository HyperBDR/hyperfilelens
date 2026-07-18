package config

import "hyperfilelens/agent/internal/model"

// Provider supplies the latest effective agent configuration (hot-reloadable).
type Provider interface {
	Current() *model.AgentConfig
}

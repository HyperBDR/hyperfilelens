package model

import "time"

// Repo is a locally registered Kopia repository alias (config file path).
type Repo struct {
	Name        string     `json:"name"`
	ConfigFile  string     `json:"config_file"`
	Description string     `json:"description,omitempty"`
	CreatedAt   *time.Time `json:"created_at,omitempty"`
	UpdatedAt   *time.Time `json:"updated_at,omitempty"`
}

package engine

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/vfs"
)

// ensureKopiaProcessEnv fills cache/home variables required when Agent runs as a
// service (systemd, Windows Service, LaunchDaemon) without a user shell profile.
// KOPIA_CACHE_DIRECTORY is set for all platforms; OS-specific vars cover Kopia
// fallbacks and tools that read os.UserCacheDir().
func ensureKopiaProcessEnv(cfg *model.AgentConfig, env map[string]string) (map[string]string, error) {
	if env == nil {
		env = map[string]string{}
	}
	dataDir := strings.TrimSpace(cfg.DataDir)
	if dataDir == "" {
		dataDir = vfs.DefaultAgentDataDir()
	}
	cacheDir := vfs.AgentCacheDir(dataDir)
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		return nil, fmt.Errorf("create kopia cache dir: %w", err)
	}

	if strings.TrimSpace(env["KOPIA_CACHE_DIRECTORY"]) == "" {
		env["KOPIA_CACHE_DIRECTORY"] = cacheDir
	}
	effectiveCacheDir := strings.TrimSpace(env["KOPIA_CACHE_DIRECTORY"])
	if effectiveCacheDir == "" {
		effectiveCacheDir = cacheDir
	}
	if err := os.MkdirAll(effectiveCacheDir, 0o755); err != nil {
		return nil, fmt.Errorf("create kopia cache dir: %w", err)
	}
	if err := os.MkdirAll(filepath.Join(effectiveCacheDir, "server-contents"), 0o755); err != nil {
		return nil, fmt.Errorf("create kopia server content cache dir: %w", err)
	}
	if err := os.MkdirAll(filepath.Join(effectiveCacheDir, "kopia", "cli-logs"), 0o755); err != nil {
		return nil, fmt.Errorf("create kopia cli log cache dir: %w", err)
	}
	if filepath.Clean(effectiveCacheDir) != filepath.Clean(cacheDir) {
		if err := os.MkdirAll(filepath.Join(cacheDir, "kopia", "cli-logs"), 0o755); err != nil {
			return nil, fmt.Errorf("create kopia default cli log cache dir: %w", err)
		}
	}
	if strings.TrimSpace(env["KOPIA_USE_KEYRING"]) == "" {
		env["KOPIA_USE_KEYRING"] = "false"
	}
	if strings.TrimSpace(env["KOPIA_PERSIST_CREDENTIALS_ON_CONNECT"]) == "" {
		env["KOPIA_PERSIST_CREDENTIALS_ON_CONNECT"] = "false"
	}

	switch runtime.GOOS {
	case "windows":
		if strings.TrimSpace(env["LOCALAPPDATA"]) == "" {
			env["LOCALAPPDATA"] = cacheDir
		}
		if strings.TrimSpace(env["USERPROFILE"]) == "" {
			env["USERPROFILE"] = dataDir
		}
		if strings.TrimSpace(env["HOME"]) == "" {
			env["HOME"] = dataDir
		}
	default:
		if strings.TrimSpace(env["HOME"]) == "" {
			env["HOME"] = dataDir
		}
		if strings.TrimSpace(env["XDG_CACHE_HOME"]) == "" {
			env["XDG_CACHE_HOME"] = cacheDir
		}
	}
	return env, nil
}

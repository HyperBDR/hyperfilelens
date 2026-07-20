package engine

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/model"
	"hyperfilelens/agent/internal/platform/vfs"
)

func agentDataDir(cfg *model.AgentConfig) string {
	dataDir := strings.TrimSpace(cfg.DataDir)
	if dataDir == "" {
		dataDir = vfs.DefaultAgentDataDir()
	}
	if absolute, err := filepath.Abs(dataDir); err == nil {
		return filepath.Clean(absolute)
	}
	return filepath.Clean(dataDir)
}

func managedRepositoryCacheRoot(cfg *model.AgentConfig) string {
	return filepath.Join(vfs.AgentCacheDir(agentDataDir(cfg)), "repositories")
}

// managedRepositoryCacheDir isolates Kopia's format and content caches by the
// config file that owns them. Kopia embeds this path in its config on create or
// connect, so reconnecting an older config also migrates it away from the
// legacy shared cache directory.
func managedRepositoryCacheDir(cfg *model.AgentConfig, configFile string) string {
	canonicalConfig := filepath.Clean(strings.TrimSpace(configFile))
	if absolute, err := filepath.Abs(canonicalConfig); err == nil {
		canonicalConfig = filepath.Clean(absolute)
	}
	base := strings.TrimSuffix(filepath.Base(canonicalConfig), filepath.Ext(canonicalConfig))
	base = sanitizeSessionToken(base)
	sum := sha256.Sum256([]byte(canonicalConfig))
	token := hex.EncodeToString(sum[:])[:12]
	return filepath.Join(managedRepositoryCacheRoot(cfg), base+"-"+token)
}

// ensureKopiaProcessEnv fills cache/home variables required when Agent runs as a
// service (systemd, Windows Service, LaunchDaemon) without a user shell profile.
// KOPIA_CACHE_DIRECTORY is set for all platforms; OS-specific vars cover Kopia
// fallbacks and tools that read os.UserCacheDir().
func ensureKopiaProcessEnv(cfg *model.AgentConfig, env map[string]string) (map[string]string, error) {
	if env == nil {
		env = map[string]string{}
	}
	dataDir := agentDataDir(cfg)
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

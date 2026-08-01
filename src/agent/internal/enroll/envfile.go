package enroll

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
	"hyperfilelens/agent/internal/platform/vfs"
)

var managedSentryEnvKeys = []string{
	"SENTRY_ENABLED",
	"SENTRY_BACKEND_DSN",
	"SENTRY_ENVIRONMENT",
	"SENTRY_RELEASE",
	"SENTRY_TRACES_SAMPLE_RATE",
	"HFL_SENTRY_LENSNODE_RELEASE",
}

// WriteNodeID updates or appends HFL_NODE_ID in agent.env.
func WriteNodeID(envPath, nodeID string) error {
	nodeID = strings.TrimSpace(nodeID)
	if nodeID == "" {
		return fmt.Errorf("empty node_id")
	}
	lines := []string{}
	if data, err := os.ReadFile(envPath); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			if strings.HasPrefix(strings.TrimSpace(line), "HFL_NODE_ID=") {
				continue
			}
			if strings.TrimSpace(line) != "" {
				lines = append(lines, line)
			}
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	lines = append(lines, "HFL_NODE_ID="+nodeID)
	content := strings.Join(lines, "\n") + "\n"
	if err := os.MkdirAll(dirOf(envPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(envPath, []byte(content), 0o600)
}

func dirOf(path string) string {
	return filepath.Dir(path)
}

// WriteEnrollmentEnv writes enrollment credentials to agent.env.
func WriteEnrollmentEnv(cfg Config) error {
	envPath := EnvFilePath()
	dataDir := vfs.UnixDataDir()
	if runtime.GOOS == "windows" {
		pd := os.Getenv("ProgramData")
		if pd == "" {
			pd = `C:\ProgramData`
		}
		dataDir = filepath.Join(pd, "HyperFileLens", "Agent")
	}
	kopiaPath := filepath.Join(install.DefaultInstallDir(), "kopia")
	insecure := "1"
	if !cfg.InsecureTLS {
		insecure = "0"
	}
	lines := []string{
		"HFL_WSS_URL=" + cfg.WSSURL,
		"HFL_API_BASE=" + cfg.APIBase,
		"HFL_ORG_KEY=" + cfg.OrgKey,
		"HFL_NODE_TOKEN=" + cfg.NodeToken,
		"HFL_DATA_DIR=" + dataDir,
		"HFL_NODE_ROLE=" + string(cfg.NodeRole),
		"HFL_KOPIA_PATH=" + kopiaPath,
		"HFL_INSECURE_TLS=" + insecure,
	}
	for _, name := range managedSentryEnvKeys {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" && !strings.ContainsAny(value, "\r\n") {
			lines = append(lines, name+"="+value)
		}
	}
	if existing := ReadNodeID(envPath); existing != "" {
		lines = append(lines, "HFL_NODE_ID="+existing)
	}
	content := strings.Join(lines, "\n") + "\n"
	if err := os.MkdirAll(filepath.Dir(envPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(envPath, []byte(content), 0o600)
}

// SyncManagedSentryEnv converges only HFL-managed observability settings.
// Existing node credentials and user-managed Agent settings remain unchanged.
func SyncManagedSentryEnv() (bool, error) {
	return syncManagedSentryEnv(EnvFilePath())
}

func syncManagedSentryEnv(envPath string) (bool, error) {
	rawEnabled := strings.TrimSpace(os.Getenv("SENTRY_ENABLED"))
	if rawEnabled == "" {
		return false, nil
	}
	enabled := "false"
	if sentryEnabledValue(rawEnabled) {
		enabled = "true"
	}
	desired := map[string]string{"SENTRY_ENABLED": enabled}
	if sentryEnabledValue(enabled) {
		for _, name := range managedSentryEnvKeys[1:] {
			value := strings.TrimSpace(os.Getenv(name))
			if value != "" && !strings.ContainsAny(value, "\r\n") {
				desired[name] = value
			}
		}
	}

	current, err := os.ReadFile(envPath)
	if err != nil {
		return false, err
	}
	managed := make(map[string]struct{}, len(managedSentryEnvKeys))
	for _, name := range managedSentryEnvKeys {
		managed[name] = struct{}{}
	}
	written := make(map[string]bool, len(desired))
	lines := make([]string, 0, len(strings.Split(string(current), "\n"))+len(desired))
	for _, raw := range strings.Split(strings.TrimSuffix(string(current), "\n"), "\n") {
		key, _, found := strings.Cut(raw, "=")
		if _, controlled := managed[key]; !found || !controlled {
			lines = append(lines, raw)
			continue
		}
		if value, present := desired[key]; present && !written[key] {
			lines = append(lines, key+"="+value)
			written[key] = true
		}
	}
	for _, name := range managedSentryEnvKeys {
		if value, present := desired[name]; present && !written[name] {
			lines = append(lines, name+"="+value)
		}
	}
	updated := []byte(strings.Join(lines, "\n") + "\n")
	if bytes.Equal(current, updated) {
		return false, nil
	}
	if err := writePrivateEnvAtomically(envPath, updated); err != nil {
		return false, err
	}
	return true, nil
}

func sentryEnabledValue(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

func writePrivateEnvAtomically(path string, content []byte) error {
	temporary, err := os.CreateTemp(filepath.Dir(path), ".agent.env.*")
	if err != nil {
		return err
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(content); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporaryPath, path)
}

// ReadNodeID returns HFL_NODE_ID from agent.env if present.
func ReadNodeID(envPath string) string {
	f, err := os.Open(envPath)
	if err != nil {
		return ""
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if strings.HasPrefix(line, "HFL_NODE_ID=") {
			return strings.TrimSpace(strings.TrimPrefix(line, "HFL_NODE_ID="))
		}
	}
	return ""
}

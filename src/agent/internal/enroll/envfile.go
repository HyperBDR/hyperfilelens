package enroll

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
	"hyperfilelens/agent/internal/platform/vfs"
)

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
	if existing := ReadNodeID(envPath); existing != "" {
		lines = append(lines, "HFL_NODE_ID="+existing)
	}
	content := strings.Join(lines, "\n") + "\n"
	if err := os.MkdirAll(filepath.Dir(envPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(envPath, []byte(content), 0o600)
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

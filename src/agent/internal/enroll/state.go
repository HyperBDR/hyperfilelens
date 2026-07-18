package enroll

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
	"hyperfilelens/agent/internal/platform/vfs"
)

// InstallState describes an existing agent installation on this host.
type InstallState struct {
	Installed bool
	Version   string
	NodeID    string
	OrgKey    string
	Service   string
}

// DetectInstallState inspects the default install paths for an existing agent.
func DetectInstallState() InstallState {
	installDir := install.DefaultInstallDir()
	bin := filepath.Join(installDir, agentBinaryName())
	info, err := os.Stat(bin)
	if err != nil || info.IsDir() {
		return InstallState{}
	}

	state := InstallState{Installed: true}
	if data, err := os.ReadFile(filepath.Join(installDir, "INSTALLED_VERSION")); err == nil {
		state.Version = strings.TrimSpace(string(data))
	}

	envPath := EnvFilePath()
	state.NodeID = ReadNodeID(envPath)
	state.OrgKey = readEnvKey(envPath, "HFL_ORG_KEY")
	state.Service = serviceState(context.Background())
	return state
}

// ServiceHealthy reports whether the platform service appears to be running.
func (s InstallState) ServiceHealthy() bool {
	return isServiceHealthy(s.Service)
}

func isServiceHealthy(service string) bool {
	switch strings.ToLower(strings.TrimSpace(service)) {
	case "active", "running", "loaded":
		return true
	default:
		return false
	}
}

func readEnvKey(envPath, key string) string {
	data, err := os.ReadFile(envPath)
	if err != nil {
		return ""
	}
	prefix := key + "="
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, prefix) {
			return strings.TrimSpace(strings.TrimPrefix(line, prefix))
		}
	}
	return ""
}

func serviceState(ctx context.Context) string {
	switch runtime.GOOS {
	case "linux":
		if _, err := exec.LookPath("systemctl"); err != nil {
			return "unavailable"
		}
		active, _ := exec.CommandContext(ctx, "systemctl", "is-active", "hyperfilelens-agent.service").Output()
		return strings.TrimSpace(string(active))
	case "darwin":
		out, err := exec.CommandContext(ctx, "launchctl", "print", "system/com.hyperfilelens.agent").CombinedOutput()
		if err != nil {
			return "not loaded"
		}
		for _, line := range strings.Split(string(out), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "state =") {
				return strings.Trim(strings.TrimPrefix(line, "state ="), " ;")
			}
		}
		return "loaded"
	case "windows":
		out, err := exec.CommandContext(ctx, "sc.exe", "query", "HyperFileLensAgent").CombinedOutput()
		if err != nil {
			return "not installed"
		}
		for _, line := range strings.Split(string(out), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(strings.ToUpper(line), "STATE") {
				fields := strings.Fields(line)
				if len(fields) >= 4 {
					return fields[3]
				}
			}
		}
		return "unknown"
	default:
		return "unknown"
	}
}

func dataDirForAgent() string {
	if runtime.GOOS == "windows" {
		pd := os.Getenv("ProgramData")
		if pd == "" {
			pd = `C:\ProgramData`
		}
		return filepath.Join(pd, "HyperFileLens", "Agent")
	}
	return vfs.UnixDataDir()
}

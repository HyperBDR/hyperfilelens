package enroll

import (
	"path/filepath"
	"runtime"

	"hyperfilelens/agent/internal/platform/install"
)

func defaultInstallPath() string {
	return install.DefaultInstallDir()
}

func defaultAgentBinaryPath() string {
	name := "hfl-agent"
	if runtime.GOOS == "windows" {
		name = "hfl-agent.exe"
	}
	return filepath.Join(defaultInstallPath(), name)
}

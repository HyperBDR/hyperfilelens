package vfs

import (
	"os"
	"path/filepath"
	"runtime"
)

// UnixProductSlug is the FHS directory basename for Agent on Linux/macOS
// (/opt/hyperfilelens-agent, /var/lib/hyperfilelens-agent, hyperfilelens-agent.service).
const UnixProductSlug = "hyperfilelens-agent"

// WindowsVendorDir is the vendor folder under Program Files / ProgramData.
const WindowsVendorDir = "HyperFileLens"

// WindowsProductDir is the product folder under WindowsVendorDir (PascalCase per Windows convention).
const WindowsProductDir = "Agent"

// UnixInstallDir returns the FHS /opt install root (hfl-agent + bundled kopia).
func UnixInstallDir() string {
	return filepath.Join("/opt", UnixProductSlug)
}

// UnixDataDir returns the FHS /var/lib state root (agent.env, agent.db, logs, cache).
func UnixDataDir() string {
	return filepath.Join("/var/lib", UnixProductSlug)
}

// DefaultInstallDir returns the platform default binary install directory.
func DefaultInstallDir() string {
	switch runtime.GOOS {
	case "windows":
		pf := os.Getenv("ProgramFiles")
		if pf == "" {
			pf = `C:\Program Files`
		}
		return filepath.Join(pf, WindowsVendorDir, WindowsProductDir)
	default:
		return UnixInstallDir()
	}
}

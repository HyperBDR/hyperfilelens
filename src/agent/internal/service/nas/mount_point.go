package nas

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"hyperfilelens/agent/internal/platform/vfs"
)

// ResolvedMountPoint returns the host-local mount path for control-plane mount_point values.
func ResolvedMountPoint(mountPoint string) string {
	resolved, err := resolveMountPoint(mountPoint)
	if err != nil {
		return ""
	}
	return resolved
}

func resolveMountPoint(mountPoint string) (string, error) {
	clean := strings.TrimSpace(mountPoint)
	if clean == "" {
		return "", fmt.Errorf("mount_point is required")
	}

	dataDir := agentDataDirForMounts()
	defaultUnix := vfs.UnixDataDir()
	resolved := filepath.Clean(filepath.FromSlash(clean))

	if resolved == defaultUnix || strings.HasPrefix(resolved, defaultUnix+string(os.PathSeparator)) {
		rel, err := filepath.Rel(defaultUnix, resolved)
		if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			resolved = filepath.Join(dataDir, rel)
		}
	}

	mountsRoot := filepath.Clean(vfs.AgentMountsDir(dataDir))
	rel, err := filepath.Rel(mountsRoot, resolved)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return "", fmt.Errorf("mount_point must be under %s", mountsRoot)
	}
	return resolved, nil
}

func agentDataDirForMounts() string {
	if v := strings.TrimSpace(os.Getenv("HFL_DATA_DIR")); v != "" {
		return filepath.Clean(v)
	}
	return vfs.DefaultAgentDataDir()
}

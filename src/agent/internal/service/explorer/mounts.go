package explorer

import (
	"path/filepath"
	"runtime"
	"strings"
)

// NormalizeMountPath canonicalizes mount/browse roots; on Windows, C: and C:. become C:\.
func NormalizeMountPath(mountpoint string) string {
	return normalizeMountPath(mountpoint)
}

func normalizeMountPath(mountpoint string) string {
	clean := strings.TrimSpace(mountpoint)
	if runtime.GOOS != "windows" {
		return filepath.Clean(clean)
	}
	volume := filepath.VolumeName(clean)
	if volume == "" {
		return filepath.Clean(clean)
	}
	rest := strings.TrimLeft(clean[len(volume):], `\/.`)
	if rest == "" || rest == "." {
		return strings.ToUpper(string(volume[0])) + `:\`
	}
	return filepath.Clean(clean)
}

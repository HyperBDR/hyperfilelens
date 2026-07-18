package main

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// removeBootstrapTempBinary deletes this executable when staged under the system temp dir by enrollment bootstrap.
func removeBootstrapTempBinary() {
	exe, err := os.Executable()
	if err != nil {
		return
	}
	resolved, err := filepath.EvalSymlinks(exe)
	if err == nil {
		exe = resolved
	}
	if !isBootstrapTempExecutable(exe) {
		return
	}
	_ = os.Remove(exe)
}

func isBootstrapTempExecutable(path string) bool {
	base := filepath.Base(path)
	dir := filepath.Clean(filepath.Dir(path))
	if dir != filepath.Clean(os.TempDir()) {
		return false
	}
	if runtime.GOOS == "windows" {
		lower := strings.ToLower(base)
		return strings.HasPrefix(lower, "hfl-enroll-") && strings.HasSuffix(lower, ".exe")
	}
	return strings.HasPrefix(base, "hfl-enroll-")
}

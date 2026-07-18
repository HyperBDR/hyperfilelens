package pathsize

import (
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
)

// Estimate returns logical byte size for a file or directory path.
func Estimate(path string, pathType string) (uint64, error) {
	clean := strings.TrimSpace(path)
	if clean == "" {
		return 0, os.ErrInvalid
	}
	kind := strings.ToLower(strings.TrimSpace(pathType))
	info, err := os.Stat(clean)
	if err != nil {
		return 0, err
	}
	if kind == "file" || (!info.IsDir() && kind != "directory") {
		if info.Size() < 0 {
			return 0, nil
		}
		return uint64(info.Size()), nil
	}
	if runtime.GOOS != "windows" {
		if size, ok := duBytes(clean); ok {
			return size, nil
		}
	}
	return walkBytes(clean)
}

func duBytes(path string) (uint64, bool) {
	cmd := exec.Command("du", "-sb", path)
	output, err := cmd.Output()
	if err != nil {
		return 0, false
	}
	fields := strings.Fields(strings.TrimSpace(string(output)))
	if len(fields) == 0 {
		return 0, false
	}
	parsed, err := strconv.ParseUint(fields[0], 10, 64)
	if err != nil {
		return 0, false
	}
	return parsed, true
}

func walkBytes(root string) (uint64, error) {
	var total uint64
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			return nil
		}
		info, infoErr := entry.Info()
		if infoErr != nil {
			return infoErr
		}
		if info.Size() > 0 {
			total += uint64(info.Size())
		}
		return nil
	})
	return total, err
}

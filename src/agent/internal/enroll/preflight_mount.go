package enroll

import (
	"path/filepath"
	"runtime"
	"strings"

	"github.com/shirou/gopsutil/v4/disk"
)

func pathOnNoExecMount(path string) (bool, string) {
	if runtime.GOOS == "windows" {
		return false, ""
	}
	path = filepath.Clean(path)
	partitions, err := disk.Partitions(true)
	if err != nil {
		return false, ""
	}
	bestMount := ""
	var bestOptions []string
	for _, partition := range partitions {
		mount := filepath.Clean(partition.Mountpoint)
		withinMount := mount == string(filepath.Separator) ||
			path == mount ||
			strings.HasPrefix(path, mount+string(filepath.Separator))
		if !withinMount {
			continue
		}
		if len(mount) > len(bestMount) {
			bestMount = mount
			bestOptions = partition.Opts
		}
	}
	for _, option := range bestOptions {
		if strings.TrimSpace(option) == "noexec" {
			return true, bestMount
		}
	}
	return false, bestMount
}

package disk

import (
	"runtime"
	"strings"

	"github.com/shirou/gopsutil/v4/disk"
)

// HostStorageUsage returns summed total/used/free bytes across local mount points.
func HostStorageUsage() (total, used, free uint64, count int, err error) {
	parts, err := disk.Partitions(false)
	if err != nil {
		return 0, 0, 0, 0, err
	}
	seen := make(map[string]struct{})
	for _, part := range parts {
		mp := normalizeMountpoint(part.Mountpoint)
		if mp == "" {
			continue
		}
		if _, ok := seen[mp]; ok {
			continue
		}
		seen[mp] = struct{}{}
		usage, uerr := disk.Usage(mp)
		if uerr != nil {
			continue
		}
		total += usage.Total
		used += usage.Used
		free += usage.Free
		count++
	}
	if count == 0 {
		return 0, 0, 0, 0, err
	}
	return total, used, free, count, nil
}

func normalizeMountpoint(mountpoint string) string {
	clean := strings.TrimSpace(mountpoint)
	if runtime.GOOS == "windows" {
		if len(clean) == 2 && clean[1] == ':' {
			return strings.ToUpper(string(clean[0])) + `:\`
		}
		if len(clean) >= 3 && clean[1] == ':' && (clean[2] == '\\' || clean[2] == '/') {
			return strings.ToUpper(string(clean[0])) + `:\`
		}
	}
	return clean
}

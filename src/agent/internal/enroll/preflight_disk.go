package enroll

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/shirou/gopsutil/v4/disk"
)

const minEnrollmentFreeBytes = 200 * 1024 * 1024

type diskCheckResult struct {
	OK      bool
	Warning bool
	Title   string
	Detail  string
}

func checkEnrollmentDiskSpace() diskCheckResult {
	paths := enrollmentDiskPaths()
	var lowParts []string
	var okParts []string
	checked := 0

	for _, path := range paths {
		checkPath := diskCheckPath(path)
		free, err := freeBytes(checkPath)
		if err != nil {
			continue
		}
		checked++
		label := diskPathLabel(path)
		part := fmt.Sprintf("%s %s free", label, humanBytes(free))
		if free < minEnrollmentFreeBytes {
			lowParts = append(lowParts, part)
		} else {
			okParts = append(okParts, part)
		}
	}

	if len(lowParts) > 0 {
		return diskCheckResult{
			Title:  "Disk space insufficient",
			Detail: strings.Join(lowParts, ", ") + fmt.Sprintf("; need %s each", humanBytes(minEnrollmentFreeBytes)),
		}
	}
	if checked == 0 {
		return diskCheckResult{
			Warning: true,
			Title:   "Disk space could not be verified",
			Detail:  strings.Join(paths, ", "),
		}
	}
	return diskCheckResult{
		OK:     true,
		Title:  "Disk space sufficient",
		Detail: strings.Join(okParts, ", "),
	}
}

func diskPathLabel(path string) string {
	path = filepath.Clean(path)
	switch path {
	case defaultInstallPath():
		if runtime.GOOS == "windows" {
			return path
		}
		return "/opt"
	case dataDirForAgent():
		if runtime.GOOS == "windows" {
			return path
		}
		return "/var/lib"
	default:
		if runtime.GOOS == "windows" {
			return path
		}
		return "/tmp"
	}
}

// diskCheckPath returns path or nearest existing parent for volume free-space lookup.
func diskCheckPath(path string) string {
	path = filepath.Clean(path)
	for {
		if path == "" || path == string(os.PathSeparator) {
			return string(os.PathSeparator)
		}
		if info, err := os.Stat(path); err == nil {
			if info.IsDir() {
				return path
			}
		}
		parent := filepath.Dir(path)
		if parent == path {
			return path
		}
		path = parent
	}
}

func enrollmentDiskPaths() []string {
	installDir := defaultInstallPath()
	dataDir := dataDirForAgent()
	tmp := os.TempDir()
	if tmp == "" {
		tmp = string(os.PathSeparator) + "tmp"
	}
	return []string{installDir, dataDir, tmp}
}

func freeBytes(path string) (uint64, error) {
	usage, err := disk.Usage(path)
	if err != nil {
		return 0, err
	}
	return usage.Free, nil
}

func humanBytes(n uint64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div := uint64(unit)
	exp := 0
	for n/div >= unit && exp < 4 {
		div *= unit
		exp++
	}
	val := float64(n) / float64(div)
	suffix := []string{"KB", "MB", "GB", "TB", "PB"}
	return fmt.Sprintf("%.1f %s", val, suffix[exp])
}

func logDiskResult(r diskCheckResult) {
	switch {
	case r.OK:
		logOKDetail(r.Title, r.Detail)
	case r.Warning:
		logWarnDetail(r.Title, r.Detail)
	default:
		logFailDetail(r.Title, r.Detail, 2)
	}
}

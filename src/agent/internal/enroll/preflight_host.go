package enroll

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

type hostnameCheckResult struct {
	OK      bool
	Warning bool
	Name    string
	Title   string
	Detail  string
}

func checkHostname() hostnameCheckResult {
	name, err := os.Hostname()
	if err != nil || strings.TrimSpace(name) == "" {
		return hostnameCheckResult{
			Warning: true,
			Title:   "Hostname is not configured",
			Detail:  "set a unique host name for console identification",
		}
	}
	name = strings.TrimSpace(name)
	lower := strings.ToLower(name)
	if lower == "localhost" || lower == "localhost.localdomain" {
		return hostnameCheckResult{
			Warning: true,
			Name:    name,
			Title:   "Hostname is generic",
			Detail:  name + "; set a unique host name for console identification",
		}
	}
	return hostnameCheckResult{
		OK:     true,
		Name:   name,
		Title:  "Hostname configured",
		Detail: name,
	}
}

type writableCheckResult struct {
	OK     bool
	Title  string
	Detail string
	Err    error
}

func checkInstallPathsWritable() writableCheckResult {
	targets := []string{defaultInstallPath(), dataDirForAgent()}
	labels := []string{defaultInstallPath(), dataDirForAgent()}
	for i, target := range targets {
		if err := checkWritableTarget(target); err != nil {
			return writableCheckResult{
				Title:  "Install paths not writable",
				Detail: fmt.Sprintf("%s — %s", labels[i], shortenErr(err)),
				Err:    err,
			}
		}
	}
	return writableCheckResult{
		OK:     true,
		Title:  "Install paths writable",
		Detail: strings.Join(labels, ", "),
	}
}

func checkWritableTarget(path string) error {
	target := writableCheckDir(path)
	testFile := filepath.Join(target, ".hfl-enroll-write-test")
	f, err := os.OpenFile(testFile, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	if err := f.Close(); err != nil {
		return err
	}
	return os.Remove(testFile)
}

func writableCheckDir(path string) string {
	path = filepath.Clean(path)
	for {
		if path == "" || path == string(os.PathSeparator) {
			return string(os.PathSeparator)
		}
		if info, err := os.Stat(path); err == nil && info.IsDir() {
			return path
		}
		parent := filepath.Dir(path)
		if parent == path {
			return path
		}
		path = parent
	}
}

func checkNASMountHelpers(role string) (ok bool, warning bool, title, detail string) {
	if runtime.GOOS != "linux" {
		return true, false, "", ""
	}
	switch role {
	case "proxy", "gateway":
	default:
		return true, false, "", ""
	}
	if !nasMountHelpersReady() {
		return false, true, "NAS mount helpers missing", "need mount.nfs and mount.cifs for role " + role + "; on Ubuntu 20.04+ use apt install nfs-common cifs-utils (offline bundle targets 24.04)"
	}
	if !kernelModuleAvailable("nls_utf8") {
		return false, true, "NAS SMB UTF-8 kernel module missing", `install linux-modules-extra-$(uname -r), then run modprobe nls_utf8; SMB mounts can fall back without iocharset`
	}
	return true, false, "NAS mount helpers available", "mount.nfs, mount.cifs, nls_utf8"
}

func nasMountHelpersReady() bool {
	return mountHelperExists("mount.nfs") && mountHelperUsable("mount.cifs", "--version")
}

func mountHelperExists(name string) bool {
	return mountHelperPath(name) != ""
}

func mountHelperUsable(name string, args ...string) bool {
	path := mountHelperPath(name)
	if path == "" {
		return false
	}
	return exec.Command(path, args...).Run() == nil
}

func mountHelperPath(name string) string {
	if _, err := exec.LookPath(name); err == nil {
		return name
	}
	for _, dir := range []string{"/sbin", "/usr/sbin"} {
		path := filepath.Join(dir, name)
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path
		}
	}
	return ""
}

func kernelModuleAvailable(name string) bool {
	name = strings.TrimSpace(name)
	if name == "" {
		return false
	}
	if info, err := os.Stat(filepath.Join("/sys/module", name)); err == nil && info.IsDir() {
		return true
	}
	if data, err := os.ReadFile("/proc/modules"); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			fields := strings.Fields(line)
			if len(fields) > 0 && fields[0] == name {
				return true
			}
		}
	}
	return mountHelperUsable("modprobe", "-n", name)
}

func logHostnameResult(r hostnameCheckResult) {
	switch {
	case r.OK:
		logOKDetail(r.Title, r.Detail)
	case r.Warning:
		logWarnDetail(r.Title, r.Detail)
	}
}

func logWritableResult(r writableCheckResult) {
	if r.Err != nil {
		logFailDetail(r.Title, r.Detail, 2)
		return
	}
	logOKDetail(r.Title, r.Detail)
}

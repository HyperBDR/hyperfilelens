// Package hostinfo collects normalized operating-system facts for enrollment
// preflight checks, node registration, and recurring inventory heartbeats.
package hostinfo

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	goshost "github.com/shirou/gopsutil/v4/host"
)

// Info describes the operating system that is actually running the Agent.
type Info struct {
	OSFamily       string `json:"os_family"`
	OSName         string `json:"os_name"`
	OSVersion      string `json:"os_version"`
	OSBuild        string `json:"os_build,omitempty"`
	OSEdition      string `json:"os_edition,omitempty"`
	KernelVersion  string `json:"kernel_version,omitempty"`
	Arch           string `json:"arch"`
	ServiceManager string `json:"service_manager"`
}

// Collect returns best-effort platform facts without making support-policy
// decisions. Missing optional values do not prevent enrollment.
func Collect(ctx context.Context) Info {
	info := Info{
		OSFamily:       runtime.GOOS,
		OSName:         runtime.GOOS,
		Arch:           runtime.GOARCH,
		ServiceManager: DetectServiceManager(ctx),
	}

	if system, err := goshost.InfoWithContext(ctx); err == nil {
		info.OSName = firstNonEmpty(system.Platform, system.OS, info.OSName)
		info.OSVersion = strings.TrimSpace(system.PlatformVersion)
		info.KernelVersion = strings.TrimSpace(system.KernelVersion)
	}

	switch runtime.GOOS {
	case "linux":
		applyLinuxOSRelease(&info, "/etc/os-release")
	case "darwin":
		applyMacOSVersion(ctx, &info)
	case "windows":
		applyWindowsVersion(&info)
	}

	return info
}

// Description returns a concise human-readable platform value for installer
// and enrollment logs.
func (i Info) Description() string {
	name := strings.TrimSpace(i.OSName)
	version := strings.TrimSpace(i.OSVersion)
	if name == "" {
		name = i.OSFamily
	}
	detail := name
	if version != "" && !strings.Contains(strings.ToLower(name), strings.ToLower(version)) {
		detail = strings.TrimSpace(name + " " + version)
	}
	if detail == "" || strings.EqualFold(detail, i.OSFamily) {
		return fmt.Sprintf("%s/%s", i.OSFamily, i.Arch)
	}
	return fmt.Sprintf("%s/%s (%s)", i.OSFamily, i.Arch, detail)
}

// Inventory returns stable keys for registration and heartbeat payloads.
func (i Info) Inventory() map[string]any {
	return map[string]any{
		"os":              i.OSFamily,
		"os_family":       i.OSFamily,
		"os_name":         i.OSName,
		"os_version":      i.OSVersion,
		"os_build":        i.OSBuild,
		"os_edition":      i.OSEdition,
		"kernel_version":  i.KernelVersion,
		"arch":            i.Arch,
		"service_manager": i.ServiceManager,
	}
}

// DetectServiceManager reports the native service manager available to the
// installer. Linux is intentionally systemd-only for the P0 Source Host.
func DetectServiceManager(ctx context.Context) string {
	switch runtime.GOOS {
	case "linux":
		if SystemdAvailable(ctx) {
			return "systemd"
		}
		return "none"
	case "darwin":
		if _, err := exec.LookPath("launchctl"); err == nil {
			return "launchd"
		}
		return "none"
	case "windows":
		return "windows-service"
	default:
		return "unknown"
	}
}

// SystemdAvailable verifies both the systemd runtime directory and a working
// connection to the service manager. A systemctl binary alone is insufficient
// in containers and chroots.
func SystemdAvailable(ctx context.Context) bool {
	if runtime.GOOS != "linux" {
		return false
	}
	if _, err := exec.LookPath("systemctl"); err != nil {
		return false
	}
	if info, err := os.Stat("/run/systemd/system"); err != nil || !info.IsDir() {
		return false
	}
	cmd := exec.CommandContext(ctx, "systemctl", "show-environment")
	return cmd.Run() == nil
}

func applyLinuxOSRelease(info *Info, path string) {
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()

	values := map[string]string{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		key, value, ok := strings.Cut(scanner.Text(), "=")
		if !ok {
			continue
		}
		values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(value), `"'`)
	}
	info.OSName = firstNonEmpty(values["PRETTY_NAME"], values["NAME"], info.OSName)
	info.OSVersion = firstNonEmpty(values["VERSION_ID"], info.OSVersion)
}

func applyMacOSVersion(ctx context.Context, info *Info) {
	for key, target := range map[string]*string{
		"-productName":    &info.OSName,
		"-productVersion": &info.OSVersion,
		"-buildVersion":   &info.OSBuild,
	} {
		out, err := exec.CommandContext(ctx, "sw_vers", key).Output()
		if err == nil && strings.TrimSpace(string(out)) != "" {
			*target = strings.TrimSpace(string(out))
		}
	}
}

func applyWindowsVersion(info *Info) {
	// gopsutil uses Windows version APIs and WMI internally. Keep the raw
	// platform version as the canonical version/build evidence without invoking
	// PowerShell, which is important on Server Core and older Server releases.
	if info.OSName == "windows" {
		info.OSName = "Windows"
	}
	if info.OSBuild == "" {
		info.OSBuild = lastNumericComponent(info.KernelVersion)
	}
}

func lastNumericComponent(value string) string {
	parts := strings.FieldsFunc(value, func(r rune) bool { return r < '0' || r > '9' })
	if len(parts) == 0 {
		return ""
	}
	return parts[len(parts)-1]
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value = strings.TrimSpace(value); value != "" {
			return value
		}
	}
	return ""
}

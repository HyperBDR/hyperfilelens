package enroll

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"

	"hyperfilelens/agent/internal/model"
)

// EnvironmentReport is the result of pre-install environment checks.
type EnvironmentReport struct {
	Platform     string
	PrivilegesOK bool
	ArchOK       bool
	ServiceMgr   string
	Existing     InstallState
	RoleOK       bool
	RoleError    string
}

// RunEnvironmentChecks validates the host and prints user-facing results.
func RunEnvironmentChecks(ctx context.Context, cfg Config) (*EnvironmentReport, error) {
	report := &EnvironmentReport{
		Platform: platformDescription(),
		ArchOK:   runtime.GOARCH == "amd64" || runtime.GOARCH == "arm64",
		Existing: DetectInstallState(),
	}

	if err := requireAdmin(); err != nil {
		report.PrivilegesOK = false
	} else {
		report.PrivilegesOK = true
	}

	report.ServiceMgr = detectServiceManager()
	consoleReach := checkConsoleReachable(ctx, cfg.APIBase)
	wssReach := checkWSSReachable(ctx, resolveWSSURL(cfg))
	hostname := checkHostname()
	clock := checkClockSync(ctx, cfg.APIBase)

	if err := roleConstraints(cfg.NodeRole); err != nil {
		report.RoleOK = false
		report.RoleError = err.Error()
	} else {
		report.RoleOK = true
	}

	printEnrollmentContext(cfg.APIBase, cfg.OrgKey, string(cfg.NodeRole), report.Platform, hostname.Name)

	if report.PrivilegesOK {
		logOKDetail("Running with administrator privileges", adminPrivilegeDetail())
	} else {
		logFailDetail("Administrator privileges are required", "re-run with sudo or as Administrator", 1)
	}

	if report.ArchOK {
		logOKDetail("CPU architecture is supported", runtime.GOARCH)
	} else {
		logFailDetail("CPU architecture is not supported", runtime.GOARCH+" (only amd64/arm64)", 4)
	}

	if report.RoleOK {
		logOKDetail("Role is supported on this platform", fmt.Sprintf("%s on %s", cfg.NodeRole, runtime.GOOS))
	} else {
		logFail(ensureSentence(report.RoleError), 1)
	}

	switch report.ServiceMgr {
	case "systemd", "launchd", "windows-service":
		logOKDetail("Service manager is available", report.ServiceMgr)
	case "none":
		logWarnDetail("No service manager was detected", "the agent can install but auto-start may be unavailable")
	default:
		logOKDetail("Service manager is available", report.ServiceMgr)
	}

	logHostnameResult(hostname)
	logClockResult(clock)
	logReachResult(consoleReach)
	logReachResult(wssReach)

	if err := checkRequiredCommands(); err != nil {
		logFailDetail("Required commands are missing", err.Error(), 2)
	} else {
		logOKDetail("Required commands are available", requiredCommandsDetail())
	}

	logWritableResult(checkInstallPathsWritable())
	logDiskResult(checkEnrollmentDiskSpace())

	nasOK, nasWarn, nasTitle, nasDetail := checkNASMountHelpers(string(cfg.NodeRole))
	switch {
	case nasOK && nasTitle != "":
		logOKDetail(nasTitle, nasDetail)
	case nasWarn:
		logWarnDetail(nasTitle, nasDetail)
	}

	if report.Existing.Installed {
		title := "An existing agent installation was detected"
		detail := strings.TrimPrefix(formatExistingInstallDetail(report.Existing), " (")
		detail = strings.TrimSuffix(detail, ")")
		if report.Existing.ServiceHealthy() {
			logOKDetail(title, detail)
		} else {
			logWarnDetail(title, detail)
		}
	} else {
		logOKDetail("No existing agent installation was found", defaultInstallPath())
	}

	return report, nil
}

func adminPrivilegeDetail() string {
	if runtime.GOOS == "windows" {
		return "elevated Administrator session"
	}
	return "root"
}

func formatExistingInstallDetail(state InstallState) string {
	parts := []string{}
	if state.NodeID != "" {
		parts = append(parts, "node "+state.NodeID)
	}
	if state.Version != "" {
		parts = append(parts, "v"+state.Version)
	}
	if state.Service != "" && state.Service != "unknown" {
		parts = append(parts, "service "+state.Service)
	}
	if len(parts) == 0 {
		return ""
	}
	return " (" + strings.Join(parts, ", ") + ")"
}

// Preflight checks privileges and role/OS constraints (legacy entry point).
func Preflight(role model.Role) error {
	if err := requireAdmin(); err != nil {
		return err
	}
	switch runtime.GOARCH {
	case "amd64", "arm64":
	default:
		return fmt.Errorf("unsupported arch %s (only amd64/arm64)", runtime.GOARCH)
	}
	return roleConstraints(role)
}

func roleConstraints(role model.Role) error {
	if role == model.RoleProxy || role == model.RoleGateway {
		if runtime.GOOS != "linux" {
			return fmt.Errorf("role %s is Linux-only", role)
		}
		if !isUbuntuMin(20, 4) {
			return fmt.Errorf("role %s requires Ubuntu 20.04 LTS or newer", role)
		}
	}
	return nil
}

func detectServiceManager() string {
	switch runtime.GOOS {
	case "linux":
		if _, err := exec.LookPath("systemctl"); err == nil {
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

func requireAdmin() error {
	if runtime.GOOS == "windows" {
		return requireWindowsAdmin()
	}
	if os.Geteuid() != 0 {
		return fmt.Errorf("re-run with sudo or as Administrator to install the agent service and %s", defaultInstallPath())
	}
	return nil
}

func isUbuntuMin(major, minor int) bool {
	f, err := os.Open("/etc/os-release")
	if err != nil {
		return false
	}
	defer f.Close()
	id := ""
	versionID := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "ID=") {
			id = strings.Trim(strings.TrimPrefix(line, "ID="), `"`)
		}
		if strings.HasPrefix(line, "VERSION_ID=") {
			versionID = strings.Trim(strings.TrimPrefix(line, "VERSION_ID="), `"`)
		}
	}
	if id != "ubuntu" {
		return false
	}
	return ubuntuVersionAtLeast(versionID, major, minor)
}

func ubuntuVersionAtLeast(versionID string, major, minor int) bool {
	parts := strings.SplitN(versionID, ".", 2)
	if len(parts) < 2 {
		return false
	}
	maj, err1 := strconv.Atoi(parts[0])
	min, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		return false
	}
	if maj > major {
		return true
	}
	if maj < major {
		return false
	}
	return min >= minor
}

func requireWindowsAdmin() error {
	cmd := exec.Command("powershell", "-NoProfile", "-Command",
		"([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)")
	out, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("Administrator privileges required")
	}
	if !strings.Contains(strings.ToLower(string(out)), "true") {
		return fmt.Errorf("Administrator privileges required")
	}
	return nil
}

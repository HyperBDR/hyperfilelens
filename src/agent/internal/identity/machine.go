package identity

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// MachineID returns a stable, cross-platform hardware identifier for this host.
func MachineID(ctx context.Context) (string, error) {
	var candidates []string
	switch runtime.GOOS {
	case "linux":
		candidates = []string{"/etc/machine-id", "/var/lib/dbus/machine-id"}
		for _, path := range candidates {
			if raw, err := os.ReadFile(path); err == nil {
				if value := strings.TrimSpace(string(raw)); value != "" {
					return value, nil
				}
			}
		}
	case "darwin":
		out, err := exec.CommandContext(
			ctx,
			"ioreg",
			"-rd1",
			"-c",
			"IOPlatformExpertDevice",
		).Output()
		if err == nil {
			for _, line := range strings.Split(string(out), "\n") {
				if !strings.Contains(line, "IOPlatformUUID") {
					continue
				}
				parts := strings.SplitN(line, "=", 2)
				if len(parts) == 2 {
					if value := strings.Trim(strings.TrimSpace(parts[1]), `"`); value != "" {
						return value, nil
					}
				}
			}
		}
	case "windows":
		out, err := exec.CommandContext(
			ctx,
			"powershell",
			"-NoProfile",
			"-Command",
			`(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid`,
		).Output()
		if err == nil {
			if value := strings.TrimSpace(string(out)); value != "" {
				return value, nil
			}
		}
	}
	hostname, _ := os.Hostname()
	if hostname != "" {
		return "hostname:" + strings.ToLower(strings.TrimSpace(hostname)), nil
	}
	return "", fmt.Errorf("stable machine identifier is unavailable")
}

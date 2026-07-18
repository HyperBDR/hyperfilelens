//go:build !windows

package enroll

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"hyperfilelens/agent/internal/platform/install"
)

// StartInstalledService enables and starts the platform service after enrollment.
func StartInstalledService(ctx context.Context) error {
	if runtime.GOOS == "darwin" {
		return startUnixScript(ctx, "start")
	}
	return startSystemd(ctx)
}

func startUnixScript(ctx context.Context, command string) error {
	script := filepath.Join(install.DefaultInstallDir(), "install.sh")
	cmd := exec.CommandContext(ctx, script, command)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return commandError("start service", err, out)
	}
	return nil
}

func startSystemd(ctx context.Context) error {
	if _, err := exec.LookPath("systemctl"); err != nil {
		return fmt.Errorf("systemctl not found")
	}
	for _, args := range [][]string{
		{"daemon-reload"},
		{"enable", "hyperfilelens-agent.service"},
		{"start", "hyperfilelens-agent.service"},
	} {
		cmd := exec.CommandContext(ctx, "systemctl", args...)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("systemctl %s: %w (%s)", strings.Join(args, " "), err, strings.TrimSpace(string(out)))
		}
	}
	active, _ := exec.CommandContext(ctx, "systemctl", "is-active", "hyperfilelens-agent.service").Output()
	if strings.TrimSpace(string(active)) != "active" {
		return fmt.Errorf("service not active after start")
	}
	return nil
}

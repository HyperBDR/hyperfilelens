//go:build windows

package enroll

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// StartInstalledService registers and starts HyperFileLensAgent after enrollment.
func StartInstalledService(ctx context.Context) error {
	return startWindowsService(ctx)
}

func startWindowsService(ctx context.Context) error {
	installRoot := filepath.Join(os.Getenv("ProgramFiles"), "HyperFileLens", "Agent")
	agentBin := filepath.Join(installRoot, "hfl-agent.exe")
	dataRoot := filepath.Join(os.Getenv("ProgramData"), "HyperFileLens", "Agent")
	envFile := filepath.Join(dataRoot, "agent.env")

	if _, err := os.Stat(agentBin); err != nil {
		return fmt.Errorf("agent binary missing at %s", agentBin)
	}

	if data, err := os.ReadFile(envFile); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "HFL_DATA_DIR=") {
				dataRoot = strings.Trim(strings.TrimPrefix(line, "HFL_DATA_DIR="), `"`)
				break
			}
		}
	}

	// Remove stale service if present.
	_ = exec.CommandContext(ctx, "sc.exe", "query", "HyperFileLensAgent").Run()
	_ = exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-Command",
		"Stop-Service -Name HyperFileLensAgent -Force -ErrorAction SilentlyContinue").Run()
	_ = exec.CommandContext(ctx, "sc.exe", "delete", "HyperFileLensAgent").Run()

	binPath := fmt.Sprintf(`"%s" run -data-dir "%s"`, agentBin, dataRoot)
	psScript := fmt.Sprintf(`
$bin = '%s'
$data = '%s'
New-Service -Name HyperFileLensAgent -BinaryPathName $bin -DisplayName 'HyperFileLens Agent' -Description 'HyperFileLens backup agent' -StartupType Automatic | Out-Null
sc.exe failure HyperFileLensAgent reset= 86400 actions= restart/5000/restart/10000/restart/30000 | Out-Null
Start-Service -Name HyperFileLensAgent
`, binPath, dataRoot)

	cmd := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-Command", psScript)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("Windows service start failed: %w (%s)", err, strings.TrimSpace(string(out)))
	}
	return nil
}

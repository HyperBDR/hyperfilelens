//go:build windows

package install

import (
	"fmt"
	"os/exec"
	"strings"
	"syscall"
)

const (
	windowsCreateNewProcessGroup  = 0x00000200
	windowsCreateBreakawayFromJob = 0x01000000
)

func psSingleQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "''") + "'"
}

// startWindowsDetachedScript launches scriptPath outside the agent service job object.
func startWindowsDetachedScript(scriptPath string, logFn func(string)) error {
	scriptPath = strings.TrimSpace(scriptPath)
	if scriptPath == "" {
		return fmt.Errorf("script path required")
	}
	// Start-Process fully detaches from the service process tree (launchd/systemd analogue).
	bootstrap := fmt.Sprintf(
		"Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',%s) -WindowStyle Hidden",
		psSingleQuote(scriptPath),
	)
	cmd := exec.Command(
		"powershell.exe",
		"-NoProfile",
		"-ExecutionPolicy", "Bypass",
		"-WindowStyle", "Hidden",
		"-Command", bootstrap,
	)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: windowsCreateNewProcessGroup | windowsCreateBreakawayFromJob,
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start detached script launcher: %w", err)
	}
	go func() {
		_ = cmd.Wait()
	}()
	if logFn != nil {
		logFn(fmt.Sprintf("started detached runner via Start-Process script=%s", scriptPath))
	}
	return nil
}

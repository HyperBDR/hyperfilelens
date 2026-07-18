package install

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const UninstallLogFileName = "uninstall.log"

// UninstallLogPath returns the absolute uninstall trace file under logDir.
func UninstallLogPath(logDir string) string {
	return filepath.Join(strings.TrimSpace(logDir), UninstallLogFileName)
}

// AppendUninstallLog appends one UTC-stamped line to logs/uninstall.log (best-effort).
func AppendUninstallLog(logDir, message string) error {
	logDir = strings.TrimSpace(logDir)
	if logDir == "" {
		return nil
	}
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		return err
	}
	path := UninstallLogPath(logDir)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = fmt.Fprintf(f, "%s\n", FormatLogLine("INFO", strings.TrimSpace(message)))
	return err
}

func resolveUninstallLogDir(dataDir, logDir string) string {
	logDir = strings.TrimSpace(logDir)
	if logDir != "" {
		return logDir
	}
	dataDir = strings.TrimSpace(dataDir)
	if dataDir == "" {
		return ""
	}
	return filepath.Join(dataDir, "logs")
}

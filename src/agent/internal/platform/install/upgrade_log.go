package install

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const UpgradeLogFileName = "upgrade.log"

// UpgradeLogPath returns the absolute upgrade trace file under logDir.
func UpgradeLogPath(logDir string) string {
	return filepath.Join(strings.TrimSpace(logDir), UpgradeLogFileName)
}

// AppendUpgradeLog appends one UTC-stamped line to logs/upgrade.log (best-effort).
func AppendUpgradeLog(logDir, message string) error {
	logDir = strings.TrimSpace(logDir)
	if logDir == "" {
		return nil
	}
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		return err
	}
	path := UpgradeLogPath(logDir)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = fmt.Fprintf(f, "%s\n", FormatLogLine("INFO", strings.TrimSpace(message)))
	return err
}

func resolveUpgradeLogDir(dataDir, logDir string) string {
	return resolveUninstallLogDir(dataDir, logDir)
}

//go:build !windows

package install

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const upgradeDelaySecond = 5

// ScheduleDetachedUpgrade runs install.sh upgrade after a short delay so the agent
// can report task.result before stop_service terminates the process.
func ScheduleDetachedUpgrade(installDir, archivePath, logDir string) error {
	installDir = strings.TrimSpace(installDir)
	if archivePath = strings.TrimSpace(archivePath); archivePath == "" {
		return fmt.Errorf("upgrade archive path required")
	}
	if installDir == "" {
		installDir = DefaultInstallDir()
	}
	logDir = resolveUpgradeLogDir("", logDir)
	if logDir != "" {
		_ = AppendUpgradeLog(logDir, fmt.Sprintf("Scheduled detached upgrade (archive=%s).", archivePath))
	}
	pendingDir := filepath.Dir(archivePath)
	scriptPath := filepath.Join(pendingDir, pendingUpgradeRunnerName)
	if err := writeUnixUpgradeScript(installDir, archivePath, logDir, scriptPath); err != nil {
		if logDir != "" {
			_ = AppendUpgradeLog(logDir, fmt.Sprintf("Failed to write upgrade script: %v.", err))
		}
		return err
	}
	logFn := func(msg string) {
		if logDir != "" {
			_ = AppendUpgradeLog(logDir, msg)
		}
	}
	if err := startDetachedShellScript("hfl-agent-upgrade", scriptPath, logFn); err != nil {
		return fmt.Errorf("start detached upgrade: %w", err)
	}
	return nil
}

func writeUnixUpgradeScript(installDir, archivePath, logDir, scriptPath string) error {
	installScript := filepath.Join(installDir, "install.sh")
	logFile := UpgradeLogPath(logDir)
	pendingDir := filepath.Dir(archivePath)
	body := fmt.Sprintf(`#!/usr/bin/env bash
set -u
ARCHIVE=%q
INSTALL_SH=%q
LOG_FILE=%q
PENDING_DIR=%q
SLEEP_SECONDS=%d

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
umask 022
exec >>"$LOG_FILE" 2>&1

log() {
  local level="$1"
  shift
  local msg="$*"
  case "${msg}" in
  *.|*.?|*!) ;;
  *) msg="${msg}." ;;
  esac
  printf '[%%s] [%%s] %%s\n' "$(date -u +%%Y-%%m-%%dT%%H:%%M:%%S.000Z 2>/dev/null || date -u +%%Y-%%m-%%dT%%H:%%M:%%SZ)" "${level}" "${msg}"
}

log "INFO " "Detached upgrade script started (archive=${ARCHIVE})."
sleep "$SLEEP_SECONDS"
log "INFO " "Delay elapsed; running upgrade."
%s

if [[ ! -x "$INSTALL_SH" ]]; then
  log "FAIL " "install.sh is missing or not executable at ${INSTALL_SH}."
  exit 1
fi
if [[ ! -f "$ARCHIVE" ]]; then
  log "FAIL " "Upgrade archive is missing at ${ARCHIVE}."
  exit 1
fi

set +e
bash "$INSTALL_SH" upgrade --from "$ARCHIVE" --yes --quiet-footer
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  log " OK  " "Upgrade completed successfully."
  if ! run_gateway_sidecar_upgrade_if_needed; then
    log "FAIL " "Gateway sidecar upgrade failed after agent upgrade."
    echo "failed" > "$PENDING_DIR/FAILED"
    exit 1
  fi
  rm -rf "$PENDING_DIR"
  exit 0
fi
log "FAIL " "Upgrade failed (exit=${rc}). Attempting service recovery."
if command -v systemctl >/dev/null 2>&1; then
  systemctl start hyperfilelens-agent.service 2>/dev/null || true
  if systemctl is-active hyperfilelens-agent.service >/dev/null 2>&1; then
    log " OK  " "Agent service recovered after the failed upgrade."
  else
    log "WARN " "Agent service is still inactive after the failed upgrade."
  fi
fi
echo "failed" > "$PENDING_DIR/FAILED"
exit "$rc"
`,
		archivePath,
		installScript,
		logFile,
		pendingDir,
		upgradeDelaySecond,
		unixGatewaySidecarUpgradeHook,
	)
	if err := os.MkdirAll(filepath.Dir(scriptPath), 0o750); err != nil {
		return err
	}
	return os.WriteFile(scriptPath, []byte(body), 0o700)
}

//go:build !windows

package install

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const (
	unixServiceUnit      = "hyperfilelens-agent.service"
	unixUnitPath         = "/etc/systemd/system/hyperfilelens-agent.service"
	unixLaunchdPlist     = "/Library/LaunchDaemons/com.hyperfilelens.agent.plist"
	unixLaunchdLabel     = "com.hyperfilelens.agent"
	unixDefaultDataRoot  = "/var/lib/hyperfilelens-agent"
	uninstallDelaySecond = 5
)

// ScheduleDetachedUninstall stops the agent service and removes install/data files
// after a short delay so the running process can report task.result upstream first.
func ScheduleDetachedUninstall(installDir, dataDir, logDir string, keepData bool) error {
	installDir = strings.TrimSpace(installDir)
	if installDir == "" {
		installDir = DefaultInstallDir()
	}
	dataDir = strings.TrimSpace(dataDir)
	if dataDir == "" {
		dataDir = unixDefaultDataRoot
	}
	logDir = resolveUninstallLogDir(dataDir, logDir)
	if logDir != "" {
		_ = AppendUninstallLog(
			logDir,
			fmt.Sprintf(
				"scheduled detached uninstall install_dir=%s data_dir=%s keep_data=%t",
				installDir,
				dataDir,
				keepData,
			),
		)
	}
	return scheduleDetachedUninstallUnix(installDir, dataDir, logDir, keepData)
}

func scheduleDetachedUninstallUnix(installDir, dataDir, logDir string, keepData bool) error {
	pendingDir := LifecycleUninstallDir(dataDir)
	if err := os.MkdirAll(pendingDir, 0o750); err != nil {
		return err
	}
	scriptPath := filepath.Join(pendingDir, pendingUninstallRunnerName)
	if err := writeUnixUninstallScript(installDir, dataDir, logDir, keepData, scriptPath); err != nil {
		if logDir != "" {
			_ = AppendUninstallLog(logDir, fmt.Sprintf("failed to write uninstall script: %v", err))
		}
		return err
	}
	logFn := func(msg string) {
		if logDir != "" {
			_ = AppendUninstallLog(logDir, msg)
		}
	}
	if err := startDetachedShellScript("hfl-agent-uninstall", scriptPath, logFn); err != nil {
		return fmt.Errorf("start detached uninstall: %w", err)
	}
	return nil
}

func writeUnixUninstallScript(installDir, dataDir, logDir string, keepData bool, scriptPath string) error {
	keepFlag := "0"
	if keepData {
		keepFlag = "1"
	}
	logFile := UninstallLogPath(logDir)
	body := fmt.Sprintf(`#!/usr/bin/env bash
set -u
INSTALL_DIR=%q
DATA_DIR=%q
LOG_FILE=%q
KEEP_DATA=%s
UNIT_FILE=%q
SERVICE_NAME=%q
LAUNCHD_PLIST=%q
LAUNCHD_LABEL=%q
DEFAULT_DATA_ROOT=%q
SLEEP_SECONDS=%d

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
umask 022
exec >>"$LOG_FILE" 2>&1

uninstall_ts_utc() { date -u +"%%Y-%%m-%%dT%%H:%%M:%%SZ" 2>/dev/null || date -u; }
log() { echo "$(uninstall_ts_utc) $*"; }

log "detached uninstall script started install_dir=$INSTALL_DIR data_dir=$DATA_DIR keep_data=$KEEP_DATA log_file=$LOG_FILE"
sleep "$SLEEP_SECONDS"
log "delay elapsed; running gateway sidecar uninstall when applicable"
%s
run_gateway_sidecar_uninstall_if_needed || log "gateway sidecar uninstall reported errors; continuing agent uninstall"
log "delay elapsed; stopping service"

if [[ "$(uname -s)" == "Darwin" ]]; then
  if launchctl print "system/$LAUNCHD_LABEL" >/dev/null 2>&1; then
    if launchctl bootout "system/$LAUNCHD_LABEL" 2>/dev/null; then
      log "launchctl bootout $LAUNCHD_LABEL succeeded"
    else
      log "launchctl bootout $LAUNCHD_LABEL failed (exit=$?)"
    fi
  else
    log "launchd $LAUNCHD_LABEL not loaded"
  fi
  if [[ -f "$LAUNCHD_PLIST" ]]; then
    if rm -f "$LAUNCHD_PLIST"; then
      log "removed launchd plist $LAUNCHD_PLIST"
    else
      log "failed to remove launchd plist $LAUNCHD_PLIST (exit=$?)"
    fi
  else
    log "launchd plist $LAUNCHD_PLIST not present"
  fi
elif command -v systemctl >/dev/null 2>&1; then
  if systemctl stop "$SERVICE_NAME" 2>/dev/null; then
    log "systemctl stop $SERVICE_NAME succeeded"
  else
    log "systemctl stop $SERVICE_NAME failed (exit=$?)"
  fi
  if systemctl disable "$SERVICE_NAME" 2>/dev/null; then
    log "systemctl disable $SERVICE_NAME succeeded"
  else
    log "systemctl disable $SERVICE_NAME failed (exit=$?)"
  fi
else
  log "systemctl not found; skipped service stop/disable"
fi

if [[ "$(uname -s)" != "Darwin" && -f "$UNIT_FILE" ]]; then
  if rm -f "$UNIT_FILE"; then
    log "removed unit file $UNIT_FILE"
  else
    log "failed to remove unit file $UNIT_FILE (exit=$?)"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload 2>/dev/null || log "systemctl daemon-reload failed (exit=$?)"
  fi
else
  if [[ "$(uname -s)" != "Darwin" ]]; then
    log "unit file $UNIT_FILE not present"
  fi
fi

for target in "$INSTALL_DIR/hfl-agent" "$INSTALL_DIR/kopia" "$INSTALL_DIR/run-agent.sh" "$INSTALL_DIR/INSTALLED_VERSION" "$INSTALL_DIR/install.sh" "$INSTALL_DIR/MANIFEST.json"; do
  if [[ -e "$target" ]]; then
    if rm -f "$target"; then
      log "removed $target"
    else
      log "failed to remove $target (exit=$?)"
    fi
  else
    log "install artifact not present: $target"
  fi
done

case "$INSTALL_DIR" in
  /opt/hyperfilelens-agent|/opt/hyperfilelens-agent/*|/var/lib/hyperfilelens-agent|/var/lib/hyperfilelens-agent/*)
    if [[ -e "$INSTALL_DIR" ]]; then
      if rm -rf "$INSTALL_DIR"; then
        log "removed install directory tree $INSTALL_DIR (including backup artifacts)"
      else
        log "failed to remove install directory tree $INSTALL_DIR (exit=$?)"
      fi
    else
      log "install directory $INSTALL_DIR not present"
    fi
    ;;
  *)
    if [[ -d "$INSTALL_DIR/backup" ]]; then
      if rm -rf "$INSTALL_DIR/backup"; then
        log "removed install backup directory $INSTALL_DIR/backup"
      else
        log "failed to remove install backup directory $INSTALL_DIR/backup (exit=$?)"
      fi
    fi
    if rmdir "$INSTALL_DIR" 2>/dev/null; then
      log "removed install directory $INSTALL_DIR"
    else
      log "install directory $INSTALL_DIR not removed (may be non-empty or missing)"
    fi
    ;;
esac

if [[ "$KEEP_DATA" == "0" ]]; then
  case "$DATA_DIR" in
    /var/lib/hyperfilelens-agent|/var/lib/hyperfilelens-agent/*|/opt/hyperfilelens-agent|/opt/hyperfilelens-agent/*)
      if [[ -e "$DATA_DIR" ]]; then
        if rm -rf "$DATA_DIR"; then
          log "removed data directory $DATA_DIR"
        else
          log "failed to remove data directory $DATA_DIR (exit=$?)"
        fi
      else
        log "data directory $DATA_DIR not present"
      fi
      ;;
    *)
      log "data directory $DATA_DIR outside allowed prefixes; skipped removal"
      ;;
  esac
  if [[ -f "$DEFAULT_DATA_ROOT/agent.env" ]]; then
    if rm -f "$DEFAULT_DATA_ROOT/agent.env"; then
      log "removed $DEFAULT_DATA_ROOT/agent.env"
    else
      log "failed to remove $DEFAULT_DATA_ROOT/agent.env (exit=$?)"
    fi
  fi
else
  log "keep_data=1; preserved data directory $DATA_DIR (uninstall log retained under logs/)"
fi

log "detached uninstall script finished"
`,
		installDir,
		dataDir,
		logFile,
		keepFlag,
		unixUnitPath,
		unixServiceUnit,
		unixLaunchdPlist,
		unixLaunchdLabel,
		unixDefaultDataRoot,
		uninstallDelaySecond,
		unixGatewaySidecarUninstallHook,
	)
	if err := os.MkdirAll(filepath.Dir(scriptPath), 0o750); err != nil {
		return err
	}
	if err := os.WriteFile(scriptPath, []byte(body), 0o700); err != nil {
		return err
	}
	return nil
}

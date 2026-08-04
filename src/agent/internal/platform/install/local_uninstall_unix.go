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
	unixResourceDropIn   = "/etc/systemd/system/hyperfilelens-agent.service.d/20-gateway-resources.conf"
	unixLaunchdPlist     = "/Library/LaunchDaemons/com.hyperfilelens.agent.plist"
	unixLaunchdLabel     = "com.hyperfilelens.agent"
	unixDefaultDataRoot  = "/var/lib/hyperfilelens-agent"
	uninstallDelaySecond = 5
)

// ScheduleDetachedUninstall stops the agent service and removes install/data files
// after a short delay so the running process can report task.result upstream first.
func ScheduleDetachedUninstall(
	installDir, dataDir, logDir string,
	keepData bool,
	completion UninstallCompletion,
) error {
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
	return scheduleDetachedUninstallUnix(installDir, dataDir, logDir, keepData, completion)
}

func scheduleDetachedUninstallUnix(
	installDir, dataDir, logDir string,
	keepData bool,
	completion UninstallCompletion,
) error {
	pendingDir := LifecycleUninstallDir(dataDir)
	if err := os.MkdirAll(pendingDir, 0o750); err != nil {
		return err
	}
	scriptPath := filepath.Join(pendingDir, pendingUninstallRunnerName)
	if err := writeUnixUninstallScript(
		installDir,
		dataDir,
		logDir,
		keepData,
		completion,
		scriptPath,
	); err != nil {
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

func writeUnixUninstallScript(
	installDir, dataDir, logDir string,
	keepData bool,
	completion UninstallCompletion,
	scriptPath string,
) error {
	keepFlag := "0"
	if keepData {
		keepFlag = "1"
	}
	callbackURL, err := completion.CallbackURL()
	if err != nil {
		return err
	}
	insecureTLSFlag := "0"
	if completion.InsecureTLS {
		insecureTLSFlag = "1"
	}
	forceCleanupFlag := "0"
	if completion.ForceCleanup {
		forceCleanupFlag = "1"
	}
	logFile := UninstallLogPath(logDir)
	body := fmt.Sprintf(`#!/usr/bin/env bash
set -u
INSTALL_DIR=%q
DATA_DIR=%q
LOG_FILE=%q
KEEP_DATA=%s
UNIT_FILE=%q
RESOURCE_DROPIN=%q
SERVICE_NAME=%q
LAUNCHD_PLIST=%q
LAUNCHD_LABEL=%q
DEFAULT_DATA_ROOT=%q
SLEEP_SECONDS=%d
CALLBACK_URL=%q
CALLBACK_TOKEN=%q
CALLBACK_INSECURE_TLS=%s
FORCE_CLEANUP=%s
CLEANUP_FAILED=0
GATEWAY_SIDECAR_FAILED=0
MANAGED_MOUNTS_FAILED=0
AGENT_ARTIFACTS_FAILED=0

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
umask 022
exec >>"$LOG_FILE" 2>&1

uninstall_ts_utc() { date -u +"%%Y-%%m-%%dT%%H:%%M:%%SZ" 2>/dev/null || date -u; }
log() { echo "$(uninstall_ts_utc) $*"; }
report_uninstall_completion() {
  local rc="$1" complete="true" payload_file
  local failures retained
  local -a failure_items=() retained_items=()
  if [[ "$GATEWAY_SIDECAR_FAILED" -eq 1 ]]; then
    failure_items+=('{"code":"gateway_sidecar_uninstall_failed","detail":"LensNode sidecar cleanup did not complete."}')
    retained_items+=('"lensnode_sidecar"')
  fi
  if [[ "$MANAGED_MOUNTS_FAILED" -eq 1 ]]; then
    failure_items+=('{"code":"managed_mount_cleanup_failed","detail":"One or more Agent-managed NAS mounts could not be unmounted."}')
    retained_items+=('"managed_nas_mounts"')
  fi
  if [[ "$AGENT_ARTIFACTS_FAILED" -eq 1 ]]; then
    failure_items+=('{"code":"agent_uninstall_failed","detail":"Agent service, files, or data remain after cleanup."}')
    retained_items+=('"agent_installation"')
  fi
  if [[ "${#failure_items[@]}" -eq 0 && ( "$rc" -ne 0 || "$CLEANUP_FAILED" -ne 0 ) ]]; then
    failure_items+=('{"code":"detached_uninstall_failed","detail":"Detached uninstall exited before all cleanup steps completed."}')
    retained_items+=('"agent_installation_or_managed_mounts"')
  fi
  failures="[$(IFS=,; echo "${failure_items[*]}")]"
  retained="[$(IFS=,; echo "${retained_items[*]}")]"
  [[ "$rc" -eq 0 && "$CLEANUP_FAILED" -eq 0 ]] || {
    complete="false"
  }
  command -v curl >/dev/null 2>&1 || {
    log "curl not found; uninstall completion callback could not be sent"
    return 0
  }
  payload_file="$(mktemp "${TMPDIR:-/tmp}/hfl-uninstall-completion.XXXXXX")" || return 0
  chmod 600 "$payload_file" 2>/dev/null || true
  printf '{"token":"%%s","cleanup_complete":%%s,"cleanup_failures":%%s,"retained_resources":%%s}\n' \
    "$CALLBACK_TOKEN" "$complete" "$failures" "$retained" >"$payload_file"
  local -a curl_args=(-fsS -X POST -H 'Content-Type: application/json' --data-binary "@$payload_file")
  [[ "$CALLBACK_INSECURE_TLS" == "1" ]] && curl_args+=(-k)
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if curl "${curl_args[@]}" "$CALLBACK_URL" >/dev/null; then
      log "uninstall completion callback accepted cleanup_complete=$complete attempt=$attempt"
      break
    fi
    log "uninstall completion callback failed attempt=$attempt"
    [[ "$attempt" -lt 6 ]] && sleep 10
  done
  rm -f "$payload_file"
}
finish_detached_uninstall() {
  local rc="$?"
  trap - EXIT
  report_uninstall_completion "$rc"
  rm -f -- "$0" 2>/dev/null || true
  exit "$rc"
}
trap finish_detached_uninstall EXIT
%s

verify_uninstall_artifacts() {
  local failed=0 target
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if launchctl print "system/$LAUNCHD_LABEL" >/dev/null 2>&1; then
      log "launchd service remains loaded: $LAUNCHD_LABEL"
      failed=1
    fi
  elif command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
      log "systemd service remains active: $SERVICE_NAME"
      failed=1
    fi
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
      log "systemd service remains enabled: $SERVICE_NAME"
      failed=1
    fi
  fi
  for target in \
    "$INSTALL_DIR/hfl-agent" \
    "$INSTALL_DIR/kopia" \
    "$INSTALL_DIR/run-agent.sh" \
    "$INSTALL_DIR/INSTALLED_VERSION" \
    "$INSTALL_DIR/install.sh" \
    "$INSTALL_DIR/MANIFEST.json" \
    "$UNIT_FILE" \
    "$RESOURCE_DROPIN" \
    "$LAUNCHD_PLIST"; do
    if [[ -e "$target" ]]; then
      log "uninstall artifact remains: $target"
      failed=1
    fi
  done
  if [[ "$KEEP_DATA" == "0" && -e "$DATA_DIR" ]]; then
    log "data directory remains after requested purge: $DATA_DIR"
    failed=1
  fi
  return "$failed"
}

log "detached uninstall script started install_dir=$INSTALL_DIR data_dir=$DATA_DIR keep_data=$KEEP_DATA log_file=$LOG_FILE"
sleep "$SLEEP_SECONDS"
log "delay elapsed; running gateway sidecar uninstall when applicable"
%s
if ! run_gateway_sidecar_uninstall_if_needed; then
  CLEANUP_FAILED=1
  GATEWAY_SIDECAR_FAILED=1
  if [[ "$FORCE_CLEANUP" == "1" ]]; then
    log "gateway sidecar uninstall failed; Force Cleanup will continue with Agent cleanup"
  else
    AGENT_ARTIFACTS_FAILED=1
    log "gateway sidecar uninstall failed; keeping the Agent installed for retry"
    exit 1
  fi
fi
log "cleaning Agent-managed NAS mounts before stopping the Agent service"
if ! unmount_agent_mounts "$DATA_DIR"; then
  CLEANUP_FAILED=1
  MANAGED_MOUNTS_FAILED=1
  if [[ "$FORCE_CLEANUP" == "1" ]]; then
    log "Agent-managed NAS mount cleanup failed; Force Cleanup will continue with Agent cleanup"
  else
    AGENT_ARTIFACTS_FAILED=1
    log "Agent-managed NAS mount cleanup failed; preserving Agent files and data for manual retry"
    exit 1
  fi
fi
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

if [[ "$(uname -s)" != "Darwin" && -f "$RESOURCE_DROPIN" ]]; then
  if rm -f "$RESOURCE_DROPIN"; then
    log "removed gateway resource policy $RESOURCE_DROPIN"
    rmdir "$(dirname "$RESOURCE_DROPIN")" 2>/dev/null || true
  else
    log "failed to remove gateway resource policy $RESOURCE_DROPIN (exit=$?)"
  fi
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

if [[ "$KEEP_DATA" == "1" ]]; then
  if [[ ! -x "$INSTALL_DIR/hfl-agent" ]]; then
    log "cannot retire installation identity because $INSTALL_DIR/hfl-agent is unavailable"
    AGENT_ARTIFACTS_FAILED=1
    exit 1
  fi
  if ! HFL_DATA_DIR="$DATA_DIR" \
    "$INSTALL_DIR/hfl-agent" config retire-installation --data-dir "$DATA_DIR"; then
    log "failed to retire installation identity; Agent files and data were preserved for retry"
    AGENT_ARTIFACTS_FAILED=1
    exit 1
  fi
  log "retired installation identity; the next install will create a new console record"
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
          if [[ -e "$DATA_DIR" ]]; then
            log "data directory $DATA_DIR remains after removal"
            AGENT_ARTIFACTS_FAILED=1
            exit 1
          fi
          log "removed data directory $DATA_DIR"
        else
          log "failed to remove data directory $DATA_DIR (exit=$?)"
          AGENT_ARTIFACTS_FAILED=1
          exit 1
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

if ! verify_uninstall_artifacts; then
  CLEANUP_FAILED=1
  AGENT_ARTIFACTS_FAILED=1
  if [[ "$FORCE_CLEANUP" == "1" ]]; then
    log "post-uninstall verification found residue; Force Cleanup will report it and finish"
  else
    log "post-uninstall verification failed; Strict Cleanup remains retryable"
    exit 1
  fi
fi

log "detached uninstall script finished"
`,
		installDir,
		dataDir,
		logFile,
		keepFlag,
		unixUnitPath,
		unixResourceDropIn,
		unixServiceUnit,
		unixLaunchdPlist,
		unixLaunchdLabel,
		unixDefaultDataRoot,
		uninstallDelaySecond,
		callbackURL,
		completion.Token,
		insecureTLSFlag,
		forceCleanupFlag,
		unixManagedMountCleanupScript,
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

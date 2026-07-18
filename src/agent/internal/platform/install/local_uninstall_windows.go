//go:build windows

package install

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"hyperfilelens/agent/internal/platform/vfs"
)

const uninstallDelaySecond = 5

const windowsUninstallRunnerName = "run-uninstall.ps1"

// ScheduleDetachedUninstall stops the agent service and removes install/data files
// after a short delay so the running process can report task.result upstream first.
func ScheduleDetachedUninstall(installDir, dataDir, logDir string, keepData bool) error {
	installDir = strings.TrimSpace(installDir)
	if installDir == "" {
		installDir = DefaultInstallDir()
	}
	dataDir = strings.TrimSpace(dataDir)
	if dataDir == "" {
		dataDir = vfs.DefaultAgentDataDir()
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
	tmpDir := os.TempDir()
	scriptPath := filepath.Join(
		tmpDir,
		fmt.Sprintf("%s-%d.ps1", strings.TrimSuffix(windowsUninstallRunnerName, ".ps1"), time.Now().UnixNano()),
	)
	if err := writeWindowsUninstallScript(installDir, dataDir, logDir, keepData, scriptPath); err != nil {
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
	if err := startWindowsDetachedScript(scriptPath, logFn); err != nil {
		return fmt.Errorf("start detached uninstall: %w", err)
	}
	return nil
}

func writeWindowsUninstallScript(installDir, dataDir, logDir string, keepData bool, scriptPath string) error {
	keepFlag := "0"
	if keepData {
		keepFlag = "1"
	}
	logFile := UninstallLogPath(logDir)
	body := fmt.Sprintf(`$logFile = %q
$install = %q
$data = %q
$keep = %s
$SLEEP_SECONDS = %d

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logFile) | Out-Null
function Log([string]$msg) {
  $ts = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
  Add-Content -LiteralPath $logFile -Value "$ts $msg" -Encoding UTF8
}

function Start-DeferredRemove([string]$target) {
  if (-not (Test-Path -LiteralPath $target)) {
    Log "deferred remove skipped (not present): $target"
    return
  }
  $deferCmd = 'ping -n 3 127.0.0.1 >nul & rmdir /s /q "' + $target + '"'
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $deferCmd -WindowStyle Hidden | Out-Null
  Log "scheduled deferred removal of $target"
}

function Stop-HflProcessesForUninstall {
  Log "stopping HyperFileLensAgent service and child processes (pre-uninstall)"
  Stop-Service -Name HyperFileLensAgent -Force -ErrorAction SilentlyContinue
  foreach ($procName in @('hfl-agent', 'kopia')) {
    Stop-Process -Name $procName -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 3
}

function Remove-InstallDirectoryResidue {
  param([string]$InstallDir)
  Start-Sleep -Seconds 2
  $installCmd = Join-Path $InstallDir "install.cmd"
  if (Test-Path -LiteralPath $installCmd) {
    Remove-Item -Force -LiteralPath $installCmd -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $installCmd) {
      Log "residual install.cmd still present after first remove attempt"
      Start-Sleep -Seconds 2
      Remove-Item -Force -LiteralPath $installCmd -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path -LiteralPath $installCmd)) {
      Log "removed residual install.cmd"
    }
  }
  if (-not (Test-Path -LiteralPath $InstallDir)) { return }
  foreach ($attempt in 1..3) {
    try {
      Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction Stop
      Log "removed install directory $InstallDir (attempt $attempt)"
      return
    } catch {
      Log "install directory remove attempt $attempt failed: $($_.Exception.Message)"
      Start-Sleep -Seconds 2
    }
  }
  Start-DeferredRemove $InstallDir
}

function Confirm-UninstallArtifacts {
  param(
    [string]$InstallDir,
    [string]$DataDir,
    [string]$KeepFlag
  )
  # Allow Schedule-InstallRootRemoval deferred cleanup to run first.
  Start-Sleep -Seconds 6
  $issues = @()
  if (Test-Path -LiteralPath $InstallDir) {
    $issues += "install directory still present: $InstallDir"
  }
  if ($KeepFlag -eq '0' -and (Test-Path -LiteralPath $DataDir)) {
    $issues += "data directory still present: $DataDir"
  }
  return $issues
}

Log "detached uninstall script started install_dir=$install data_dir=$data keep_data=$keep"
$ErrorActionPreference = 'Stop'
try {
  Start-Sleep -Seconds $SLEEP_SECONDS
  Log "delay elapsed; running uninstall"
  Stop-HflProcessesForUninstall

  $installCmd = Join-Path $install "install.cmd"
  $installPs1 = Join-Path $install "install.ps1"
  $usedInstallCmd = $false
  if (Test-Path -LiteralPath $installCmd) {
    $usedInstallCmd = $true
    Log "running install.cmd uninstall"
    $cmdLine = '"' + $installCmd + '" uninstall'
    if ($keep -eq '0') {
      $cmdLine += ' -PurgeAll'
    }
    Push-Location $env:TEMP
    try {
      $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $cmdLine -Wait -PassThru -WindowStyle Hidden
      $rc = if ($null -ne $proc) { $proc.ExitCode } else { 1 }
    } finally {
      Pop-Location
    }
    if ($rc -ne 0) {
      Log "install.cmd uninstall failed exit=$rc"
      exit $rc
    }
    Log "install.cmd uninstall succeeded"
    Remove-InstallDirectoryResidue -InstallDir $install
  } elseif (Test-Path -LiteralPath $installPs1) {
    Log "install.cmd missing; running install.ps1 uninstall fallback"
    $uninstallArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installPs1, 'uninstall')
    if ($keep -eq '0') {
      $uninstallArgs += '-PurgeAll'
    }
    Push-Location $env:TEMP
    try {
      $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $uninstallArgs -Wait -PassThru -WindowStyle Hidden
      $rc = if ($null -ne $proc) { $proc.ExitCode } else { 1 }
    } finally {
      Pop-Location
    }
    if ($rc -ne 0) {
      Log "install.ps1 uninstall failed exit=$rc"
      exit $rc
    }
    Log "install.ps1 uninstall succeeded"
  } else {
    Log "install.cmd and install.ps1 missing; running fallback cleanup"
    sc.exe delete HyperFileLensAgent 2>$null | Out-Null
    Start-DeferredRemove $install
  }

  if (-not $usedInstallCmd -and $keep -eq '0') {
    Start-DeferredRemove $data
  } elseif ($keep -eq '1') {
    Log "keep_data=1; preserved data directory $data"
  }

  $issues = @(Confirm-UninstallArtifacts -InstallDir $install -DataDir $data -KeepFlag $keep)
  if ($issues.Count -gt 0) {
    foreach ($issue in $issues) { Log "post-uninstall verify: $issue" }
    Log "detached uninstall script finished with errors"
    exit 1
  }

  Log "detached uninstall script finished"
  exit 0
} catch {
  Log "detached uninstall script failed: $($_.Exception.Message)"
  exit 1
}
`,
		logFile,
		installDir,
		dataDir,
		keepFlag,
		uninstallDelaySecond,
	)
	if err := os.MkdirAll(filepath.Dir(scriptPath), 0o750); err != nil {
		return err
	}
	return os.WriteFile(scriptPath, append([]byte{0xEF, 0xBB, 0xBF}, []byte(body)...), 0o644)
}

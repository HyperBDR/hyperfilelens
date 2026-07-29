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
	if err := writeWindowsUninstallScript(
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
	if err := startWindowsDetachedScript(scriptPath, logFn); err != nil {
		return fmt.Errorf("start detached uninstall: %w", err)
	}
	return nil
}

func writeWindowsUninstallScript(
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
	insecureTLSFlag := "$false"
	if completion.InsecureTLS {
		insecureTLSFlag = "$true"
	}
	forceCleanupFlag := "$false"
	if completion.ForceCleanup {
		forceCleanupFlag = "$true"
	}
	logFile := UninstallLogPath(logDir)
	body := fmt.Sprintf(`$logFile = %q
$install = %q
$data = %q
$keep = %s
$SLEEP_SECONDS = %d
$callbackUrl = %q
$callbackToken = %q
$callbackInsecureTls = %s
$forceCleanup = %s
$cleanupFailures = @()
$retainedResources = @()

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logFile) | Out-Null
function Log([string]$msg) {
  $ts = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
  Add-Content -LiteralPath $logFile -Value "$ts $msg" -Encoding UTF8
}

function Add-CleanupFailure(
  [string]$code,
  [string]$detail,
  [string[]]$retained = @()
) {
  $script:cleanupFailures += @{
    code = $code
    detail = $detail
  }
  foreach ($resource in $retained) {
    if ($resource -and $script:retainedResources -notcontains $resource) {
      $script:retainedResources += $resource
    }
  }
  Log "cleanup failure code=$code detail=$detail"
}

function Stop-Or-ContinueAfterFailure {
  if ($forceCleanup) {
    Log "Force Cleanup will continue with the remaining physical cleanup steps"
    return
  }
  throw "Strict Cleanup stopped after a required physical cleanup step failed."
}

function Report-UninstallCompletion {
  if ($callbackInsecureTls) {
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
  }
  $complete = $cleanupFailures.Count -eq 0
  $payload = @{
    token = $callbackToken
    cleanup_complete = $complete
    cleanup_failures = @($cleanupFailures)
    retained_resources = @($retainedResources)
  } | ConvertTo-Json -Depth 5 -Compress
  foreach ($attempt in 1..6) {
    try {
      Invoke-RestMethod -Method Post -Uri $callbackUrl -ContentType 'application/json' -Body $payload | Out-Null
      Log "uninstall completion callback accepted cleanup_complete=$complete attempt=$attempt"
      return
    } catch {
      Log "uninstall completion callback failed attempt=${attempt}: $($_.Exception.Message)"
      if ($attempt -lt 6) { Start-Sleep -Seconds 10 }
    }
  }
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
  if ($null -ne (Get-Service -Name HyperFileLensAgent -ErrorAction SilentlyContinue)) {
    $issues += "HyperFileLensAgent service is still registered"
  }
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
  try {
    Stop-HflProcessesForUninstall
  } catch {
    Add-CleanupFailure -code 'agent_process_stop_failed' -detail $_.Exception.Message -retained @('agent_processes')
    Stop-Or-ContinueAfterFailure
  }

  $installCmd = Join-Path $install "install.cmd"
  $installPs1 = Join-Path $install "install.ps1"
  $usedInstallCmd = $false
  $installerSucceeded = $false
  $failureCountBefore = $cleanupFailures.Count
  try {
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
        Add-CleanupFailure -code 'install_cmd_uninstall_failed' -detail "install.cmd uninstall failed exit=$rc" -retained @('agent_installation')
        Stop-Or-ContinueAfterFailure
      } else {
        Log "install.cmd uninstall succeeded"
        $installerSucceeded = $true
      }
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
        Add-CleanupFailure -code 'install_ps1_uninstall_failed' -detail "install.ps1 uninstall failed exit=$rc" -retained @('agent_installation')
        Stop-Or-ContinueAfterFailure
      } else {
        Log "install.ps1 uninstall succeeded"
        $installerSucceeded = $true
      }
    } else {
      Log "install.cmd and install.ps1 missing; running fallback cleanup"
      sc.exe delete HyperFileLensAgent 2>$null | Out-Null
      Start-DeferredRemove $install
      $installerSucceeded = $true
    }
  } catch {
    if ($cleanupFailures.Count -eq $failureCountBefore) {
      Add-CleanupFailure -code 'agent_installation_cleanup_failed' -detail $_.Exception.Message -retained @('agent_installation')
    }
    Stop-Or-ContinueAfterFailure
  }

  try {
    if ($keep -eq '0' -and (-not $usedInstallCmd -or ($forceCleanup -and -not $installerSucceeded))) {
      Start-DeferredRemove $data
    } elseif ($keep -eq '1') {
      Log "keep_data=1; preserved data directory $data"
    }
  } catch {
    Add-CleanupFailure -code 'agent_data_cleanup_failed' -detail $_.Exception.Message -retained @('agent_data')
    Stop-Or-ContinueAfterFailure
  }

  try {
    $issues = @(Confirm-UninstallArtifacts -InstallDir $install -DataDir $data -KeepFlag $keep)
    if ($issues.Count -gt 0) {
      foreach ($issue in $issues) {
        Log "post-uninstall verify: $issue"
        Add-CleanupFailure -code 'uninstall_artifact_retained' -detail $issue -retained @($issue)
      }
    }
  } catch {
    Add-CleanupFailure -code 'uninstall_verification_failed' -detail $_.Exception.Message -retained @('agent_installation_or_data')
    Stop-Or-ContinueAfterFailure
  }

  if ($cleanupFailures.Count -gt 0) {
    Log "detached uninstall script finished with cleanup residue"
  } else {
    Log "detached uninstall script finished"
  }
} catch {
  Log "detached uninstall script failed: $($_.Exception.Message)"
  if ($cleanupFailures.Count -eq 0) {
    Add-CleanupFailure -code 'detached_uninstall_failed' -detail $_.Exception.Message -retained @('agent_installation_or_managed_mounts')
  }
}

Report-UninstallCompletion
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
if ($cleanupFailures.Count -eq 0) {
  exit 0
}
if ($forceCleanup) {
  Log "Force Cleanup accepted the recorded uninstall residue"
  exit 0
} else {
  exit 1
}
`,
		logFile,
		installDir,
		dataDir,
		keepFlag,
		uninstallDelaySecond,
		callbackURL,
		completion.Token,
		insecureTLSFlag,
		forceCleanupFlag,
	)
	if err := os.MkdirAll(filepath.Dir(scriptPath), 0o750); err != nil {
		return err
	}
	return os.WriteFile(scriptPath, append([]byte{0xEF, 0xBB, 0xBF}, []byte(body)...), 0o644)
}

//go:build windows

package install

import (
	"os"
	"strings"
	"testing"
)

func TestWriteWindowsUninstallScriptUsesUninstallLogAndInstallPs1(t *testing.T) {
	dir := t.TempDir()
	dataDir := dir + `/data`
	logDir := dir + `/data/logs`
	path := dir + "/run-uninstall.ps1"
	err := writeWindowsUninstallScript(
		`C:\Program Files\HyperFileLens\Agent`,
		dataDir,
		logDir,
		false,
		UninstallCompletion{
			APIBaseURL: "https://control.example",
			Path:       "/api/v1/node/agent-uninstall/completion/",
			Token:      "signed-test-token",
		},
		path,
	)
	if err != nil {
		t.Fatalf("writeWindowsUninstallScript: %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read script: %v", err)
	}
	body := string(raw)
	for _, want := range []string{
		UninstallLogPath(logDir),
		`install.cmd uninstall`,
		`-PurgeAll`,
		`Stop-HflProcessesForUninstall`,
		`Start-Sleep -Seconds 3`,
		`Remove-InstallDirectoryResidue`,
		`removed residual install.cmd`,
		`Confirm-UninstallArtifacts`,
		`Get-Service -Name HyperFileLensAgent`,
		`post-uninstall verify:`,
		`install.cmd uninstall succeeded`,
		`Push-Location $env:TEMP`,
		`Start-DeferredRemove`,
		`ping -n 3 127.0.0.1 >nul & rmdir /s /q "`,
		`Add-CleanupFailure`,
		`Stop-Or-ContinueAfterFailure`,
		`Force Cleanup will continue with the remaining physical cleanup steps`,
		`Report-UninstallCompletion`,
		`cleanup_failures = @($cleanupFailures)`,
		`retained_resources = @($retainedResources)`,
		`foreach ($attempt in 1..6)`,
		`Remove-Item -LiteralPath $PSCommandPath`,
		`"signed-test-token"`,
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("script missing %q:\n%s", want, body)
		}
	}
	if strings.Contains(body, ".install.out") {
		t.Fatalf("script must not reference separate install output log:\n%s", body)
	}
}

func TestWriteWindowsForceCleanupScriptContinuesAfterInstallerFailure(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/run-uninstall.ps1"
	err := writeWindowsUninstallScript(
		`C:\Program Files\HyperFileLens\Agent`,
		dir+`/data`,
		dir+`/data/logs`,
		false,
		UninstallCompletion{
			APIBaseURL:   "https://control.example",
			Path:         "/api/v1/node/agent-uninstall/completion/",
			Token:        "signed-test-token",
			ForceCleanup: true,
		},
		path,
	)
	if err != nil {
		t.Fatalf("writeWindowsUninstallScript: %v", err)
	}
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read script: %v", err)
	}
	text := string(body)
	for _, want := range []string{
		`$forceCleanup = $true`,
		`install_cmd_uninstall_failed`,
		`Stop-Or-ContinueAfterFailure`,
		`Remove-InstallDirectoryResidue -InstallDir $install`,
		`$forceCleanup -and -not $installerSucceeded`,
		`Confirm-UninstallArtifacts`,
		`Force Cleanup accepted the recorded uninstall residue`,
	} {
		if !strings.Contains(text, want) {
			t.Fatalf("Force Cleanup script missing %q:\n%s", want, text)
		}
	}
}

func TestWriteWindowsUninstallScriptKeepDataSkipsPurgeAll(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/run-uninstall.ps1"
	err := writeWindowsUninstallScript(
		`C:\Program Files\HyperFileLens\Agent`,
		dir+`/data`,
		dir+`/data/logs`,
		true,
		UninstallCompletion{
			APIBaseURL: "https://control.example",
			Path:       "/api/v1/node/agent-uninstall/completion/",
			Token:      "signed-test-token",
		},
		path,
	)
	if err != nil {
		t.Fatalf("writeWindowsUninstallScript: %v", err)
	}
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read script: %v", err)
	}
	text := string(body)
	if strings.Contains(text, "-PurgeAll") {
		t.Fatalf("keep_data script must not pass -PurgeAll:\n%s", text)
	}
	if !strings.Contains(text, "keep_data=1; preserved data directory") {
		t.Fatalf("keep_data script missing preserve log line:\n%s", text)
	}
}

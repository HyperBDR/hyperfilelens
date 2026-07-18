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
		`post-uninstall verify:`,
		`install.cmd uninstall succeeded`,
		`Push-Location $env:TEMP`,
		`Start-DeferredRemove`,
		`ping -n 3 127.0.0.1 >nul & rmdir /s /q "`,
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("script missing %q:\n%s", want, body)
		}
	}
	if strings.Contains(body, ".install.out") {
		t.Fatalf("script must not reference separate install output log:\n%s", body)
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

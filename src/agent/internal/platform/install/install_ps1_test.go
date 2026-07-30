package install

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestInstallPs1PurgeDoesNotRecreateDataLogDirectory(t *testing.T) {
	source := readPackagingInstallScript(t)
	for _, want := range []string{
		"if (-not `$dir -or -not (Test-Path -LiteralPath `$dir)) { return }",
		`$uninstallLog = if (-not $PurgeAll -and $uninstallLogPath) { $uninstallLogPath } else { "" }`,
	} {
		if !strings.Contains(source, want) {
			t.Fatalf("install.ps1 missing %q", want)
		}
	}
	if strings.Contains(source, "if (`$dir) { New-Item -ItemType Directory -Force -Path `$dir") {
		t.Fatal("deferred install-root cleanup must not recreate the uninstall log directory")
	}
}

func TestInstallPs1SafeDataPathRequiresHyperFileLensDescendant(t *testing.T) {
	source := readPackagingInstallScript(t)
	for _, want := range []string{
		`$allowedRoot = Join-Path $pd "HyperFileLens"`,
		`$allowedRoot.TrimEnd('\') + '\'`,
	} {
		if !strings.Contains(source, want) {
			t.Fatalf("install.ps1 safe data path check missing %q", want)
		}
	}
	if strings.Contains(source, `StartsWith($pd.TrimEnd('\') + '\HyperFileLens'`) {
		t.Fatal("safe data path check must enforce a path-component boundary")
	}
}

func readPackagingInstallScript(t *testing.T) string {
	t.Helper()
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve current test file")
	}
	path := filepath.Clean(filepath.Join(
		filepath.Dir(currentFile),
		"..", "..", "..", "packaging", "install", "install.ps1",
	))
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		t.Skipf("packaging source is not available beside the compiled test: %s", path)
	}
	if err != nil {
		t.Fatalf("read install.ps1: %v", err)
	}
	return string(raw)
}

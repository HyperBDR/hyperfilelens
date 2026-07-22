package hostinfo

import (
	"os"
	"path/filepath"
	"testing"
)

func TestApplyLinuxOSRelease(t *testing.T) {
	path := filepath.Join(t.TempDir(), "os-release")
	content := "ID=ubuntu\nNAME=Ubuntu\nPRETTY_NAME=\"Ubuntu 24.04.2 LTS\"\nVERSION_ID=\"24.04\"\n"
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	info := Info{OSName: "linux"}
	applyLinuxOSRelease(&info, path)
	if info.OSName != "Ubuntu 24.04.2 LTS" || info.OSVersion != "24.04" {
		t.Fatalf("unexpected info: %+v", info)
	}
}

func TestDescription(t *testing.T) {
	info := Info{OSFamily: "linux", OSName: "Ubuntu", OSVersion: "24.04", Arch: "arm64"}
	if got, want := info.Description(), "linux/arm64 (Ubuntu 24.04)"; got != want {
		t.Fatalf("Description()=%q want %q", got, want)
	}
}

func TestLastNumericComponent(t *testing.T) {
	if got := lastNumericComponent("10.0.20348 Build 20348"); got != "20348" {
		t.Fatalf("got %q", got)
	}
}

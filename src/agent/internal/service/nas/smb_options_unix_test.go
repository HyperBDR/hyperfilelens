//go:build !windows

package nas

import (
	"strings"
	"testing"

	"hyperfilelens/agent/internal/platform/process"
)

func TestSMBMountOptionsInlineAuth(t *testing.T) {
	spec := Spec{
		Server:   "192.168.14.23",
		Share:    "backup",
		Username: "backupuser",
		Password: "Abc999@1",
		Options:  "uid=1000,gid=1000",
	}
	opts, cleanup, err := smbMountOptions(spec)
	defer cleanup()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	joined := strings.Join(opts, ",")
	if strings.Contains(joined, "credentials=") {
		t.Fatalf("expected inline auth, got %q", joined)
	}
	for _, want := range []string{"rw", "iocharset=utf8", "username=backupuser", "password=Abc999@1", "uid=1000", "gid=1000"} {
		if !strings.Contains(joined, want) {
			t.Fatalf("missing %q in %q", want, joined)
		}
	}
	for _, banned := range []string{"nounix", "sec=ntlmssp"} {
		if strings.Contains(joined, banned) {
			t.Fatalf("unexpected default option %q in %q", banned, joined)
		}
	}
}

func TestSMBMountOptionsUserOverridesIOCharset(t *testing.T) {
	spec := Spec{
		Username: "backupuser",
		Password: "secret",
		Options:  "iocharset=cp850",
	}
	opts, cleanup, err := smbMountOptions(spec)
	defer cleanup()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	joined := strings.Join(opts, ",")
	if strings.Contains(joined, "iocharset=utf8") {
		t.Fatalf("expected user iocharset override, got %q", joined)
	}
	if !strings.Contains(joined, "iocharset=cp850") {
		t.Fatalf("missing user iocharset in %q", joined)
	}
}

func TestSMBMountOptionsUserOverridesRW(t *testing.T) {
	opts, cleanup, err := smbMountOptions(Spec{Options: "ro"})
	defer cleanup()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	joined := strings.Join(opts, ",")
	if mountOptionsContainKey(joined, "rw") {
		t.Fatalf("expected ro to replace rw, got %q", joined)
	}
	if !mountOptionsContainKey(joined, "ro") {
		t.Fatalf("missing ro in %q", joined)
	}
}

func TestMountOptionsContainKey(t *testing.T) {
	if !mountOptionsContainKey("vers=3.0,iocharset=cp850", "iocharset") {
		t.Fatal("expected iocharset option")
	}
	if mountOptionsContainKey("vers=3.0,uid=1000", "iocharset") {
		t.Fatal("did not expect iocharset option")
	}
	if !mountOptionsContainKey("vers=3.0,IOCHARSET=utf8", "iocharset") {
		t.Fatal("expected case-insensitive iocharset option")
	}
}

func TestMountOptionsContainKeyValue(t *testing.T) {
	if !mountOptionsContainKeyValue("rw,iocharset=UTF8,vers=3.0", "iocharset", "utf8") {
		t.Fatal("expected iocharset=utf8 option")
	}
	if mountOptionsContainKeyValue("rw,iocharset=cp850,vers=3.0", "iocharset", "utf8") {
		t.Fatal("did not expect iocharset=utf8 option")
	}
}

func TestUnavailableSMBCharset(t *testing.T) {
	charset, unavailable := unavailableSMBCharset(
		"rw,iocharset=utf8,vers=3.1.1",
		process.Result{Stderr: "CIFS mount error: iocharset utf8 not found"},
		errExitForTest{},
	)
	if !unavailable || charset != "utf8" {
		t.Fatalf("unavailableSMBCharset() = (%q, %v), want (utf8, true)", charset, unavailable)
	}
}

func TestUnavailableSMBCharsetSupportsCIFSError79(t *testing.T) {
	charset, unavailable := unavailableSMBCharset(
		"rw,iocharset=utf8,vers=3.1.1",
		process.Result{Stderr: "mount error(79): Can not access a needed shared library"},
		errExitForTest{},
	)
	if !unavailable || charset != "utf8" {
		t.Fatalf("unavailableSMBCharset() = (%q, %v), want (utf8, true)", charset, unavailable)
	}
}

func TestUnavailableSMBCharsetSupportsExplicitOverride(t *testing.T) {
	charset, unavailable := unavailableSMBCharset(
		"rw,iocharset=cp936",
		process.Result{Stderr: "unable to load NLS charset cp936"},
		errExitForTest{},
	)
	if !unavailable || charset != "cp936" {
		t.Fatalf("unavailableSMBCharset() = (%q, %v), want (cp936, true)", charset, unavailable)
	}
}

func TestUnavailableSMBCharsetIgnoresUnrelatedErrors(t *testing.T) {
	_, unavailable := unavailableSMBCharset(
		"rw,iocharset=utf8",
		process.Result{Stderr: "mount error(13): Permission denied"},
		errExitForTest{},
	)
	if unavailable {
		t.Fatal("did not expect unrelated mount error to be classified as charset unavailable")
	}
}

func TestMountOptionValue(t *testing.T) {
	if got := mountOptionValue("rw,iocharset=cp936,vers=3.0", "iocharset"); got != "cp936" {
		t.Fatalf("mountOptionValue() = %q, want cp936", got)
	}
}

func TestMountRunErrorMessagePrefersStderr(t *testing.T) {
	res := process.Result{Stdout: "stdout", Stderr: "stderr", ExitCode: 79}
	if got := mountRunErrorMessage(res, errExitForTest{}); got != "stderr" {
		t.Fatalf("mountRunErrorMessage() = %q", got)
	}
}

func TestSMBMountOptionsCredentialsFileForCommaPassword(t *testing.T) {
	spec := Spec{
		Username: "backupuser",
		Password: "pass,word",
	}
	if !smbNeedsCredentialsFile(spec) {
		t.Fatal("expected credentials file for comma in password")
	}
	opts, cleanup, err := smbMountOptions(spec)
	defer cleanup()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	joined := strings.Join(opts, ",")
	if !strings.Contains(joined, "credentials=") {
		t.Fatalf("expected credentials file, got %q", joined)
	}
}

func TestEscapeSMBMountOption(t *testing.T) {
	if got := escapeSMBMountOption(`a,b`); got != `a\054b` {
		t.Fatalf("unexpected escape: %q", got)
	}
}

func TestMergeMountOptionsOverridesDefaults(t *testing.T) {
	opts := mergeMountOptions([]string{"rw", "username=user"}, "rw,uid=1000")
	joined := strings.Join(opts, ",")
	if strings.Count(joined, "rw") != 1 {
		t.Fatalf("expected single rw, got %q", joined)
	}
	if !strings.Contains(joined, "uid=1000") {
		t.Fatalf("missing uid in %q", joined)
	}
}

type errExitForTest struct{}

func (errExitForTest) Error() string {
	return "exit 32"
}

//go:build !windows

package install

import (
	"slices"
	"testing"
)

func TestShellSingleQuote(t *testing.T) {
	got := shellSingleQuote("/var/lib/hyperfilelens-agent/lifecycle/upgrade/run-upgrade.sh")
	want := "'/var/lib/hyperfilelens-agent/lifecycle/upgrade/run-upgrade.sh'"
	if got != want {
		t.Fatalf("shellSingleQuote() = %q, want %q", got, want)
	}
	got = shellSingleQuote("/tmp/it's fine.sh")
	want = "'/tmp/it'\\''s fine.sh'"
	if got != want {
		t.Fatalf("shellSingleQuote(escaped) = %q, want %q", got, want)
	}
}

func TestSystemdRunArgsAreCentOS7Compatible(t *testing.T) {
	args := systemdRunArgs("hfl-agent-upgrade-123", "/tmp/run-upgrade.sh")
	if slices.Contains(args, "--collect") {
		t.Fatal("systemd-run arguments must not use --collect; CentOS 7 systemd 219 does not support it")
	}
	if slices.Contains(args, "--property=Type=oneshot") {
		t.Fatal("systemd-run arguments must not set Type=oneshot; CentOS 7 systemd-run rejects it")
	}
	want := []string{
		"--unit=hfl-agent-upgrade-123",
		"--property=KillMode=process",
		"/bin/bash", "/tmp/run-upgrade.sh",
	}
	if !slices.Equal(args, want) {
		t.Fatalf("systemdRunArgs() = %q, want %q", args, want)
	}
}

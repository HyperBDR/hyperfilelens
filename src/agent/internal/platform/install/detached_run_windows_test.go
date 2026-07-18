//go:build windows

package install

import "testing"

func TestPsSingleQuote(t *testing.T) {
	got := psSingleQuote(`C:\ProgramData\HyperFileLens\Agent\lifecycle\upgrade\run-upgrade.ps1`)
	want := `'C:\ProgramData\HyperFileLens\Agent\lifecycle\upgrade\run-upgrade.ps1'`
	if got != want {
		t.Fatalf("psSingleQuote() = %q, want %q", got, want)
	}
	got = psSingleQuote(`C:\it's\path.ps1`)
	want = `'C:\it''s\path.ps1'`
	if got != want {
		t.Fatalf("psSingleQuote(escaped) = %q, want %q", got, want)
	}
}

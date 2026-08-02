package cli

import "testing"

func TestVersionIsARealSubcommand(t *testing.T) {
	if !IsSubcommand("version") {
		t.Fatal("version must be dispatched as a short-lived CLI command")
	}
}

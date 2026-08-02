package main

import (
	"strings"
	"testing"
)

func TestRunDaemonRejectsUnexpectedPositionalArgument(t *testing.T) {
	err := runDaemon([]string{"version"})
	if err == nil || !strings.Contains(err.Error(), "unexpected daemon argument") {
		t.Fatalf("unexpected positional argument was not rejected: %v", err)
	}
}

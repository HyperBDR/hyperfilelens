package enroll

import (
	"errors"
	"os"
	"strings"
	"testing"
)

func TestPreflightFailuresAggregatesWithoutDiscardingFirstFailure(t *testing.T) {
	failures := &preflightFailures{}
	failures.add("First check failed", "first detail", 2)
	failures.add("Second check failed", "second detail", 3)

	err := failures.err()
	var failure InstallFailure
	if !errors.As(err, &failure) {
		t.Fatalf("error type = %T, want InstallFailure", err)
	}
	if failure.Stage != "Preflight checks" {
		t.Fatalf("stage = %q", failure.Stage)
	}
	if failure.CodeKey != "HFL-PREFLIGHT-002" {
		t.Fatalf("code = %q", failure.CodeKey)
	}
	if !strings.Contains(failure.Reason, "2 preflight checks failed") ||
		!strings.Contains(failure.Reason, "First check failed") {
		t.Fatalf("reason = %q", failure.Reason)
	}
}

func TestWritablePreflightDoesNotCreateProbeFiles(t *testing.T) {
	dir := t.TempDir()
	before, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := checkWritableTarget(dir); err != nil {
		t.Fatal(err)
	}
	after, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(before) != len(after) {
		t.Fatalf("directory entries changed from %d to %d", len(before), len(after))
	}
}

package main

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestIsBootstrapTempExecutable(t *testing.T) {
	tempDir := filepath.Clean(os.TempDir())

	if runtime.GOOS == "windows" {
		if !isBootstrapTempExecutable(filepath.Join(tempDir, "hfl-enroll-abc.exe")) {
			t.Fatal("expected windows bootstrap path to match")
		}
		if isBootstrapTempExecutable(filepath.Join(tempDir, "hfl-enroll-abc")) {
			t.Fatal("expected windows path without .exe to reject")
		}
	} else {
		if !isBootstrapTempExecutable(filepath.Join(tempDir, "hfl-enroll-12345")) {
			t.Fatal("expected unix bootstrap path to match")
		}
	}

	if isBootstrapTempExecutable(filepath.Join(t.TempDir(), "hfl-enroll-12345")) {
		t.Fatal("expected path outside os.TempDir() to reject")
	}
	if isBootstrapTempExecutable(filepath.Join(tempDir, "hfl-enroll")) {
		t.Fatal("expected exact name hfl-enroll to reject")
	}
}

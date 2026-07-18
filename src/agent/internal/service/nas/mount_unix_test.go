//go:build !windows

package nas

import (
	"fmt"
	"testing"

	"hyperfilelens/agent/internal/platform/process"
)

func TestIsBusyMountErrorDetectsCIFSError16(t *testing.T) {
	res := process.Result{Stderr: "mount error(16): Device or resource busy"}
	if !isBusyMountError(res, fmt.Errorf("exit 32")) {
		t.Fatal("expected CIFS error 16 to be treated as busy")
	}
}

func TestIsBusyMountErrorIgnoresPermissionDenied(t *testing.T) {
	res := process.Result{Stderr: "mount error(13): Permission denied"}
	if isBusyMountError(res, fmt.Errorf("exit 32")) {
		t.Fatal("did not expect permission denied to be treated as busy")
	}
}

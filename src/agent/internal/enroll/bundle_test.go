package enroll

import (
	"os/exec"
	"strings"
	"testing"
)

func TestRunStreamingCommandReturnsCapturedFailureDetail(t *testing.T) {
	t.Parallel()
	cmd := exec.Command("sh", "-c", "printf 'visible output\\n'; printf 'install detail\\n' >&2; exit 7")
	err := runStreamingCommand(cmd, "fixture install")
	if err == nil {
		t.Fatal("runStreamingCommand returned nil for a failing command")
	}
	if !strings.Contains(err.Error(), "install detail") {
		t.Fatalf("error %q does not contain captured stderr detail", err)
	}
}

func TestRunStreamingCommandReturnsSuccess(t *testing.T) {
	t.Parallel()
	cmd := exec.Command("sh", "-c", "printf 'streamed success\\n'")
	if err := runStreamingCommand(cmd, "fixture install"); err != nil {
		t.Fatalf("runStreamingCommand returned %v", err)
	}
}

package nas

import (
	"strings"
	"testing"
)

func TestRedactMountOptions(t *testing.T) {
	options := `vers=3.0,password=secret-value,username=backup`
	redacted := redactMountOptions(options)
	if strings.Contains(redacted, "secret-value") {
		t.Fatalf("mount options leaked password: %q", redacted)
	}
	if !strings.Contains(redacted, "password=***") {
		t.Fatalf("mount password was not redacted: %q", redacted)
	}
}

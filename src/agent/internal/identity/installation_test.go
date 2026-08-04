package identity

import (
	"strings"
	"testing"
)

func TestNewInstallationIDIsRandomAndWellFormed(t *testing.T) {
	t.Parallel()
	first, err := NewInstallationID()
	if err != nil {
		t.Fatal(err)
	}
	second, err := NewInstallationID()
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatalf("installation IDs must be unique: %q", first)
	}
	for _, value := range []string{first, second} {
		if len(value) != 45 || !strings.HasPrefix(value, "hfli_") {
			t.Fatalf("invalid installation ID %q", value)
		}
	}
}

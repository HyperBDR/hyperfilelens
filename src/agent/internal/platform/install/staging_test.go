package install

import "testing"

func TestStagedPackageFilename(t *testing.T) {
	tests := map[string]string{
		"/tmp/hfl-agent-bundle-1/package.tar.gz": "package.tar.gz",
		"/tmp/package.tar.gz":                    "package.tar.gz",
		"C:\\pending\\package.zip":               "package.zip",
		"/tmp/package.zip":                       "package.zip",
	}
	for input, want := range tests {
		if got := stagedPackageFilename(input); got != want {
			t.Fatalf("stagedPackageFilename(%q) = %q, want %q", input, got, want)
		}
	}
}

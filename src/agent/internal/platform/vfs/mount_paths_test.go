package vfs

import "testing"

func TestRepositoryMountPoint(t *testing.T) {
	got := RepositoryMountPoint(UnixDataDir(), 42, 3)
	want := "/var/lib/hyperfilelens-agent/mounts/repositories/repo-42-node-3"
	if got != want {
		t.Fatalf("RepositoryMountPoint() = %q want %q", got, want)
	}
}

func TestSourceMountPoint(t *testing.T) {
	got := SourceMountPoint(UnixDataDir(), 12)
	want := "/var/lib/hyperfilelens-agent/mounts/sources/source-12"
	if got != want {
		t.Fatalf("SourceMountPoint() = %q want %q", got, want)
	}
}

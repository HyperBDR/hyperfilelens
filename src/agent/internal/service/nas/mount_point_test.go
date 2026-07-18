package nas

import (
	"path/filepath"
	"testing"

	"hyperfilelens/agent/internal/platform/vfs"
)

func TestResolveMountPointRepository(t *testing.T) {
	t.Setenv("HFL_DATA_DIR", t.TempDir())
	dataDir := agentDataDirForMounts()
	got := ResolvedMountPoint(vfs.RepositoryMountPoint(vfs.UnixDataDir(), 9, 3))
	want := vfs.RepositoryMountPoint(dataDir, 9, 3)
	if got != want {
		t.Fatalf("ResolvedMountPoint() = %q want %q", got, want)
	}
}

func TestResolveMountPointSource(t *testing.T) {
	t.Setenv("HFL_DATA_DIR", t.TempDir())
	dataDir := agentDataDirForMounts()
	got := ResolvedMountPoint(vfs.SourceMountPoint(vfs.UnixDataDir(), 12))
	want := vfs.SourceMountPoint(dataDir, 12)
	if got != want {
		t.Fatalf("ResolvedMountPoint() = %q want %q", got, want)
	}
}

func TestResolveMountPointRewritesDefaultUnixDataDir(t *testing.T) {
	t.Setenv("HFL_DATA_DIR", t.TempDir())
	dataDir := agentDataDirForMounts()
	input := filepath.Join(vfs.UnixDataDir(), "mounts", "custom", "nas-data")
	got := ResolvedMountPoint(input)
	want := filepath.Join(dataDir, "mounts", "custom", "nas-data")
	if got != want {
		t.Fatalf("ResolvedMountPoint() = %q want %q", got, want)
	}
}

func TestResolveMountPointRejectsOutsideMounts(t *testing.T) {
	if got := ResolvedMountPoint("/mnt/nas/data"); got != "" {
		t.Fatalf("ResolvedMountPoint() = %q want empty", got)
	}
	if got := ResolvedMountPoint(`D:\backups\repo`); got != "" {
		t.Fatalf("ResolvedMountPoint() = %q want empty", got)
	}
}

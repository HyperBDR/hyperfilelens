//go:build linux

package enroll

import "golang.org/x/sys/unix"

func readOnlyWritableAccess(path string) (bool, error) {
	var filesystem unix.Statfs_t
	if err := unix.Statfs(path, &filesystem); err != nil {
		return false, err
	}
	if filesystem.Flags&unix.ST_RDONLY != 0 {
		return false, unix.EROFS
	}
	if err := unix.Access(path, unix.W_OK); err != nil {
		return false, err
	}
	return true, nil
}

//go:build !windows

package disk

import "syscall"

// Usage returns total/used/free bytes for the filesystem containing path.
func Usage(path string) (total, used, free uint64, err error) {
	var stat syscall.Statfs_t
	if err = syscall.Statfs(path, &stat); err != nil {
		return 0, 0, 0, err
	}
	bsize := uint64(stat.Bsize)
	total = stat.Blocks * bsize
	free = stat.Bavail * bsize
	if total >= free {
		used = total - free
	}
	return total, used, free, nil
}

//go:build linux

package enroll

import (
	"io"
	"os"
	"strings"

	"golang.org/x/sys/unix"
)

func packageManagerLockDetail() string {
	busy := []string{}
	for _, path := range []string{
		"/var/lib/dpkg/lock-frontend",
		"/var/lib/dpkg/lock",
		"/var/cache/apt/archives/lock",
		"/var/lib/apt/lists/lock",
	} {
		file, err := os.Open(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			continue
		}
		lock := unix.Flock_t{
			Type:   unix.F_WRLCK,
			Whence: int16(io.SeekStart),
			Start:  0,
			Len:    0,
		}
		if err := unix.FcntlFlock(file.Fd(), unix.F_GETLK, &lock); err == nil &&
			lock.Type != unix.F_UNLCK {
			busy = append(busy, path)
		}
		_ = file.Close()
	}
	return strings.Join(busy, ", ")
}

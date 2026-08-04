//go:build darwin

package enroll

import (
	"context"
	"errors"
	"os"

	"golang.org/x/sys/unix"
)

const fullInstallLockPath = "/var/run/hyperfilelens-install.lock"

func acquireInstallLock(_ context.Context) (func(), error) {
	file, err := os.OpenFile(fullInstallLockPath, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return nil, err
	}
	if err := unix.Flock(int(file.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		_ = file.Close()
		if errors.Is(err, unix.EWOULDBLOCK) || errors.Is(err, unix.EAGAIN) {
			return nil, ErrInstallLocked
		}
		return nil, err
	}
	return func() {
		_ = unix.Flock(int(file.Fd()), unix.LOCK_UN)
		_ = file.Close()
	}, nil
}

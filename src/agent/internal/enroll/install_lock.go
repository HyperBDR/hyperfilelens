package enroll

import (
	"context"
	"errors"
)

// ErrInstallLocked indicates another full installation is already running.
var ErrInstallLocked = errors.New("another HyperFileLens installation is already running")

// WithInstallLock runs one complete install flow under a host-wide nonblocking lock.
func WithInstallLock(ctx context.Context, action func() error) error {
	return RunCommand(func() error {
		release, err := acquireInstallLock(ctx)
		if err != nil {
			return err
		}
		defer release()
		return action()
	})
}

// RunCommand converts typed installer aborts into returned errors.
func RunCommand(action func() error) (err error) {
	defer RecoverInstallFailure(&err)
	return action()
}

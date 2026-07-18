//go:build !windows

package engine

import "syscall"

func acquireRepositoryFileLock(configFile string) (func(), error) {
	file, err := openRepositoryLockFile(configFile)
	if err != nil {
		return func() {}, err
	}
	if err := syscall.Flock(int(file.Fd()), syscall.LOCK_EX); err != nil {
		_ = file.Close()
		return func() {}, err
	}
	return func() {
		_ = syscall.Flock(int(file.Fd()), syscall.LOCK_UN)
		_ = file.Close()
	}, nil
}

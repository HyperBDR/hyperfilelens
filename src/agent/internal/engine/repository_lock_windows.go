//go:build windows

package engine

func acquireRepositoryFileLock(configFile string) (func(), error) {
	file, err := openRepositoryLockFile(configFile)
	if err != nil {
		return func() {}, err
	}
	return func() {
		_ = file.Close()
	}, nil
}

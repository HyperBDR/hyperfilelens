package engine

import (
	"context"
	"os"
	"path/filepath"
	"sync"
)

var repositoryPrepareLocks sync.Map

func withRepositoryPrepareLock(ctx context.Context, configFile string, fn func() (string, map[string]string, map[string]any, repositorySpec, string)) (string, map[string]string, map[string]any, repositorySpec, string) {
	if err := ctx.Err(); err != nil {
		return "", nil, nil, repositorySpec{}, err.Error()
	}
	key := filepath.Clean(configFile)
	lockValue, _ := repositoryPrepareLocks.LoadOrStore(key, &sync.Mutex{})
	mu := lockValue.(*sync.Mutex)
	mu.Lock()
	defer mu.Unlock()
	if err := ctx.Err(); err != nil {
		return "", nil, nil, repositorySpec{}, err.Error()
	}
	unlock, err := acquireRepositoryFileLock(configFile)
	if err != nil {
		return "", nil, nil, repositorySpec{}, err.Error()
	}
	defer unlock()
	return fn()
}

func repositoryLockFile(configFile string) string {
	return configFile + ".lock"
}

func openRepositoryLockFile(configFile string) (*os.File, error) {
	lockPath := repositoryLockFile(configFile)
	if err := os.MkdirAll(filepath.Dir(lockPath), 0o700); err != nil {
		return nil, err
	}
	return os.OpenFile(lockPath, os.O_CREATE|os.O_RDWR, 0o600)
}

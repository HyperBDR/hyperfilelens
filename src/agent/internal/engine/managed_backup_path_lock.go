package engine

import (
	"context"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
)

type managedBackupPathLockEntry struct {
	token chan struct{}
	refs  int
}

type managedBackupPathLockRegistry struct {
	mu      sync.Mutex
	entries map[string]*managedBackupPathLockEntry
}

var managedBackupPathLocks = newManagedBackupPathLockRegistry()

func newManagedBackupPathLockRegistry() *managedBackupPathLockRegistry {
	return &managedBackupPathLockRegistry{entries: make(map[string]*managedBackupPathLockEntry)}
}

func managedBackupPathLockKey(configFile string, sourcePath string) string {
	configKey := filepath.Clean(configFile)
	pathKey := filepath.Clean(sourcePath)
	if runtime.GOOS == "windows" {
		configKey = strings.ToLower(configKey)
		pathKey = strings.ToLower(pathKey)
	}
	return configKey + "\x00" + pathKey
}

func (r *managedBackupPathLockRegistry) acquire(
	ctx context.Context,
	configFile string,
	sourcePath string,
) (func(), error) {
	key := managedBackupPathLockKey(configFile, sourcePath)
	r.mu.Lock()
	entry := r.entries[key]
	if entry == nil {
		entry = &managedBackupPathLockEntry{token: make(chan struct{}, 1)}
		entry.token <- struct{}{}
		r.entries[key] = entry
	}
	entry.refs++
	r.mu.Unlock()

	select {
	case <-ctx.Done():
		r.dropReference(key, entry)
		return nil, ctx.Err()
	case <-entry.token:
	}

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.token <- struct{}{}
			r.dropReference(key, entry)
		})
	}, nil
}

func (r *managedBackupPathLockRegistry) dropReference(key string, entry *managedBackupPathLockEntry) {
	r.mu.Lock()
	defer r.mu.Unlock()
	entry.refs--
	if entry.refs == 0 && r.entries[key] == entry {
		delete(r.entries, key)
	}
}

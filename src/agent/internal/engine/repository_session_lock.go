package engine

import (
	"context"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
)

// repositorySessionLock serializes policy writers while allowing prepared
// snapshots for the same repository session to upload concurrently.
type repositorySessionLock struct {
	mu             sync.Mutex
	readers        int
	writer         bool
	waitingWriters int
	changed        chan struct{}
}

var repositorySessionLocks sync.Map

func newRepositorySessionLock() *repositorySessionLock {
	return &repositorySessionLock{changed: make(chan struct{})}
}

func managedRepositorySessionLockKey(spec repositorySpec, configFile string) string {
	var key string
	if spec.ID > 0 {
		key = spec.Type + "\x00" + strconv.FormatInt(spec.ID, 10)
		if spec.Type == "kopia_server" && strings.TrimSpace(spec.SessionID) != "" {
			key += "\x00" + strings.TrimSpace(spec.SessionID)
		}
	} else {
		key = filepath.Clean(configFile)
	}
	if runtime.GOOS == "windows" {
		key = strings.ToLower(key)
	}
	return key
}

func repositorySessionLockFor(spec repositorySpec, configFile string) *repositorySessionLock {
	key := managedRepositorySessionLockKey(spec, configFile)
	value, _ := repositorySessionLocks.LoadOrStore(key, newRepositorySessionLock())
	return value.(*repositorySessionLock)
}

func (l *repositorySessionLock) notifyLocked() {
	close(l.changed)
	l.changed = make(chan struct{})
}

func (l *repositorySessionLock) acquireRead(ctx context.Context) (func(), error) {
	for {
		l.mu.Lock()
		if !l.writer && l.waitingWriters == 0 {
			l.readers++
			l.mu.Unlock()
			var once sync.Once
			return func() {
				once.Do(func() {
					l.mu.Lock()
					l.readers--
					l.notifyLocked()
					l.mu.Unlock()
				})
			}, nil
		}
		changed := l.changed
		l.mu.Unlock()
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-changed:
		}
	}
}

func (l *repositorySessionLock) acquireWrite(ctx context.Context) (func(), error) {
	l.mu.Lock()
	l.waitingWriters++
	l.mu.Unlock()
	waiting := true
	defer func() {
		if !waiting {
			return
		}
		l.mu.Lock()
		l.waitingWriters--
		l.notifyLocked()
		l.mu.Unlock()
	}()

	for {
		l.mu.Lock()
		if !l.writer && l.readers == 0 {
			l.waitingWriters--
			l.writer = true
			waiting = false
			l.mu.Unlock()
			var once sync.Once
			return func() {
				once.Do(func() {
					l.mu.Lock()
					l.writer = false
					l.notifyLocked()
					l.mu.Unlock()
				})
			}, nil
		}
		changed := l.changed
		l.mu.Unlock()
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-changed:
		}
	}
}

package logging

import (
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"

	"gopkg.in/natefinch/lumberjack.v2"
)

const (
	maxLogSizeMB  = 100
	maxLogBackups = 4 // 4 rotated + active agent.log → 5 files max, 100MB each (~500MB cap)
	logFileName   = "agent.log"
)

// stderrWriter mirrors logs to stderr when available. Windows services often have
// no stderr sink; failures there must not block agent.log writes.
type stderrWriter struct{}

func (stderrWriter) Write(p []byte) (int, error) {
	n, err := os.Stderr.Write(p)
	if err != nil {
		return len(p), nil
	}
	return n, err
}

// Setup configures the default slog logger with the unified text format.
func Setup(logDir string, orgKey string) error {
	defaultOrgKey = orgKey
	hostPID = hostnamePID()

	if err := os.MkdirAll(logDir, 0o755); err != nil {
		return err
	}
	logPath := filepath.Join(logDir, logFileName)
	if err := touchLogFile(logPath); err != nil {
		return err
	}
	lj := &lumberjack.Logger{
		Filename:   logPath,
		MaxSize:    maxLogSizeMB,
		MaxBackups: maxLogBackups,
		LocalTime:  false,
		Compress:   false,
	}
	mw := io.MultiWriter(lj, stderrWriter{})
	h := newUnifiedHandler(mw, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	slog.SetDefault(slog.New(h))
	return nil
}

func touchLogFile(path string) error {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	return f.Close()
}

func hostnamePID() string {
	host, err := os.Hostname()
	if err != nil || host == "" {
		host = "unknown"
	}
	return host + ":" + strconv.Itoa(os.Getpid())
}

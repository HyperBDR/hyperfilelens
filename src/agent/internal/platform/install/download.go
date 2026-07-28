package install

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sync/atomic"
	"time"
)

const defaultDownloadProgressInterval = time.Second

// DownloadProgress describes one safe, URL-free transfer progress snapshot.
type DownloadProgress struct {
	DownloadedBytes int64
	TotalBytes      int64
	Elapsed         time.Duration
	BytesPerSecond  float64
	Completed       bool
}

// ProgressReporter receives rate-limited download progress snapshots.
type ProgressReporter func(DownloadProgress)

// DownloadURL streams url into destPath without interactive progress output.
func DownloadURL(ctx context.Context, rawURL, destPath string) error {
	return DownloadURLWithProgress(ctx, rawURL, destPath, nil)
}

// DownloadURLWithProgress safely downloads one file and reports transfer progress.
func DownloadURLWithProgress(
	ctx context.Context,
	rawURL string,
	destPath string,
	reporter ProgressReporter,
) error {
	return downloadURLWithInterval(
		ctx,
		rawURL,
		destPath,
		reporter,
		defaultDownloadProgressInterval,
	)
}

func downloadURLWithInterval(
	ctx context.Context,
	rawURL string,
	destPath string,
	reporter ProgressReporter,
	interval time.Duration,
) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return fmt.Errorf("create download request: %w", sanitizeDownloadError(err))
	}
	client := &http.Client{Timeout: 30 * time.Minute}
	if os.Getenv("HFL_INSECURE_TLS") != "0" {
		client.Transport = insecureTransport()
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("download request failed: %w", sanitizeDownloadError(err))
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("download HTTP %s", resp.Status)
	}
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return err
	}

	partPath := destPath + ".part"
	if err := os.Remove(partPath); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove stale partial download: %w", err)
	}
	file, err := os.OpenFile(partPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	completed := false
	defer func() {
		_ = file.Close()
		if !completed {
			_ = os.Remove(partPath)
		}
	}()

	started := time.Now()
	var downloaded atomic.Int64
	stopProgress := startDownloadProgress(
		reporter,
		&downloaded,
		resp.ContentLength,
		started,
		interval,
	)
	written, copyErr := io.Copy(file, io.TeeReader(resp.Body, byteCounter{value: &downloaded}))
	stopProgress(false)
	if copyErr != nil {
		return fmt.Errorf("download stream failed: %w", sanitizeDownloadError(copyErr))
	}
	if resp.ContentLength >= 0 && written != resp.ContentLength {
		return fmt.Errorf(
			"download size mismatch: received %d bytes, expected %d",
			written,
			resp.ContentLength,
		)
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Rename(partPath, destPath); err != nil {
		return err
	}
	completed = true
	stopProgress(true)
	return nil
}

type byteCounter struct {
	value *atomic.Int64
}

func (counter byteCounter) Write(p []byte) (int, error) {
	counter.value.Add(int64(len(p)))
	return len(p), nil
}

func startDownloadProgress(
	reporter ProgressReporter,
	downloaded *atomic.Int64,
	total int64,
	started time.Time,
	interval time.Duration,
) func(completed bool) {
	if reporter == nil {
		return func(bool) {}
	}
	if interval <= 0 {
		interval = defaultDownloadProgressInterval
	}
	done := make(chan struct{})
	stopped := make(chan struct{})
	go func() {
		defer close(stopped)
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		lastBytes := int64(0)
		lastAt := started
		for {
			select {
			case now := <-ticker.C:
				current := downloaded.Load()
				seconds := now.Sub(lastAt).Seconds()
				rate := float64(0)
				if seconds > 0 {
					rate = float64(current-lastBytes) / seconds
				}
				reporter(DownloadProgress{
					DownloadedBytes: current,
					TotalBytes:      total,
					Elapsed:         now.Sub(started),
					BytesPerSecond:  rate,
				})
				lastBytes = current
				lastAt = now
			case <-done:
				return
			}
		}
	}()
	var stoppedOnce atomic.Bool
	return func(completed bool) {
		if stoppedOnce.CompareAndSwap(false, true) {
			close(done)
			<-stopped
		}
		if !completed {
			return
		}
		elapsed := time.Since(started)
		current := downloaded.Load()
		rate := float64(0)
		if elapsed > 0 {
			rate = float64(current) / elapsed.Seconds()
		}
		reporter(DownloadProgress{
			DownloadedBytes: current,
			TotalBytes:      total,
			Elapsed:         elapsed,
			BytesPerSecond:  rate,
			Completed:       true,
		})
	}
}

func sanitizeDownloadError(err error) error {
	var urlErr *url.Error
	if errors.As(err, &urlErr) && urlErr.Err != nil {
		return urlErr.Err
	}
	return err
}

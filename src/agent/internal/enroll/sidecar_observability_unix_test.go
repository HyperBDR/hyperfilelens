//go:build !windows

package enroll

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestWriteLensEnvFileAtAppliesPlatformPolicyIdempotently(t *testing.T) {
	path := filepath.Join(t.TempDir(), "lensnode.env")
	lens := LensSidecarConfig{
		LensBaseURL:   "https://lens.example.com",
		LensnodeUUID:  "26d1822b-3ccc-48f8-80f1-f4c0ae99e61e",
		LensnodeToken: "lens-token",
		LensnodeName:  "platform-lens",
		WorkspaceRoot: "/workspace",
		Observability: platformObservabilityPolicy(),
	}

	changed, fingerprint, err := writeLensEnvFileAt(path, lens)
	if err != nil {
		t.Fatal(err)
	}
	if !changed {
		t.Fatal("first write changed = false, want true")
	}
	if fingerprint == "" {
		t.Fatal("first write returned an empty fingerprint")
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(content)
	for _, expected := range []string{
		"SENTRY_ENABLED=true",
		"SENTRY_BACKEND_DSN=https://public@sentry.example.com/25",
		"SENTRY_ENVIRONMENT=hfl-test",
		"HFL_SENTRY_LENSNODE_RELEASE=hyperfilelens-lensnode@main-123abcd-sl0.20.0",
	} {
		if !strings.Contains(text, expected+"\n") {
			t.Fatalf("lensnode.env missing %q:\n%s", expected, text)
		}
	}

	changed, secondFingerprint, err := writeLensEnvFileAt(path, lens)
	if err != nil {
		t.Fatal(err)
	}
	if changed {
		t.Fatal("second write changed = true, want false")
	}
	if secondFingerprint != fingerprint {
		t.Fatalf("fingerprint changed: %q != %q", secondFingerprint, fingerprint)
	}
}

func TestWriteLensEnvFileAtDisablesPrivateGateway(t *testing.T) {
	path := filepath.Join(t.TempDir(), "lensnode.env")
	lens := LensSidecarConfig{
		LensBaseURL:   "https://lens.example.com",
		LensnodeUUID:  "26d1822b-3ccc-48f8-80f1-f4c0ae99e61e",
		LensnodeToken: "lens-token",
		WorkspaceRoot: "/workspace",
	}

	if _, _, err := writeLensEnvFileAt(path, lens); err != nil {
		t.Fatal(err)
	}
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(content)
	if !strings.Contains(text, "SENTRY_ENABLED=false\n") {
		t.Fatalf("private lensnode.env did not disable Sentry:\n%s", text)
	}
	if strings.Contains(text, "SENTRY_BACKEND_DSN=") {
		t.Fatalf("private lensnode.env contains a DSN field:\n%s", text)
	}
}

func TestLensObservabilityRetriesFailedApply(t *testing.T) {
	root := t.TempDir()
	attempts := 0
	runtime := lensSidecarRuntime{
		envPath:     filepath.Join(root, "lensnode.env"),
		appliedPath: filepath.Join(root, "state", "applied.sha256"),
		lockPath:    filepath.Join(root, "sidecar.lock"),
		healthy:     func() bool { return true },
		ensureImage: func(context.Context, Config) error { return nil },
		installSidecar: func(context.Context, Config) error {
			attempts++
			if attempts == 1 {
				return errors.New("simulated compose failure")
			}
			return nil
		},
	}
	lens := LensSidecarConfig{
		LensBaseURL:   "https://lens.example.com",
		LensnodeUUID:  "26d1822b-3ccc-48f8-80f1-f4c0ae99e61e",
		LensnodeToken: "lens-token",
		WorkspaceRoot: "/workspace",
		Observability: platformObservabilityPolicy(),
	}

	if _, err := runtime.convergeObservability(context.Background(), Config{}, lens); err == nil {
		t.Fatal("first convergence unexpectedly succeeded")
	}
	if _, err := os.Stat(runtime.appliedPath); !os.IsNotExist(err) {
		t.Fatalf("failed apply recorded a fingerprint: %v", err)
	}
	changed, err := runtime.convergeObservability(context.Background(), Config{}, lens)
	if err != nil {
		t.Fatal(err)
	}
	if !changed || attempts != 2 {
		t.Fatalf("retry result changed=%v attempts=%d", changed, attempts)
	}
	changed, err = runtime.convergeObservability(context.Background(), Config{}, lens)
	if err != nil {
		t.Fatal(err)
	}
	if changed || attempts != 2 {
		t.Fatalf("idempotent result changed=%v attempts=%d", changed, attempts)
	}
}

func TestHealthyLensSidecarAppliesChangedConfiguration(t *testing.T) {
	root := t.TempDir()
	runs := 0
	runtime := lensSidecarRuntime{
		envPath:     filepath.Join(root, "lensnode.env"),
		appliedPath: filepath.Join(root, "state", "applied.sha256"),
		lockPath:    filepath.Join(root, "sidecar.lock"),
		healthy:     func() bool { return true },
		ensureImage: func(context.Context, Config) error { return nil },
		installSidecar: func(context.Context, Config) error {
			runs++
			return nil
		},
	}
	privateLens := LensSidecarConfig{
		LensBaseURL:   "https://lens.example.com",
		LensnodeUUID:  "26d1822b-3ccc-48f8-80f1-f4c0ae99e61e",
		LensnodeToken: "lens-token",
		WorkspaceRoot: "/workspace",
	}
	_, privateFingerprint, err := writeLensEnvFileAt(runtime.envPath, privateLens)
	if err != nil {
		t.Fatal(err)
	}
	if err := markLensConfigurationApplied(runtime.appliedPath, privateFingerprint); err != nil {
		t.Fatal(err)
	}

	platformLens := privateLens
	platformLens.Observability = platformObservabilityPolicy()
	if err := runtime.install(context.Background(), Config{}, platformLens); err != nil {
		t.Fatal(err)
	}
	if runs != 1 {
		t.Fatalf("changed configuration installer runs = %d, want 1", runs)
	}
	if err := runtime.install(context.Background(), Config{}, platformLens); err != nil {
		t.Fatal(err)
	}
	if runs != 1 {
		t.Fatalf("unchanged configuration installer runs = %d, want 1", runs)
	}
}

func TestFileLockSerializesAndHonorsContext(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sidecar.lock")
	locked := make(chan struct{})
	release := make(chan struct{})
	firstDone := make(chan error, 1)
	go func() {
		firstDone <- withFileLock(context.Background(), path, func() error {
			close(locked)
			<-release
			return nil
		})
	}()
	<-locked

	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	defer cancel()
	unexpectedRun := errors.New("second action ran while the first lock was held")
	err := withFileLock(ctx, path, func() error {
		return unexpectedRun
	})
	close(release)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("second lock error = %v, want deadline exceeded", err)
	}
	if err := <-firstDone; err != nil {
		t.Fatal(err)
	}
}

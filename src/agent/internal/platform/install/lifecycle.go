package install

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"hyperfilelens/agent/internal/platform/vfs"
)

// RunUpgrade runs the installed upgrade script against a release archive (requires root/admin).
func RunUpgrade(ctx context.Context, archivePath string) error {
	script, args := upgradeCommand(archivePath)
	cmd := exec.CommandContext(ctx, script, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s upgrade: %w", script, err)
	}
	return nil
}

// RunUninstall invokes bundled uninstall (keepData=false).
func RunUninstall(ctx context.Context, bundleDir string) error {
	script, args := uninstallCommand(bundleDir, false)
	cmd := exec.CommandContext(ctx, script, args...)
	cmd.Dir = bundleDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s uninstall: %w", script, err)
	}
	return nil
}

func upgradeCommand(archivePath string) (string, []string) {
	installDir := DefaultInstallDir()
	if runtime.GOOS == "windows" {
		return filepath.Join(installDir, "install.ps1"), []string{"upgrade", "-From", archivePath}
	}
	// Remote upgrade has no TTY; --yes allows same-version reinstall (warn + continue).
	return filepath.Join(installDir, "install.sh"), []string{"upgrade", "--from", archivePath, "--yes"}
}

func uninstallCommand(bundleDir string, keepData bool) (string, []string) {
	if runtime.GOOS == "windows" {
		args := []string{"uninstall"}
		if !keepData {
			args = append(args, "-PurgeAll")
		}
		return filepath.Join(bundleDir, "install.ps1"), args
	}
	args := []string{"uninstall"}
	if !keepData {
		args = append(args, "--purge-all")
	}
	return filepath.Join(bundleDir, "install.sh"), args
}

// DownloadURL streams url into destPath (TLS verify skipped unless HFL_INSECURE_TLS=0).
func DownloadURL(ctx context.Context, url, destPath string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	client := &http.Client{Timeout: 30 * time.Minute}
	if os.Getenv("HFL_INSECURE_TLS") != "0" {
		client.Transport = insecureTransport()
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("download HTTP %s", resp.Status)
	}
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return err
	}
	f, err := os.Create(destPath)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = io.Copy(f, resp.Body)
	return err
}

// ExtractArchive unpacks tar.gz (Unix) or zip (Windows) into destDir.
func ExtractArchive(ctx context.Context, archivePath, destDir string) error {
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return err
	}
	switch {
	case strings.HasSuffix(strings.ToLower(archivePath), ".zip"):
		return extractZip(ctx, archivePath, destDir)
	default:
		return extractTarGz(ctx, archivePath, destDir)
	}
}

func extractTarGz(ctx context.Context, archivePath, destDir string) error {
	cmd := exec.CommandContext(ctx, "tar", "xzf", archivePath, "-C", destDir)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("tar: %w (%s)", err, strings.TrimSpace(string(out)))
	}
	return nil
}

func extractZip(ctx context.Context, archivePath, destDir string) error {
	script := fmt.Sprintf(
		"Expand-Archive -LiteralPath %q -DestinationPath %q -Force",
		archivePath,
		destDir,
	)
	cmd := exec.CommandContext(ctx, "powershell", "-NoProfile", "-Command", script)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("Expand-Archive: %w (%s)", err, strings.TrimSpace(string(out)))
	}
	return nil
}

// FindBundleRoot returns the single top-level hfl-agent-* directory inside workDir.
func FindBundleRoot(workDir string) (string, error) {
	entries, err := os.ReadDir(workDir)
	if err != nil {
		return "", err
	}
	for _, e := range entries {
		if !e.IsDir() || !strings.HasPrefix(e.Name(), "hfl-agent-") {
			continue
		}
		root := filepath.Join(workDir, e.Name())
		if runtime.GOOS == "windows" {
			if _, err := os.Stat(filepath.Join(root, "install.ps1")); err == nil {
				return root, nil
			}
		} else if _, err := os.Stat(filepath.Join(root, "install.sh")); err == nil {
			return root, nil
		}
	}
	return "", fmt.Errorf("bundle root not found under %s", workDir)
}

// DefaultInstallDir returns the platform install root for bundled scripts.
func DefaultInstallDir() string {
	return vfs.DefaultInstallDir()
}

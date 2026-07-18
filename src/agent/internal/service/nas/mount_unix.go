//go:build !windows

package nas

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"log/slog"

	"hyperfilelens/agent/internal/platform/process"
)

func isMounted(mountPoint string) bool {
	mountPoint = strings.TrimSpace(mountPoint)
	if mountPoint == "" {
		return false
	}
	res, err := process.Run(context.Background(), "mountpoint", []string{"-q", mountPoint}, nil, "")
	if err == nil && res.ExitCode == 0 {
		return true
	}
	data, readErr := os.ReadFile("/proc/mounts")
	if readErr != nil {
		return false
	}
	target := filepath.Clean(mountPoint)
	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		if filepath.Clean(fields[1]) == target {
			return true
		}
	}
	return false
}

func mountShare(ctx context.Context, spec Spec) error {
	LogSpec("mount_begin", spec)

	if err := os.MkdirAll(spec.MountPoint, 0o755); err != nil {
		LogSpec("mount_failed", spec, "stage", "mkdir_mount_point", "err", err.Error())
		return fmt.Errorf("create mount point: %w", err)
	}
	if isMounted(spec.MountPoint) {
		LogSpec("mount_skip_already_mounted", spec)
		return nil
	}
	var err error
	switch spec.Protocol {
	case "smb":
		err = mountSMB(ctx, spec)
	case "nfs":
		err = mountNFS(ctx, spec)
	default:
		err = fmt.Errorf("unsupported nas protocol %q", spec.Protocol)
	}
	if err != nil {
		LogSpec("mount_failed", spec, "err", err.Error())
		return err
	}
	LogSpec("mount_success", spec)
	return nil
}

func mountSMB(ctx context.Context, spec Spec) error {
	if err := ensureSMBMountHelper(ctx); err != nil {
		slog.Info("nas", "event", "mount_helper_missing", "protocol", "smb", "err", err.Error())
		return err
	}
	args, cleanup, err := formatSMBMountArgs(spec)
	if err != nil {
		return err
	}
	defer func() { cleanup() }()

	source := fmt.Sprintf("//%s/%s", spec.Server, strings.Trim(spec.Share, "/"))
	optsStr := ""
	if len(args) >= 2 && args[len(args)-2] == "-o" {
		optsStr = args[len(args)-1]
	}
	res, runErr := process.Run(ctx, "mount", args, nil, "")
	logMountCommand("smb", source, spec.MountPoint, optsStr, res.ExitCode, res.Stderr, runErr)
	if runErr != nil && shouldRetrySMBWithoutDefaultCharset(spec, optsStr, res, runErr) {
		primaryMsg := mountRunErrorMessage(res, runErr)
		cleanup()
		cleanup = func() {}
		slog.Info("nas", "event", "mount_retry_without_default_iocharset", "protocol", "smb", "source", source, "mount_point", spec.MountPoint)
		retryArgs, retryCleanup, retryErr := formatSMBMountArgsWithoutDefaultCharset(spec)
		if retryErr != nil {
			return retryErr
		}
		defer retryCleanup()
		retryOptsStr := ""
		if len(retryArgs) >= 2 && retryArgs[len(retryArgs)-2] == "-o" {
			retryOptsStr = retryArgs[len(retryArgs)-1]
		}
		retryRes, retryRunErr := process.Run(ctx, "mount", retryArgs, nil, "")
		logMountCommand("smb", source, spec.MountPoint, retryOptsStr, retryRes.ExitCode, retryRes.Stderr, retryRunErr)
		if retryRunErr == nil {
			return nil
		}
		return fmt.Errorf("mount SMB share: default iocharset=utf8 failed (%s); retry without default iocharset failed (%s)", primaryMsg, mountRunErrorMessage(retryRes, retryRunErr))
	}
	if runErr != nil {
		if isBusyMountError(res, runErr) {
			if isMounted(spec.MountPoint) {
				slog.Info("nas", "event", "mount_busy_already_mounted", "protocol", "smb", "source", source, "mount_point", spec.MountPoint)
				return nil
			}
			return fmt.Errorf("mount SMB share: mount point %s is busy but is not an active mount; unmount the stale path or choose another mount point (%s)", spec.MountPoint, mountRunErrorMessage(res, runErr))
		}
		return fmt.Errorf("mount SMB share: %s", mountRunErrorMessage(res, runErr))
	}
	return nil
}

func isBusyMountError(res process.Result, err error) bool {
	output := strings.ToLower(strings.Join([]string{
		res.Stdout,
		res.Stderr,
		fmt.Sprint(err),
	}, "\n"))
	return strings.Contains(output, "mount error(16)") ||
		strings.Contains(output, "device or resource busy") ||
		strings.Contains(output, "already mounted") ||
		strings.Contains(output, "is busy")
}

func shouldRetrySMBWithoutDefaultCharset(spec Spec, opts string, res process.Result, err error) bool {
	if mountOptionsContainKey(spec.Options, "iocharset") {
		return false
	}
	if !mountOptionsContainKeyValue(opts, "iocharset", "utf8") {
		return false
	}
	return smbMountDefaultCharsetUnavailable(res, err)
}

func smbMountDefaultCharsetUnavailable(res process.Result, err error) bool {
	output := strings.ToLower(strings.Join([]string{
		res.Stdout,
		res.Stderr,
		fmt.Sprint(err),
	}, "\n"))
	return strings.Contains(output, "mount error(79)") ||
		strings.Contains(output, "mount error(95)") ||
		strings.Contains(output, "needed shared library") ||
		strings.Contains(output, "unable to load nls charset") ||
		(strings.Contains(output, "iocharset") && strings.Contains(output, "utf8") && strings.Contains(output, "not found"))
}

func mountRunErrorMessage(res process.Result, err error) string {
	msg := strings.TrimSpace(res.Stderr)
	if msg == "" {
		msg = strings.TrimSpace(res.Stdout)
	}
	if msg == "" && err != nil {
		msg = err.Error()
	}
	if msg == "" {
		msg = fmt.Sprintf("exit code %d", res.ExitCode)
	}
	return msg
}

func ensureSMBMountHelper(ctx context.Context) error {
	helper := mountHelperPath("mount.cifs")
	if helper == "" {
		return fmt.Errorf("mount SMB share: cifs-utils is not installed on this proxy host (missing mount.cifs helper)")
	}
	res, err := process.Run(ctx, helper, []string{"--version"}, nil, "")
	if err == nil && res.ExitCode == 0 {
		return nil
	}
	msg := strings.TrimSpace(res.Stderr)
	if msg == "" {
		msg = strings.TrimSpace(res.Stdout)
	}
	if msg == "" && err != nil {
		msg = err.Error()
	}
	if msg == "" {
		msg = fmt.Sprintf("exit code %d", res.ExitCode)
	}
	return fmt.Errorf("mount SMB share: cifs-utils is installed but not usable on this proxy host (mount.cifs failed to start: %s)", msg)
}

func mountNFS(ctx context.Context, spec Spec) error {
	if err := ensureNFSMountHelper(); err != nil {
		slog.Info("nas", "event", "mount_helper_missing", "protocol", "nfs", "err", err.Error())
		return err
	}
	source := fmt.Sprintf("%s:%s", spec.Server, spec.ExportPath)
	args := []string{
		"-t", "nfs",
		source,
		spec.MountPoint,
	}
	opts := strings.TrimSpace(spec.Options)
	if opts != "" {
		args = append(args, "-o", opts)
	}
	res, runErr := process.Run(ctx, "mount", args, nil, "")
	logMountCommand("nfs", source, spec.MountPoint, opts, res.ExitCode, res.Stderr, runErr)
	if runErr != nil {
		msg := strings.TrimSpace(res.Stderr)
		if msg == "" {
			msg = runErr.Error()
		}
		return fmt.Errorf("mount NFS export: %s", msg)
	}
	return nil
}

func ensureNFSMountHelper() error {
	if mountHelperPath("mount.nfs") != "" {
		return nil
	}
	return fmt.Errorf("mount NFS export: nfs-common is not installed on this proxy host (missing mount.nfs helper)")
}

func mountHelperPath(name string) string {
	if path, err := exec.LookPath(name); err == nil {
		return path
	}
	for _, dir := range []string{"/sbin", "/usr/sbin"} {
		path := filepath.Join(dir, name)
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path
		}
	}
	return ""
}

func unmountShare(ctx context.Context, mountPoint string) error {
	res, runErr := process.Run(ctx, "umount", []string{mountPoint}, nil, "")
	if runErr != nil {
		msg := strings.TrimSpace(res.Stderr)
		if msg == "" {
			msg = runErr.Error()
		}
		return fmt.Errorf("unmount NAS share: %s", msg)
	}
	return nil
}

func writeSMBCredentials(spec Spec) (string, error) {
	file, err := os.CreateTemp("", "hfl-nas-cred-*")
	if err != nil {
		return "", fmt.Errorf("create credentials file: %w", err)
	}
	path := file.Name()
	lines := []string{
		"username=" + spec.Username,
		"password=" + spec.Password,
	}
	if spec.Domain != "" {
		lines = append(lines, "domain="+spec.Domain)
	}
	if _, err := file.WriteString(strings.Join(lines, "\n") + "\n"); err != nil {
		file.Close()
		os.Remove(path)
		return "", fmt.Errorf("write credentials file: %w", err)
	}
	if err := file.Chmod(0o600); err != nil {
		file.Close()
		os.Remove(path)
		return "", fmt.Errorf("secure credentials file: %w", err)
	}
	if err := file.Close(); err != nil {
		os.Remove(path)
		return "", fmt.Errorf("close credentials file: %w", err)
	}
	return path, nil
}

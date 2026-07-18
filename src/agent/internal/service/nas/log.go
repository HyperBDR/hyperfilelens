package nas

import (
	"log/slog"
	"regexp"
	"strings"
)

var mountOptionSecret = regexp.MustCompile(`(?i)(password=)([^,\\]+|\\[^,\\]*)`)

// LogSpec emits a NAS mount/browse diagnostic line without credentials.
func LogSpec(event string, spec Spec, extra ...any) {
	args := []any{
		"event", event,
		"protocol", spec.Protocol,
		"server", spec.Server,
		"mount_point", spec.MountPoint,
		"resource_id", spec.ResourceID,
	}
	if spec.Protocol == "smb" {
		args = append(args, "share", spec.Share, "username", spec.Username)
	} else {
		args = append(args, "export_path", spec.ExportPath)
	}
	if opts := strings.TrimSpace(spec.Options); opts != "" {
		args = append(args, "options", redactMountOptions(opts))
	}
	args = append(args, extra...)
	slog.Info("nas", args...)
}

func redactMountOptions(opts string) string {
	return mountOptionSecret.ReplaceAllString(opts, `${1}***`)
}

func logMountCommand(protocol, source, mountPoint, opts string, exitCode int, stderr string, err error) {
	args := []any{
		"event", "mount_command",
		"protocol", protocol,
		"source", source,
		"mount_point", mountPoint,
		"exit_code", exitCode,
	}
	if opts != "" {
		args = append(args, "options", redactMountOptions(opts))
	}
	if stderr != "" {
		args = append(args, "stderr", strings.TrimSpace(stderr))
	}
	if err != nil {
		args = append(args, "err", err.Error())
	}
	slog.Info("nas", args...)
}

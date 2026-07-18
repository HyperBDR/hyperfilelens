//go:build !windows

package nas

import (
	"fmt"
	"os"
	"strings"
)

// defaultSMBMountOptions enables UTF-8 filename decoding on Linux CIFS mounts so
// international paths (e.g. Spanish accents) are visible to Kopia and the explorer.
const defaultSMBMountOptions = "iocharset=utf8"

// smbMountOptions builds mount -o values for CIFS. Inline username/password is used by
// default because it matches the most compatible manual mount style on Ubuntu/cifs-utils;
// credentials= files are reserved for values that cannot be encoded in -o safely.
func smbMountOptions(spec Spec) (opts []string, cleanup func(), err error) {
	return smbMountOptionsForMount(spec, true)
}

func smbMountOptionsWithoutDefaultCharset(spec Spec) (opts []string, cleanup func(), err error) {
	return smbMountOptionsForMount(spec, false)
}

func smbMountOptionsForMount(spec Spec, includeDefaultCharset bool) (opts []string, cleanup func(), err error) {
	cleanup = func() {}
	opts = []string{"rw"}

	if smbNeedsCredentialsFile(spec) {
		path, writeErr := writeSMBCredentials(spec)
		if writeErr != nil {
			return nil, cleanup, writeErr
		}
		cleanup = func() { _ = os.Remove(path) }
		opts = append(opts, "credentials="+path)
	} else {
		opts = append(opts,
			"username="+escapeSMBMountOption(spec.Username),
			"password="+escapeSMBMountOption(spec.Password),
		)
		if spec.Domain != "" {
			opts = append(opts, "domain="+escapeSMBMountOption(spec.Domain))
		}
	}

	if includeDefaultCharset {
		opts = mergeMountOptions(opts, defaultSMBMountOptions)
	}
	opts = mergeMountOptions(opts, spec.Options)
	return opts, cleanup, nil
}

func smbNeedsCredentialsFile(spec Spec) bool {
	return smbOptionNeedsCredentialsFile(spec.Username) ||
		smbOptionNeedsCredentialsFile(spec.Password) ||
		(spec.Domain != "" && smbOptionNeedsCredentialsFile(spec.Domain))
}

func smbOptionNeedsCredentialsFile(value string) bool {
	return strings.ContainsAny(value, ",\\=\n\r")
}

// escapeSMBMountOption escapes characters that break mount.cifs comma-separated -o parsing.
// See mount.cifs(8): comma may be encoded as \054, backslash as \134.
func escapeSMBMountOption(value string) string {
	value = strings.ReplaceAll(value, `\`, `\134`)
	value = strings.ReplaceAll(value, `,`, `\054`)
	return value
}

func mergeMountOptions(base []string, extra string) []string {
	opts := append([]string(nil), base...)
	extra = strings.TrimSpace(extra)
	if extra == "" {
		return opts
	}
	for _, item := range strings.Split(extra, ",") {
		option := strings.TrimSpace(item)
		if option == "" {
			continue
		}
		key := optionKey(option)
		filtered := make([]string, 0, len(opts))
		for _, existing := range opts {
			if optionKey(existing) == key {
				continue
			}
			filtered = append(filtered, existing)
		}
		opts = filtered
		opts = append(opts, option)
	}
	return opts
}

func optionKey(option string) string {
	key := option
	if idx := strings.Index(option, "="); idx > 0 {
		key = option[:idx]
	}
	return strings.TrimSpace(key)
}

func mountOptionsContainKey(options string, key string) bool {
	key = strings.TrimSpace(strings.ToLower(key))
	for _, item := range strings.Split(options, ",") {
		if strings.ToLower(optionKey(item)) == key {
			return true
		}
	}
	return false
}

func mountOptionsContainKeyValue(options string, key string, value string) bool {
	key = strings.TrimSpace(strings.ToLower(key))
	value = strings.TrimSpace(strings.ToLower(value))
	for _, item := range strings.Split(options, ",") {
		option := strings.TrimSpace(item)
		if option == "" {
			continue
		}
		if strings.ToLower(optionKey(option)) != key {
			continue
		}
		idx := strings.Index(option, "=")
		if idx < 0 {
			return value == ""
		}
		if strings.TrimSpace(strings.ToLower(option[idx+1:])) == value {
			return true
		}
	}
	return false
}

func formatSMBMountArgs(spec Spec) (args []string, cleanup func(), err error) {
	opts, cleanup, err := smbMountOptions(spec)
	return formatSMBMountArgsWithOptions(spec, opts, cleanup, err)
}

func formatSMBMountArgsWithoutDefaultCharset(spec Spec) (args []string, cleanup func(), err error) {
	opts, cleanup, err := smbMountOptionsWithoutDefaultCharset(spec)
	return formatSMBMountArgsWithOptions(spec, opts, cleanup, err)
}

func formatSMBMountArgsWithOptions(spec Spec, opts []string, cleanup func(), err error) (args []string, cleanupOut func(), errOut error) {
	if err != nil {
		return nil, cleanup, err
	}
	source := fmt.Sprintf("//%s/%s", spec.Server, strings.Trim(spec.Share, "/"))
	args = []string{
		"-t", "cifs",
		source,
		spec.MountPoint,
		"-o", strings.Join(opts, ","),
	}
	return args, cleanup, nil
}

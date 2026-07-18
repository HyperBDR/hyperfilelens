package nas

import (
	"fmt"
	"strings"
)

// Spec describes a NAS share to mount on the local proxy/agent host.
type Spec struct {
	ResourceID int
	Protocol   string
	Server     string
	Share      string
	ExportPath string
	MountPoint string
	Options    string
	Username   string
	Password   string
	Domain     string
}

func ParseSpec(raw map[string]any) (Spec, error) {
	if raw == nil {
		return Spec{}, fmt.Errorf("nas payload is required")
	}
	spec := Spec{
		ResourceID: intValue(raw["resource_id"]),
		Protocol:   normalizeProtocol(stringValue(raw["protocol"])),
		Server:     strings.TrimSpace(stringValue(raw["server"])),
		MountPoint: strings.TrimSpace(stringValue(raw["mount_point"])),
		Options:    strings.TrimSpace(stringValue(raw["options"])),
		Share:      strings.Trim(strings.TrimSpace(stringValue(raw["share"])), "/"),
		ExportPath: strings.TrimSpace(stringValue(raw["export_path"])),
		Username:   strings.TrimSpace(stringValue(raw["username"])),
		Password:   stringValue(raw["password"]),
		Domain:     strings.TrimSpace(stringValue(raw["domain"])),
	}
	if spec.Protocol == "" {
		if spec.Share != "" {
			spec.Protocol = "smb"
		} else if spec.ExportPath != "" {
			spec.Protocol = "nfs"
		}
	}
	if spec.Server == "" {
		return Spec{}, fmt.Errorf("nas.server is required")
	}
	if spec.MountPoint == "" {
		return Spec{}, fmt.Errorf("nas.mount_point is required")
	}
	switch spec.Protocol {
	case "smb", "cifs":
		spec.Protocol = "smb"
		if spec.Share == "" {
			return Spec{}, fmt.Errorf("nas.share is required for SMB")
		}
		if spec.Username == "" || spec.Password == "" {
			return Spec{}, fmt.Errorf("nas.username and nas.password are required for SMB")
		}
	case "nfs":
		if spec.ExportPath == "" {
			return Spec{}, fmt.Errorf("nas.export_path is required for NFS")
		}
	default:
		return Spec{}, fmt.Errorf("unsupported nas protocol %q", spec.Protocol)
	}
	return spec, nil
}

func normalizeProtocol(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "smb", "cifs":
		return "smb"
	case "nfs":
		return "nfs"
	default:
		return strings.ToLower(strings.TrimSpace(value))
	}
}

func stringValue(raw any) string {
	if raw == nil {
		return ""
	}
	switch v := raw.(type) {
	case string:
		return v
	default:
		return fmt.Sprint(v)
	}
}

func intValue(raw any) int {
	switch v := raw.(type) {
	case int:
		return v
	case int64:
		return int(v)
	case float64:
		return int(v)
	case string:
		var out int
		if _, err := fmt.Sscanf(strings.TrimSpace(v), "%d", &out); err == nil {
			return out
		}
	}
	return 0
}

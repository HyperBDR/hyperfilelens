package remote

import (
	"context"
	"net"
	"os"
	"runtime"
	"strings"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/disk"
	"github.com/shirou/gopsutil/v4/mem"

	"hyperfilelens/agent/internal/infra/config"
	agentdisk "hyperfilelens/agent/internal/platform/disk"
	"hyperfilelens/agent/internal/platform/hostinfo"
	"hyperfilelens/agent/internal/platform/install"
	"hyperfilelens/agent/internal/platform/kopia"
	"hyperfilelens/agent/internal/platform/netmac"
	"hyperfilelens/agent/internal/platform/vfs"
	"hyperfilelens/agent/internal/selfupdate"
	"hyperfilelens/agent/internal/wire"
)

// SendInventory emits a heartbeat frame with host and bundle metadata for the control plane.
func SendInventory(ctx context.Context, sink wire.Sender, provider config.Provider) error {
	if sink == nil || provider == nil {
		return nil
	}
	cfg := provider.Current()
	platform := hostinfo.Collect(ctx)
	dataDir := cfg.DataDir
	if dataDir == "" {
		dataDir = vfs.DefaultAgentDataDir()
	}
	payload := platform.Inventory()
	for key, value := range map[string]any{
		"agent_version": selfupdate.Version,
		"agent_commit":  selfupdate.Commit,
		"role":          string(cfg.Role),
		"os":            runtime.GOOS,
		"arch":          runtime.GOARCH,
		"hostname":      hostname(),
		"kopia_path":    cfg.KopiaPath,
		"root_path":     dataDir,
		"install_path":  install.DefaultInstallDir(),
		"capabilities":  []string{"repository_operation_v1", "repository_cleanup_v1"},
	} {
		payload[key] = value
	}
	if mac := netmac.PrimaryMAC(); mac != "" {
		payload["mac_address"] = mac
	}
	if addresses := hostIPv4Addresses(); len(addresses) > 0 {
		payload["ip_addresses"] = addresses
		payload["primary_ip_address"] = addresses[0]
	}
	if total, used, free, count, err := agentdisk.HostStorageUsage(); err == nil && count > 0 {
		payload["disk_total_bytes"] = total
		payload["disk_used_bytes"] = used
		payload["disk_free_bytes"] = free
		payload["disk_count"] = count
	} else if total, used, free, err := agentdisk.Usage(dataDir); err == nil {
		payload["disk_total_bytes"] = total
		payload["disk_used_bytes"] = used
		payload["disk_free_bytes"] = free
		if parts, err := disk.Partitions(false); err == nil && len(parts) > 0 {
			payload["disk_count"] = len(parts)
		}
	}
	if logical, err := cpu.Counts(true); err == nil && logical > 0 {
		payload["cpu_cores"] = logical
	}
	if vm, err := mem.VirtualMemory(); err == nil && vm.Total > 0 {
		payload["memory_total_bytes"] = vm.Total
	}
	if bin := cfg.KopiaPath; bin != "" {
		if ver, err := kopia.Version(ctx, bin); err == nil {
			payload["kopia_version"] = ver
		} else {
			payload["kopia_error"] = err.Error()
		}
	}
	return sink.SendJSON(ctx, wire.NewHeartbeatWithPayload(payload))
}

func hostname() string {
	h, err := os.Hostname()
	if err != nil {
		return ""
	}
	return h
}

func hostIPv4Addresses() []string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return nil
	}
	seen := map[string]bool{}
	out := make([]string, 0)
	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		name := strings.ToLower(iface.Name)
		if strings.HasPrefix(name, "docker") ||
			strings.HasPrefix(name, "br-") ||
			strings.HasPrefix(name, "veth") ||
			strings.HasPrefix(name, "virbr") {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			ip := addressIP(addr)
			if ip == nil {
				continue
			}
			if ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsMulticast() || ip.IsUnspecified() {
				continue
			}
			value := ip.String()
			if !seen[value] {
				out = append(out, value)
				seen[value] = true
			}
		}
	}
	return out
}

func addressIP(addr net.Addr) net.IP {
	switch value := addr.(type) {
	case *net.IPNet:
		return value.IP.To4()
	case *net.IPAddr:
		return value.IP.To4()
	default:
		return nil
	}
}

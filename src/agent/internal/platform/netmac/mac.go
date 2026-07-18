package netmac

import (
	"net"
	"strings"

	psnet "github.com/shirou/gopsutil/v4/net"
)

// PrimaryMAC returns the best-effort hardware address of the primary host interface.
func PrimaryMAC() string {
	ifaces, err := psnet.Interfaces()
	if err != nil {
		return ""
	}
	bestMAC := ""
	bestScore := -1
	for _, iface := range ifaces {
		score, mac := scoreInterface(iface)
		if mac == "" || score < 0 {
			continue
		}
		if score > bestScore {
			bestScore = score
			bestMAC = mac
		}
	}
	return bestMAC
}

func scoreInterface(iface psnet.InterfaceStat) (int, string) {
	name := strings.ToLower(strings.TrimSpace(iface.Name))
	if isSkippedInterface(name) {
		return -1, ""
	}
	mac := formatMAC(iface.HardwareAddr)
	if mac == "" || isZeroMAC(mac) {
		return -1, ""
	}
	score := 0
	if flagEnabled(iface.Flags, "up") && !flagEnabled(iface.Flags, "loopback") {
		score += 10
	}
	if hasIPv4(iface.Addrs) {
		score += 20
	}
	switch {
	case strings.HasPrefix(name, "eth"),
		strings.HasPrefix(name, "en"),
		strings.HasPrefix(name, "wlan"),
		strings.HasPrefix(name, "wl"):
		score += 5
	case strings.Contains(name, "ethernet"):
		score += 5
	}
	return score, mac
}

func isSkippedInterface(name string) bool {
	if name == "" || name == "lo" || strings.HasPrefix(name, "lo") {
		return true
	}
	skipPrefixes := []string{
		"docker", "veth", "br-", "virbr", "vmnet", "vboxnet", "tun", "tap", "wg",
		"utun", "awdl", "llw", "bridge", "vethernet", "hyper-v",
	}
	for _, prefix := range skipPrefixes {
		if strings.HasPrefix(name, prefix) {
			return true
		}
	}
	return false
}

func flagEnabled(flags []string, want string) bool {
	want = strings.ToLower(want)
	for _, flag := range flags {
		if strings.EqualFold(strings.TrimSpace(flag), want) {
			return true
		}
	}
	return false
}

func hasIPv4(addrs []psnet.InterfaceAddr) bool {
	for _, addr := range addrs {
		ip := strings.TrimSpace(strings.Split(addr.Addr, "/")[0])
		if ip == "" {
			continue
		}
		parsed := net.ParseIP(ip)
		if parsed != nil && parsed.To4() != nil && !parsed.IsLoopback() && !parsed.IsLinkLocalUnicast() {
			return true
		}
	}
	return false
}

func formatMAC(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	hw, err := net.ParseMAC(raw)
	if err != nil || len(hw) == 0 {
		return ""
	}
	return strings.ToLower(hw.String())
}

func isZeroMAC(mac string) bool {
	return mac == "00:00:00:00:00:00"
}

// Package networkinventory collects a compact, bounded snapshot of host network interfaces.
package networkinventory

import (
	"context"
	"net"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	SchemaVersion         = 1
	MaxInterfaces         = 16
	MaxAddressesPerNIC    = 8
	MaxAddressesPerHost   = 32
	routeProbeTimeout     = 2 * time.Second
	SourceRouteToControl  = "route_to_control_plane"
	SourceInterfaceBackup = "interface_fallback"
)

// Address is one usable unicast address assigned to an interface.
type Address struct {
	Address      string `json:"address"`
	Family       string `json:"family"`
	PrefixLength int    `json:"prefix_length"`
}

// Interface is the compact current state required for host-address selection and future display.
type Interface struct {
	ID           string    `json:"id"`
	Name         string    `json:"name"`
	MACAddress   string    `json:"mac_address,omitempty"`
	Type         string    `json:"type"`
	Virtual      bool      `json:"virtual"`
	DefaultRoute bool      `json:"default_route"`
	Addresses    []Address `json:"addresses"`
}

// Selection explains the single host address exposed by the current UI.
type Selection struct {
	Address     string `json:"address"`
	Family      string `json:"family"`
	InterfaceID string `json:"interface_id"`
	Source      string `json:"source"`
}

// Snapshot is a bounded current network inventory. It intentionally contains no counters or history.
type Snapshot struct {
	SchemaVersion int         `json:"schema_version"`
	CollectedAt   string      `json:"collected_at"`
	Selection     Selection   `json:"selection"`
	Interfaces    []Interface `json:"interfaces"`
}

type interfaceInfo struct {
	index      int
	name       string
	macAddress string
	virtual    bool
	kind       string
	noise      bool
	selected   bool
	addresses  []Address
}

// Collect returns a normalized, bounded snapshot. Failures are best-effort and yield an empty snapshot.
func Collect(ctx context.Context, controlPlaneURL string) Snapshot {
	return CollectWithPreferredAddress(ctx, controlPlaneURL, "")
}

// CollectWithPreferredAddress uses an active control connection's local address when available.
func CollectWithPreferredAddress(
	ctx context.Context,
	controlPlaneURL string,
	preferredAddress string,
) Snapshot {
	infos := collectInterfaces()
	routeIP := net.ParseIP(strings.TrimSpace(preferredAddress))
	if !usableIP(routeIP) {
		routeIP = routeAddress(ctx, controlPlaneURL)
	}
	return buildSnapshot(infos, routeIP, time.Now().UTC())
}

// PrimaryAddress returns the selected host address.
func (s Snapshot) PrimaryAddress() string { return strings.TrimSpace(s.Selection.Address) }

// PrimaryMACAddress returns the MAC belonging to the selected address's interface.
func (s Snapshot) PrimaryMACAddress() string {
	for _, iface := range s.Interfaces {
		if iface.ID == s.Selection.InterfaceID {
			return iface.MACAddress
		}
	}
	return ""
}

// IPAddresses returns the bounded, de-duplicated usable address list with the primary first.
func (s Snapshot) IPAddresses() []string {
	seen := map[string]bool{}
	out := make([]string, 0, MaxAddressesPerHost)
	appendAddress := func(value string) {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] || len(out) >= MaxAddressesPerHost {
			return
		}
		seen[value] = true
		out = append(out, value)
	}
	appendAddress(s.PrimaryAddress())
	for _, iface := range s.Interfaces {
		for _, addr := range iface.Addresses {
			appendAddress(addr.Address)
		}
	}
	return out
}

func collectInterfaces() []interfaceInfo {
	interfaces, err := net.Interfaces()
	if err != nil {
		return nil
	}
	out := make([]interfaceInfo, 0, len(interfaces))
	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		addresses := normalizeAddresses(addrs)
		if len(addresses) == 0 {
			continue
		}
		kind, virtual, noise := classifyInterface(iface.Name)
		out = append(out, interfaceInfo{
			index:      iface.Index,
			name:       strings.TrimSpace(iface.Name),
			macAddress: normalizeMAC(iface.HardwareAddr),
			virtual:    virtual,
			kind:       kind,
			noise:      noise,
			addresses:  addresses,
		})
	}
	return out
}

func normalizeAddresses(addrs []net.Addr) []Address {
	seen := map[string]bool{}
	out := make([]Address, 0, len(addrs))
	for _, raw := range addrs {
		ip, prefix := addressParts(raw)
		if !usableIP(ip) {
			continue
		}
		value := ip.String()
		if seen[value] {
			continue
		}
		seen[value] = true
		family := "ipv6"
		if ip.To4() != nil {
			family = "ipv4"
		}
		out = append(out, Address{Address: value, Family: family, PrefixLength: prefix})
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Family != out[j].Family {
			return out[i].Family == "ipv4"
		}
		return out[i].Address < out[j].Address
	})
	return out
}

func addressParts(addr net.Addr) (net.IP, int) {
	switch value := addr.(type) {
	case *net.IPNet:
		prefix, _ := value.Mask.Size()
		return value.IP, prefix
	case *net.IPAddr:
		return value.IP, 0
	default:
		host := strings.TrimSpace(strings.Split(addr.String(), "/")[0])
		return net.ParseIP(host), 0
	}
}

func usableIP(ip net.IP) bool {
	return ip != nil &&
		!ip.IsLoopback() &&
		!ip.IsLinkLocalUnicast() &&
		!ip.IsMulticast() &&
		!ip.IsUnspecified()
}

func buildSnapshot(infos []interfaceInfo, routeIP net.IP, collectedAt time.Time) Snapshot {
	routeValue := ""
	if usableIP(routeIP) {
		routeValue = routeIP.String()
	}
	selectedInfo := -1
	selectedAddress := ""
	selectionSource := SourceInterfaceBackup
	for i := range infos {
		for _, addr := range infos[i].addresses {
			if routeValue != "" && addr.Address == routeValue {
				selectedInfo = i
				selectedAddress = addr.Address
				selectionSource = SourceRouteToControl
				break
			}
		}
		if selectedInfo >= 0 {
			break
		}
	}
	if selectedInfo >= 0 {
		infos[selectedInfo].selected = true
	}

	sort.SliceStable(infos, func(i, j int) bool {
		leftSelected := infos[i].selected
		rightSelected := infos[j].selected
		if leftSelected != rightSelected {
			return leftSelected
		}
		leftRank := interfaceRank(infos[i])
		rightRank := interfaceRank(infos[j])
		if leftRank != rightRank {
			return leftRank < rightRank
		}
		if infos[i].name != infos[j].name {
			return infos[i].name < infos[j].name
		}
		return infos[i].index < infos[j].index
	})

	interfaces := make([]Interface, 0, MaxInterfaces)
	totalAddresses := 0
	selectedID := ""
	for _, info := range infos {
		isSelected := info.selected
		if info.noise && !isSelected {
			continue
		}
		if len(interfaces) >= MaxInterfaces || totalAddresses >= MaxAddressesPerHost {
			break
		}
		addresses := append([]Address(nil), info.addresses...)
		if isSelected {
			addresses = primaryFirst(addresses, selectedAddress)
		}
		if len(addresses) > MaxAddressesPerNIC {
			addresses = addresses[:MaxAddressesPerNIC]
		}
		remaining := MaxAddressesPerHost - totalAddresses
		if len(addresses) > remaining {
			addresses = addresses[:remaining]
		}
		iface := Interface{
			ID:           interfaceID(info),
			Name:         info.name,
			MACAddress:   info.macAddress,
			Type:         info.kind,
			Virtual:      info.virtual,
			DefaultRoute: isSelected && selectionSource == SourceRouteToControl,
			Addresses:    addresses,
		}
		if isSelected {
			selectedID = iface.ID
		}
		interfaces = append(interfaces, iface)
		totalAddresses += len(addresses)
	}

	if selectedAddress == "" && len(interfaces) > 0 && len(interfaces[0].Addresses) > 0 {
		selectedAddress = interfaces[0].Addresses[0].Address
		selectedID = interfaces[0].ID
	}
	selectionFamily := ""
	if ip := net.ParseIP(selectedAddress); ip != nil {
		selectionFamily = "ipv6"
		if ip.To4() != nil {
			selectionFamily = "ipv4"
		}
	}
	return Snapshot{
		SchemaVersion: SchemaVersion,
		CollectedAt:   collectedAt.UTC().Format(time.RFC3339),
		Selection: Selection{
			Address:     selectedAddress,
			Family:      selectionFamily,
			InterfaceID: selectedID,
			Source:      selectionSource,
		},
		Interfaces: interfaces,
	}
}

func interfaceRank(info interfaceInfo) int {
	if info.noise {
		return 4
	}
	if !info.virtual {
		return 0
	}
	if info.kind == "vpn" {
		return 1
	}
	return 2
}

func primaryFirst(addresses []Address, primary string) []Address {
	out := make([]Address, 0, len(addresses))
	for _, addr := range addresses {
		if addr.Address == primary {
			out = append(out, addr)
			break
		}
	}
	for _, addr := range addresses {
		if addr.Address != primary {
			out = append(out, addr)
		}
	}
	return out
}

func interfaceID(info interfaceInfo) string {
	if info.macAddress != "" {
		return "mac:" + info.macAddress
	}
	return "if:" + strconv.Itoa(info.index) + ":" + strings.ToLower(info.name)
}

func normalizeMAC(hw net.HardwareAddr) string {
	if len(hw) == 0 {
		return ""
	}
	value := strings.ToLower(hw.String())
	if value == "00:00:00:00:00:00" {
		return ""
	}
	return value
}

func classifyInterface(raw string) (kind string, virtual bool, noise bool) {
	name := strings.ToLower(strings.TrimSpace(raw))
	switch {
	case strings.HasPrefix(name, "tun"), strings.HasPrefix(name, "tap"),
		strings.HasPrefix(name, "wg"), strings.HasPrefix(name, "utun"),
		strings.Contains(name, "vpn"):
		return "vpn", true, false
	case strings.HasPrefix(name, "docker"), strings.HasPrefix(name, "veth"),
		strings.HasPrefix(name, "br-"), strings.HasPrefix(name, "virbr"),
		strings.HasPrefix(name, "cni"), strings.HasPrefix(name, "flannel"),
		strings.Contains(name, "vethernet (wsl"):
		return "virtual", true, true
	case strings.HasPrefix(name, "vmnet"), strings.HasPrefix(name, "vboxnet"),
		strings.HasPrefix(name, "vethernet"), strings.Contains(name, "hyper-v"),
		strings.HasPrefix(name, "bridge"):
		return "virtual", true, false
	case strings.HasPrefix(name, "wl"), strings.Contains(name, "wi-fi"), strings.Contains(name, "wifi"):
		return "wifi", false, false
	case strings.HasPrefix(name, "eth"), strings.HasPrefix(name, "en"), strings.Contains(name, "ethernet"):
		return "ethernet", false, false
	default:
		return "unknown", false, false
	}
}

func routeAddress(ctx context.Context, controlPlaneURL string) net.IP {
	u, err := url.Parse(strings.TrimSpace(controlPlaneURL))
	if err != nil || u.Hostname() == "" {
		return nil
	}
	port := u.Port()
	if port == "" {
		if strings.EqualFold(u.Scheme, "http") || strings.EqualFold(u.Scheme, "ws") {
			port = "80"
		} else {
			port = "443"
		}
	}
	lookupCtx, cancel := context.WithTimeout(ctx, routeProbeTimeout)
	defer cancel()
	resolved, err := net.DefaultResolver.LookupIPAddr(lookupCtx, u.Hostname())
	if err != nil {
		return nil
	}
	for _, candidate := range resolved {
		if !usableIP(candidate.IP) && !candidate.IP.IsLoopback() {
			continue
		}
		network := "udp6"
		if candidate.IP.To4() != nil {
			network = "udp4"
		}
		dialer := net.Dialer{Timeout: routeProbeTimeout}
		conn, err := dialer.DialContext(lookupCtx, network, net.JoinHostPort(candidate.IP.String(), port))
		if err != nil {
			continue
		}
		local := conn.LocalAddr()
		_ = conn.Close()
		if udp, ok := local.(*net.UDPAddr); ok {
			return udp.IP
		}
	}
	return nil
}

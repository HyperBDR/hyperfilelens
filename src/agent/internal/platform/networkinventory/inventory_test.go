package networkinventory

import (
	"net"
	"testing"
	"time"
)

func TestBuildSnapshotSelectsRouteAddressAndMatchingMAC(t *testing.T) {
	infos := []interfaceInfo{
		{
			index:      2,
			name:       "Ethernet 1",
			macAddress: "00:11:22:33:44:66",
			kind:       "ethernet",
			addresses:  []Address{{Address: "10.20.2.15", Family: "ipv4", PrefixLength: 24}},
		},
		{
			index:      1,
			name:       "Ethernet 0",
			macAddress: "00:11:22:33:44:55",
			kind:       "ethernet",
			addresses:  []Address{{Address: "10.20.1.15", Family: "ipv4", PrefixLength: 24}},
		},
	}

	snapshot := buildSnapshot(infos, net.ParseIP("10.20.1.15"), time.Unix(0, 0))
	if got := snapshot.PrimaryAddress(); got != "10.20.1.15" {
		t.Fatalf("PrimaryAddress()=%q", got)
	}
	if got := snapshot.PrimaryMACAddress(); got != "00:11:22:33:44:55" {
		t.Fatalf("PrimaryMACAddress()=%q", got)
	}
	if got := snapshot.Selection.Source; got != SourceRouteToControl {
		t.Fatalf("Selection.Source=%q", got)
	}
}

func TestBuildSnapshotKeepsSelectedNoisyVirtualInterface(t *testing.T) {
	infos := []interfaceInfo{
		{
			index:     9,
			name:      "vEthernet (WSL)",
			kind:      "virtual",
			virtual:   true,
			noise:     true,
			addresses: []Address{{Address: "172.28.16.1", Family: "ipv4", PrefixLength: 20}},
		},
	}
	snapshot := buildSnapshot(infos, net.ParseIP("172.28.16.1"), time.Unix(0, 0))
	if len(snapshot.Interfaces) != 1 || snapshot.PrimaryAddress() != "172.28.16.1" {
		t.Fatalf("unexpected snapshot: %+v", snapshot)
	}
}

func TestBuildSnapshotKeepsRouteAddressBeyondPerInterfaceLimit(t *testing.T) {
	addresses := make([]Address, 0, MaxAddressesPerNIC+1)
	for index := 1; index <= MaxAddressesPerNIC; index++ {
		addresses = append(addresses, Address{
			Address:      net.IPv4(10, 20, 1, byte(index)).String(),
			Family:       "ipv4",
			PrefixLength: 24,
		})
	}
	addresses = append(addresses, Address{
		Address:      "10.20.1.250",
		Family:       "ipv4",
		PrefixLength: 24,
	})
	snapshot := buildSnapshot([]interfaceInfo{{
		index:      1,
		name:       "Ethernet 0",
		macAddress: "00:11:22:33:44:55",
		kind:       "ethernet",
		addresses:  addresses,
	}}, net.ParseIP("10.20.1.250"), time.Unix(0, 0))

	if snapshot.PrimaryAddress() != "10.20.1.250" {
		t.Fatalf("PrimaryAddress()=%q", snapshot.PrimaryAddress())
	}
	if len(snapshot.Interfaces[0].Addresses) != MaxAddressesPerNIC {
		t.Fatalf("addresses=%d", len(snapshot.Interfaces[0].Addresses))
	}
}

func TestBuildSnapshotDropsUnselectedNoiseAndBoundsInventory(t *testing.T) {
	infos := make([]interfaceInfo, 0, MaxInterfaces+5)
	infos = append(infos, interfaceInfo{
		index:     99,
		name:      "docker0",
		kind:      "virtual",
		virtual:   true,
		noise:     true,
		addresses: []Address{{Address: "172.17.0.1", Family: "ipv4", PrefixLength: 16}},
	})
	for i := 0; i < MaxInterfaces+5; i++ {
		infos = append(infos, interfaceInfo{
			index:     i + 1,
			name:      "eth" + string(rune('a'+i)),
			kind:      "ethernet",
			addresses: []Address{{Address: net.IPv4(10, 0, byte(i), 1).String(), Family: "ipv4", PrefixLength: 24}},
		})
	}
	snapshot := buildSnapshot(infos, nil, time.Unix(0, 0))
	if len(snapshot.Interfaces) != MaxInterfaces {
		t.Fatalf("interfaces=%d want=%d", len(snapshot.Interfaces), MaxInterfaces)
	}
	for _, iface := range snapshot.Interfaces {
		if iface.Name == "docker0" {
			t.Fatal("unselected noise interface was retained")
		}
	}
	if got := len(snapshot.IPAddresses()); got > MaxAddressesPerHost {
		t.Fatalf("addresses=%d", got)
	}
}

func TestNormalizeAddressesRejectsNonUsableAddresses(t *testing.T) {
	addresses := normalizeAddresses([]net.Addr{
		&net.IPNet{IP: net.ParseIP("127.0.0.1"), Mask: net.CIDRMask(8, 32)},
		&net.IPNet{IP: net.ParseIP("169.254.1.1"), Mask: net.CIDRMask(16, 32)},
		&net.IPNet{IP: net.ParseIP("10.20.1.15"), Mask: net.CIDRMask(24, 32)},
	})
	if len(addresses) != 1 || addresses[0].Address != "10.20.1.15" || addresses[0].PrefixLength != 24 {
		t.Fatalf("addresses=%+v", addresses)
	}
}

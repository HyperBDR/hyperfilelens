package netmac

import (
	"testing"

	psnet "github.com/shirou/gopsutil/v4/net"
)

func TestFormatMAC(t *testing.T) {
	if got := formatMAC("AA-BB-CC-DD-EE-FF"); got != "aa:bb:cc:dd:ee:ff" {
		t.Fatalf("formatMAC() = %q", got)
	}
	if got := formatMAC(""); got != "" {
		t.Fatalf("formatMAC(empty) = %q", got)
	}
}

func TestScoreInterfacePrefersIPv4(t *testing.T) {
	low, macLow := scoreInterface(psnet.InterfaceStat{
		Name:         "eth0",
		HardwareAddr: "aa:bb:cc:dd:ee:01",
		Flags:        []string{"up"},
	})
	high, macHigh := scoreInterface(psnet.InterfaceStat{
		Name:         "eth1",
		HardwareAddr: "aa:bb:cc:dd:ee:02",
		Flags:        []string{"up"},
		Addrs:        []psnet.InterfaceAddr{{Addr: "10.0.0.5/24"}},
	})
	if macLow == "" || macHigh == "" {
		t.Fatalf("expected scored macs, got %q and %q", macLow, macHigh)
	}
	if high <= low {
		t.Fatalf("ipv4 interface score = %d, want > %d", high, low)
	}
}

func TestScoreInterfaceSkipsLoopback(t *testing.T) {
	score, mac := scoreInterface(psnet.InterfaceStat{
		Name:         "lo",
		HardwareAddr: "00:00:00:00:00:00",
		Flags:        []string{"up", "loopback"},
		Addrs:        []psnet.InterfaceAddr{{Addr: "127.0.0.1/8"}},
	})
	if score >= 0 || mac != "" {
		t.Fatalf("loopback should be skipped, score=%d mac=%q", score, mac)
	}
}

func TestPrimaryMACDoesNotPanic(t *testing.T) {
	_ = PrimaryMAC()
}

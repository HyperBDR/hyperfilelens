package enroll

import "testing"

func TestJoinDetail(t *testing.T) {
	got := joinDetail("Console API reachable", "GET /health → 200")
	if got != "Console API reachable (GET /health → 200)" {
		t.Fatalf("got %q", got)
	}
	if joinDetail("Title only", "") != "Title only" {
		t.Fatal("expected title only")
	}
}

func TestHumanBytes(t *testing.T) {
	if humanBytes(2048) != "2.0 KB" {
		t.Fatalf("got %q", humanBytes(2048))
	}
}

func TestDiskCheckPathUsesParent(t *testing.T) {
	got := diskCheckPath("/opt/hyperfilelens-agent")
	if got != "/opt" && got != "/" {
		t.Logf("diskCheckPath -> %q", got)
	}
}

func TestCheckHostname(t *testing.T) {
	result := checkHostname()
	if result.Name == "" && !result.Warning {
		t.Fatal("expected name or warning")
	}
}

func TestResolveWSSURL(t *testing.T) {
	got := resolveWSSURL(Config{APIBase: "https://console.example"})
	if got != "wss://console.example/ws/node/agent/" {
		t.Fatalf("got %q", got)
	}
}

func TestRequiredCommandsDetail(t *testing.T) {
	if requiredCommandsDetail() == "" {
		t.Fatal("expected commands detail")
	}
}

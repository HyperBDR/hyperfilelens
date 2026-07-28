package enroll

import (
	"strings"
	"testing"
	"time"

	"hyperfilelens/agent/internal/model"
	platforminstall "hyperfilelens/agent/internal/platform/install"
)

func TestFormatDownloadProgressKnownLength(t *testing.T) {
	line := formatDownloadProgress(platforminstall.DownloadProgress{
		DownloadedBytes: 5 * 1024 * 1024,
		TotalBytes:      10 * 1024 * 1024,
		Elapsed:         5 * time.Second,
		BytesPerSecond:  1024 * 1024,
	})
	for _, expected := range []string{
		"50%",
		"5.0 MiB / 10.0 MiB",
		"1.0 MiB/s",
		"ETA 5s",
	} {
		if !strings.Contains(line, expected) {
			t.Fatalf("progress %q does not contain %q", line, expected)
		}
	}
}

func TestFormatDownloadProgressWaitingWithoutLength(t *testing.T) {
	line := formatDownloadProgress(platforminstall.DownloadProgress{
		DownloadedBytes: 3 * 1024,
		TotalBytes:      -1,
		Elapsed:         7 * time.Second,
	})
	for _, expected := range []string{"3.0 KiB downloaded", "waiting for data", "elapsed 7s"} {
		if !strings.Contains(line, expected) {
			t.Fatalf("progress %q does not contain %q", line, expected)
		}
	}
}

func TestRoleDownloadLabels(t *testing.T) {
	cases := map[model.Role]string{
		model.RoleAgent:   "Source Host Agent package",
		model.RoleProxy:   "Proxy Host Agent package",
		model.RoleGateway: "Data Gateway Agent package",
	}
	for role, expected := range cases {
		if got := agentPackageLabel(role); got != expected {
			t.Fatalf("role %q label=%q, want %q", role, got, expected)
		}
	}
}

func TestSafeDownloadFilenameExcludesQuery(t *testing.T) {
	got := safeDownloadFilename(
		"https://console.example/media/agent.tar.gz?token=must-not-appear",
	)
	if got != "agent.tar.gz" || strings.Contains(got, "must-not-appear") {
		t.Fatalf("unsafe download filename: %q", got)
	}
}

package disk

import (
	"runtime"
	"testing"
)

func TestNormalizeMountpoint(t *testing.T) {
	if runtime.GOOS == "windows" {
		tests := []struct {
			in   string
			want string
		}{
			{"c:", "C:\\"},
			{"C:", "C:\\"},
			{`d:\`, "D:\\"},
			{`E:/data`, "E:\\"},
		}
		for _, tc := range tests {
			got := normalizeMountpoint(tc.in)
			if got != tc.want {
				t.Fatalf("normalizeMountpoint(%q) = %q, want %q", tc.in, got, tc.want)
			}
		}
		return
	}
	if got := normalizeMountpoint("/"); got != "/" {
		t.Fatalf("normalizeMountpoint(\"/\") = %q, want \"/\"", got)
	}
}

func TestHostStorageUsage(t *testing.T) {
	total, used, free, count, err := HostStorageUsage()
	if err != nil {
		t.Fatalf("HostStorageUsage() err = %v", err)
	}
	if count <= 0 {
		t.Fatalf("HostStorageUsage() count = %d, want > 0", count)
	}
	if total == 0 {
		t.Fatal("HostStorageUsage() total = 0")
	}
	if used+free > total {
		t.Fatalf("used(%d)+free(%d) > total(%d)", used, free, total)
	}
}

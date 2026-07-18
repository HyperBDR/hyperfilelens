package enroll

import "testing"

func TestIsUbuntuMin(t *testing.T) {
	cases := []struct {
		version string
		major   int
		minor   int
		want    bool
	}{
		{"20.04", 20, 4, true},
		{"20.03", 20, 4, false},
		{"22.04", 20, 4, true},
		{"24.04", 20, 4, true},
		{"18.04", 20, 4, false},
		{"24.10", 24, 4, true},
		{"24.03", 24, 4, false},
	}
	for _, tc := range cases {
		got := ubuntuVersionAtLeast(tc.version, tc.major, tc.minor)
		if got != tc.want {
			t.Errorf("ubuntuVersionAtLeast(%q, %d, %d) = %v, want %v", tc.version, tc.major, tc.minor, got, tc.want)
		}
	}
}

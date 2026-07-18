package kopia

import "strings"

func humanSizeHasUnit(raw string) bool {
	upper := strings.ToUpper(strings.TrimSpace(raw))
	for _, suffix := range []string{"KB", "MB", "GB", "TB", "KIB", "MIB", "GIB", "TIB"} {
		if strings.Contains(upper, suffix) {
			return true
		}
	}
	return strings.HasSuffix(upper, " B") || strings.HasSuffix(upper, "B") && len(upper) > 1 && upper[len(upper)-2] != '.'
}

func credibleBytesTotal(done, total int64) bool {
	if total <= 0 {
		return false
	}
	if done <= 0 {
		return true
	}
	return total*100 >= done*95
}

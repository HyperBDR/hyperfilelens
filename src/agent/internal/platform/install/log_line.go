package install

import (
	"fmt"
	"strings"
	"time"
)

func logTimestampUTC() string {
	t := time.Now().UTC()
	return t.Format("2006-01-02T15:04:05") + fmt.Sprintf(".%03dZ", t.Nanosecond()/1e6)
}

func ensureSentence(msg string) string {
	msg = strings.TrimSpace(msg)
	if msg == "" {
		return msg
	}
	switch msg[len(msg)-1] {
	case '.', '?', '!':
		return msg
	default:
		return msg + "."
	}
}

// FormatLogLine renders one user-facing log line: [timestamp] [LEVEL] message.
func FormatLogLine(level, message string) string {
	switch strings.TrimSpace(level) {
	case "OK":
		level = " OK  "
	case "FAIL":
		level = "FAIL "
	case "WARN":
		level = "WARN "
	case "INFO":
		level = "INFO "
	case "STEP":
		level = "STEP "
	case "SKIP":
		level = "SKIP "
	default:
		level = fmt.Sprintf("%-5s", strings.TrimSpace(level))
	}
	return fmt.Sprintf("[%s] [%s] %s", logTimestampUTC(), level, ensureSentence(message))
}

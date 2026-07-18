package kopia

import (
	"math"
	"regexp"
	"strconv"
	"strings"
)

var (
	restoreProcessedPattern = regexp.MustCompile(
		`(?i)processed\s+(\d+)\s+\(([^)]+)\)\s+of\s+(\d+)\s+\(([^)]+)\)`,
	)
	restoreSpeedPattern = regexp.MustCompile(`(?i)(\d+(?:\.\d+)?)\s*([kmgt]?i?b)\s*/\s*s`)
	restorePercentPattern = regexp.MustCompile(`\((\d+(?:\.\d+)?)\s*%\)`)
	restoreRemainingPattern = regexp.MustCompile(`(?i)remaining\s+(\d+)s`)
)

// RestoreProgressSnapshot captures parsed Kopia restore progress counters.
type RestoreProgressSnapshot struct {
	Phase            string
	Percent          int
	ProcessedCount   int64
	ProcessedBytes   int64
	TotalCount       int64
	TotalBytes       int64
	SpeedBytesPerSec int64
	KopiaEtaSeconds  int64
	Line             string
}

// ParseRestoreProgressLine extracts restore progress from one Kopia output line.
func ParseRestoreProgressLine(raw string) (RestoreProgressSnapshot, bool) {
	line := NormalizeProgressLine(raw)
	if line == "" {
		return RestoreProgressSnapshot{}, false
	}

	snapshot := RestoreProgressSnapshot{Line: line}
	match := restoreProcessedPattern.FindStringSubmatch(line)
	if len(match) != 5 {
		return RestoreProgressSnapshot{}, false
	}

	snapshot.ProcessedCount, _ = strconv.ParseInt(match[1], 10, 64)
	snapshot.ProcessedBytes = parseHumanSize(match[2])
	snapshot.TotalCount, _ = strconv.ParseInt(match[3], 10, 64)
	snapshot.TotalBytes = parseHumanSize(match[4])

	if speedMatch := restoreSpeedPattern.FindStringSubmatch(line); len(speedMatch) == 3 {
		snapshot.SpeedBytesPerSec = speedFromRate(speedMatch[1], speedMatch[2])
	}
	if percentMatch := restorePercentPattern.FindStringSubmatch(line); len(percentMatch) == 2 {
		if value, err := strconv.ParseFloat(percentMatch[1], 64); err == nil {
			snapshot.Percent = clampPercent(int(math.Round(value)))
		}
	}
	if remainingMatch := restoreRemainingPattern.FindStringSubmatch(line); len(remainingMatch) == 2 {
		if value, err := strconv.ParseInt(remainingMatch[1], 10, 64); err == nil && value >= 0 {
			snapshot.KopiaEtaSeconds = value
		}
	}
	if snapshot.Percent <= 0 && snapshot.TotalBytes > 0 {
		ratio := float64(snapshot.ProcessedBytes) / float64(snapshot.TotalBytes)
		snapshot.Percent = clampPercent(int(math.Round(ratio * 100)))
	}
	if snapshot.ProcessedBytes <= 0 && snapshot.TotalBytes <= 0 {
		return RestoreProgressSnapshot{}, false
	}
	snapshot.Phase = "restoring"
	return snapshot, true
}

// RestoreProgressPayload converts a parsed restore snapshot into a task.progress payload.
func RestoreProgressPayload(snapshot RestoreProgressSnapshot) map[string]any {
	payload := map[string]any{
		"phase":              "kopia_transfer",
		"kopia_phase":        snapshot.Phase,
		"kopia_percent":      snapshot.Percent,
		"percent":            snapshot.Percent,
		"bytes_done":         snapshot.ProcessedBytes,
		"bytes_total":        snapshot.TotalBytes,
		"bytes_total_known":  snapshot.TotalBytes > 0,
		"file_done":          snapshot.ProcessedCount,
		"file_total":         snapshot.TotalCount,
		"processed_bytes":    snapshot.ProcessedBytes,
		"total_bytes":        snapshot.TotalBytes,
		"processed_count":    snapshot.ProcessedCount,
		"total_count":        snapshot.TotalCount,
	}
	if snapshot.SpeedBytesPerSec > 0 {
		payload["speed_bps"] = snapshot.SpeedBytesPerSec
	}
	if snapshot.KopiaEtaSeconds > 0 {
		payload["kopia_eta_seconds"] = snapshot.KopiaEtaSeconds
	}
	if snapshot.Line != "" {
		payload["progress_text"] = snapshot.Line
	}
	return payload
}

func speedFromRate(numberRaw, unitRaw string) int64 {
	number, err := strconv.ParseFloat(strings.TrimSpace(numberRaw), 64)
	if err != nil || number <= 0 {
		return 0
	}
	unit := strings.ToUpper(strings.TrimSpace(unitRaw))
	multiplier := int64(1)
	switch unit {
	case "KB/S", "KB":
		multiplier = 1000
	case "MB/S", "MB":
		multiplier = 1000 * 1000
	case "GB/S", "GB":
		multiplier = 1000 * 1000 * 1000
	case "KIB/S", "KIB":
		multiplier = 1024
	case "MIB/S", "MIB":
		multiplier = 1024 * 1024
	case "GIB/S", "GIB":
		multiplier = 1024 * 1024 * 1024
	case "B/S", "B":
		multiplier = 1
	default:
		return 0
	}
	return int64(number * float64(multiplier))
}

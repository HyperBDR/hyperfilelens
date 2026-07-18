package enroll

import (
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/mattn/go-isatty"
)

const (
	ansiReset  = "\033[0m"
	ansiGreen  = "\033[32m"
	ansiYellow = "\033[33m"
	ansiRed    = "\033[31m"
	ansiCyan   = "\033[36m"
)

var useColor = false

func initOutput() {
	if os.Getenv("NO_COLOR") != "" || os.Getenv("HFL_ENROLL_NO_COLOR") != "" {
		useColor = false
		return
	}
	useColor = isatty.IsTerminal(os.Stdout.Fd())
}

func logTimestamp() string {
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

func colorizeLevel(code, level string) string {
	if !useColor || code == "" {
		return level
	}
	return code + level + ansiReset
}

func emitLine(level, msg string, w io.Writer) {
	initOutput()
	msg = ensureSentence(msg)
	var levelStyled string
	switch strings.TrimSpace(level) {
	case "OK":
		levelStyled = colorizeLevel(ansiGreen, level)
	case "WARN":
		levelStyled = colorizeLevel(ansiYellow, level)
	case "FAIL":
		levelStyled = colorizeLevel(ansiRed, level)
	case "STEP", "SKIP":
		levelStyled = colorizeLevel(ansiCyan, level)
	default:
		levelStyled = level
	}
	fmt.Fprintf(w, "[%s] [%s] %s\n", logTimestamp(), levelStyled, msg)
}

func logInfo(msg string) {
	emitLine("INFO ", msg, os.Stdout)
}

func logOK(msg string) {
	emitLine(" OK  ", msg, os.Stdout)
}

func logSkip(msg string) {
	emitLine("SKIP ", msg, os.Stdout)
}

func logWarn(msg string) {
	emitLine("WARN ", msg, os.Stderr)
}

func logStep(msg string) {
	emitLine("STEP ", msg, os.Stdout)
}

func logFail(msg string, code int) {
	emitLine("FAIL ", msg, os.Stderr)
	os.Exit(code)
}

// SummaryInfo is the final enrollment summary block.
type SummaryInfo struct {
	NodeID      string
	Version     string
	Service     string
	InstallPath string
	DataPath    string
	Console     string
}

func printEnrollmentContext(consoleURL, orgKey, role, platform, hostname string) {
	logInfo("Starting HyperFileLens agent enrollment.")
	parts := []string{
		"Console: " + consoleURL,
		"Organization: " + orgKey,
		"Role: " + role,
		"Platform: " + platform,
	}
	if hostname != "" {
		parts = append(parts, "Hostname: "+hostname)
	}
	logInfo(strings.Join(parts, " · "))
}

func printSummaryBlock(info SummaryInfo) {
	msg := "Enrollment completed"
	details := []string{}
	if info.NodeID != "" {
		details = append(details, "node id="+info.NodeID)
	}
	if info.Version != "" {
		details = append(details, "version="+info.Version)
	}
	if info.Service != "" {
		details = append(details, "service="+info.Service)
	}
	if len(details) > 0 {
		msg += " (" + strings.Join(details, ", ") + ")"
	}
	logInfo(msg + ".")
}

func printNextStep(line string) {
	logInfo(line)
}

func printResult(line string) {
	logInfo(line)
}

func printEnrollmentSuccess(info SummaryInfo) {
	printSummaryBlock(info)
	printNextStep("Return to the console to add backup sources and policies.")
}

func printAlreadyEnrolled(info SummaryInfo) {
	printSummaryBlock(info)
	printResult("This node is already enrolled. No changes were made.")
}

func printTokenAlreadyUsed(info SummaryInfo) {
	if info.NodeID != "" || info.Version != "" || info.Service != "" {
		printSummaryBlock(info)
	}
	printResult("This enrollment link was already used. Open the console to manage this node.")
}

func summaryFromState(consoleURL, nodeID, version, service string) SummaryInfo {
	installDir := defaultInstallPath()
	return SummaryInfo{
		NodeID:      nodeID,
		Version:     version,
		Service:     service,
		InstallPath: installDir,
		DataPath:    dataDirForAgent(),
		Console:     consoleURL,
	}
}

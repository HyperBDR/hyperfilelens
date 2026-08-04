package enroll

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/mattn/go-isatty"

	"hyperfilelens/agent/internal/model"
)

const (
	ansiReset   = "\033[0m"
	ansiBold    = "\033[1m"
	ansiGreen   = "\033[32m"
	ansiYellow  = "\033[33m"
	ansiRed     = "\033[31m"
	ansiCyan    = "\033[36m"
	ansiMagenta = "\033[35m"
)

var useColor bool
var bannerPrinted bool

// InstallFailure is a typed installer failure rendered at the command boundary.
type InstallFailure struct {
	Stage   string
	Reason  string
	Code    int
	CodeKey string
}

func (failure InstallFailure) Error() string { return failure.Reason }

func initOutput() {
	mode := strings.ToLower(strings.TrimSpace(os.Getenv("HFL_OUTPUT")))
	if mode == "plain" || mode == "json" || os.Getenv("NO_COLOR") != "" ||
		os.Getenv("HFL_ENROLL_NO_COLOR") != "" {
		useColor = false
		return
	}
	stdout := commandStdout()
	useColor = isatty.IsTerminal(stdout.Fd()) || isatty.IsCygwinTerminal(stdout.Fd())
}

func colorize(code, value string) string {
	if !useColor || code == "" {
		return value
	}
	return code + value + ansiReset
}

func emitLine(level, message string, writer io.Writer) {
	initOutput()
	message = strings.TrimSpace(message)
	if message == "" {
		return
	}
	if jsonOutput() {
		emitJSON(writer, map[string]any{
			"type":    "install_event",
			"status":  strings.TrimSpace(level),
			"message": message,
		})
		return
	}
	styled := level
	switch level {
	case " OK ":
		styled = colorize(ansiGreen, level)
	case "WARN":
		styled = colorize(ansiYellow, level)
	case "FAIL":
		styled = colorize(ansiRed, level)
	case "SKIP":
		styled = colorize(ansiCyan, level)
	case "....":
		styled = colorize(ansiMagenta, level)
	case "INFO":
		styled = colorize(ansiCyan, level)
	}
	_, _ = fmt.Fprintf(writer, "[%s] %s\n", styled, message)
}

func logInfo(message string) { emitLine("INFO", message, os.Stdout) }
func logOK(message string)   { emitLine(" OK ", message, os.Stdout) }
func logSkip(message string) { emitLine("SKIP", message, os.Stdout) }
func logWarn(message string) { emitLine("WARN", message, os.Stderr) }
func logStep(message string) { emitLine("....", message, os.Stdout) }

func logFail(message string, code int) {
	abortInstall("Installing", message, code, fmt.Sprintf("HFL-INSTALL-%03d", code))
}

func abortInstall(stage, message string, code int, codeKey string) {
	message = strings.TrimSpace(message)
	emitLine("FAIL", message, os.Stderr)
	panic(InstallFailure{
		Stage:   stage,
		Reason:  message,
		Code:    code,
		CodeKey: codeKey,
	})
}

// RecoverInstallFailure converts the internal abort boundary into a normal error.
func RecoverInstallFailure(target *error) {
	if recovered := recover(); recovered != nil {
		if failure, ok := recovered.(InstallFailure); ok {
			*target = failure
			return
		}
		panic(recovered)
	}
}

// PrintCommandFailure renders a stable final failure block for returned errors.
func PrintCommandFailure(err error) {
	if err == nil {
		return
	}
	failure := InstallFailure{
		Stage:   "Initialization",
		Reason:  err.Error(),
		Code:    1,
		CodeKey: "HFL-INSTALL-001",
	}
	var typed InstallFailure
	if errors.As(err, &typed) {
		failure = typed
	} else if errors.Is(err, ErrInstallLocked) {
		failure.Reason = "Another HyperFileLens installation is already running."
		failure.CodeKey = "HFL-INSTALL-LOCKED"
	}
	if jsonOutput() {
		emitJSON(os.Stderr, map[string]any{
			"type":          "install_result",
			"result":        "failed",
			"stage":         failure.Stage,
			"reason":        ensureSentence(failure.Reason),
			"error_code":    failure.CodeKey,
			"system_change": failure.Stage != "Preflight checks" && failure.Stage != "Initialization",
		})
		return
	}
	title := "Installation failed"
	systemChange := "See the cleanup status above"
	if failure.Stage == "Preflight checks" || failure.Stage == "Initialization" {
		title = "Installation was not started"
		systemChange = "None"
	}
	if failure.Stage == "Post-install verification" {
		title = "Installation completed, but verification failed"
		systemChange = "Agent installed; verification requires attention"
	}
	printResultRule(os.Stderr, title, ansiRed)
	fmt.Fprintln(os.Stderr)
	fmt.Fprintln(os.Stderr, "Failure")
	fmt.Fprintf(os.Stderr, "  %-13s %s\n", "Stage", failure.Stage)
	fmt.Fprintf(os.Stderr, "  %-13s %s\n", "Reason", ensureSentence(failure.Reason))
	fmt.Fprintf(os.Stderr, "  %-13s %s\n", "System change", systemChange)
	fmt.Fprintln(os.Stderr)
	fmt.Fprintln(os.Stderr, "Error code:")
	fmt.Fprintf(os.Stderr, "  %s\n", failure.CodeKey)
	if failure.Stage == "Post-install verification" {
		fmt.Fprintln(os.Stderr)
		fmt.Fprintln(os.Stderr, "Suggested actions:")
		fmt.Fprintln(os.Stderr, "  1. Check outbound network access to the control plane.")
		fmt.Fprintln(os.Stderr, "  2. Confirm that any proxy supports WebSocket connections.")
		fmt.Fprintln(os.Stderr, "  3. Review the Agent service log and run hfl-enroll status.")
	}
}

func ensureSentence(message string) string {
	message = strings.TrimSpace(message)
	if message == "" {
		return message
	}
	switch message[len(message)-1] {
	case '.', '?', '!':
		return message
	default:
		return message + "."
	}
}

func printBanner(role string) {
	if bannerPrinted || os.Getenv("HFL_NO_BANNER") != "" {
		return
	}
	bannerPrinted = true
	columns, _ := strconv.Atoi(strings.TrimSpace(os.Getenv("COLUMNS")))
	if columns > 0 && columns < 96 {
		fmt.Fprintln(os.Stdout, colorize(ansiBold+ansiMagenta, "HyperFileLens Installer"))
	} else {
		fmt.Fprintln(os.Stdout, colorize(ansiBold+ansiMagenta, ` _   _                       _____ _ _      _
| | | |_   _ _ __   ___ _ _|  ___(_) | ___| |    ___ _ __  ___
| |_| | | | | '_ \ / _ \ '__| |_  | | |/ _ \ |   / _ \ '_ \/ __|
|  _  | |_| | |_) |  __/ |  |  _| | | |  __/ |__|  __/ | | \__ \
|_| |_|\__, | .__/ \___|_|  |_|   |_|_|\___|_____\___|_| |_|___/
       |___/|_|                     INSTALLER`))
	}
	fmt.Fprintf(os.Stdout, "\nHyperFileLens %s Installer\n", role)
	fmt.Fprintln(os.Stdout, strings.Repeat("-", 64))
}

// SummaryInfo is the final enrollment summary block.
type SummaryInfo struct {
	Role        string
	NodeID      string
	Version     string
	Service     string
	LensNode    string
	Console     string
	InstallPath string
	DataPath    string
	LogPath     string
}

func printEnrollmentContext(
	consoleURL string,
	orgKey string,
	role model.Role,
	platform string,
	hostname string,
) {
	displayRole := roleDisplayName(role, os.Getenv("HFL_GATEWAY_SCOPE"))
	if jsonOutput() {
		emitJSON(os.Stdout, map[string]any{
			"type":         "install_target",
			"console":      consoleURL,
			"organization": orgKey,
			"role":         displayRole,
			"hostname":     hostname,
			"platform":     platform,
		})
		return
	}
	printBanner(displayRole)
	fmt.Fprintln(os.Stdout)
	fmt.Fprintln(os.Stdout, "Target")
	printSummaryValue("Console", consoleURL)
	printSummaryValue("Organization", orgKey)
	printSummaryValue("Role", displayRole)
	printSummaryValue("Hostname", hostname)
	printSummaryValue("Platform", platform)
	fmt.Fprintln(os.Stdout)
	fmt.Fprintln(os.Stdout, "Preflight checks")
}

func summaryFromState(consoleURL, nodeID, version, service string) SummaryInfo {
	return SummaryInfo{
		NodeID:      nodeID,
		Version:     version,
		Service:     service,
		InstallPath: defaultInstallPath(),
		DataPath:    dataDirForAgent(),
		Console:     consoleURL,
		LogPath:     activeInstallLogPath(),
	}
}

func printEnrollmentSuccess(info SummaryInfo) {
	if info.Role == "" {
		info.Role = roleDisplayName(model.RoleAgent)
	}
	if jsonOutput() {
		emitJSON(os.Stdout, map[string]any{
			"type":          "install_result",
			"result":        "success",
			"role":          info.Role,
			"node_id":       info.NodeID,
			"agent_version": info.Version,
			"agent_service": info.Service,
			"lensnode":      info.LensNode,
			"console_state": "online",
			"install_path":  info.InstallPath,
			"data_path":     info.DataPath,
			"log_file":      info.LogPath,
		})
		return
	}
	printResultRule(os.Stdout, "Installation completed successfully", ansiGreen)
	fmt.Fprintln(os.Stdout)
	fmt.Fprintln(os.Stdout, "Installation summary")
	printSummaryValue("Role", info.Role)
	printSummaryValue("Node ID", info.NodeID)
	printSummaryValue("Agent version", info.Version)
	printSummaryValue("Agent service", info.Service)
	printSummaryValue("LensNode", info.LensNode)
	printSummaryValue("Console state", "online")
	printSummaryValue("Install path", info.InstallPath)
	printSummaryValue("Data path", info.DataPath)
	printSummaryValue("Log file", info.LogPath)
	fmt.Fprintln(os.Stdout)
	fmt.Fprintln(os.Stdout, "Next step:")
	fmt.Fprintln(os.Stdout, "  Open HyperFileLens and continue configuring this host.")
}

func printAlreadyEnrolled(info SummaryInfo) {
	if jsonOutput() {
		emitJSON(os.Stdout, map[string]any{
			"type":          "install_result",
			"result":        "unchanged",
			"node_id":       info.NodeID,
			"agent_version": info.Version,
			"agent_service": info.Service,
		})
		return
	}
	printResultRule(os.Stdout, "Existing installation is healthy", ansiGreen)
	fmt.Fprintln(os.Stdout)
	fmt.Fprintln(os.Stdout, "No changes were required.")
	printSummaryValue("Node ID", info.NodeID)
	printSummaryValue("Agent version", info.Version)
	printSummaryValue("Agent service", info.Service)
}

func printResultRule(writer io.Writer, title, color string) {
	fmt.Fprintln(writer)
	fmt.Fprintln(writer, strings.Repeat("=", 64))
	fmt.Fprintln(writer, colorize(ansiBold+color, title))
	fmt.Fprintln(writer, strings.Repeat("=", 64))
}

func printSummaryValue(label, value string) {
	if strings.TrimSpace(value) == "" {
		return
	}
	fmt.Fprintf(os.Stdout, "  %-13s %s\n", label, value)
}

func installLogPath() string {
	return filepath.Join(dataDirForAgent(), "logs", "install.log")
}

func jsonOutput() bool {
	return strings.EqualFold(strings.TrimSpace(os.Getenv("HFL_OUTPUT")), "json")
}

func emitJSON(writer io.Writer, payload map[string]any) {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return
	}
	_, _ = fmt.Fprintln(writer, string(encoded))
}

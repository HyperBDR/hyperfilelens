package main

import (
	"context"
	"fmt"
	"os"
	"strings"

	"hyperfilelens/agent/internal/enroll"
)

func main() {
	removeBootstrapTempBinary()

	if len(os.Args) < 2 {
		printHelp()
		os.Exit(0)
	}
	ctx := context.Background()
	switch os.Args[1] {
	case "install":
		opts := enroll.ParseInstallOptions(os.Args[2:])
		if err := enroll.RunInstall(ctx, opts); err != nil {
			os.Exit(1)
		}
	case "gateway-install":
		opts := enroll.ParseInstallOptions(os.Args[2:])
		if err := enroll.RunGatewayInstall(ctx, opts); err != nil {
			os.Exit(1)
		}
	case "gateway-upgrade":
		fromArchive := parseFromFlag(os.Args[2:])
		if err := enroll.RunGatewayUpgrade(ctx, fromArchive); err != nil {
			os.Exit(1)
		}
	case "gateway-uninstall":
		purgeAll := !hasFlag(os.Args[2:], "--keep-data")
		if err := enroll.RunGatewayUninstall(ctx, purgeAll); err != nil {
			os.Exit(1)
		}
	case "register":
		opts := enroll.ParseInstallOptions(os.Args[2:])
		if err := enroll.RunRegister(ctx, opts); err != nil {
			os.Exit(1)
		}
	case "status":
		if err := enroll.RunStatus(ctx); err != nil {
			os.Exit(1)
		}
	case "help", "-h", "--help":
		printHelp()
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q (try: hfl-enroll help)\n", os.Args[1])
		os.Exit(2)
	}
}

func printHelp() {
	fmt.Print(`HyperFileLens enrollment tool

Usage:
  hfl-enroll install [--yes|-y]           Download/install or re-enroll an existing agent
  hfl-enroll gateway-install [--yes|-y]   Data Gateway: agent + AI engine (Linux)
  hfl-enroll gateway-upgrade [--from PATH] Upgrade agent bundle and LensNode sidecar (Linux)
  hfl-enroll gateway-uninstall [--keep-data] Remove sidecar and agent (default: purge-all)
  hfl-enroll register [--yes|-y]          HTTP heartbeat registration only (agent installed)
  hfl-enroll status                       Show node_id and service state
  hfl-enroll help                         Show this help

Flags:
  --yes, -y    Skip confirmation prompts (repair, upgrade, re-bind on existing install)

Environment (set by bootstrap stub from console):
  HFL_ORG_KEY, HFL_NODE_ROLE, HFL_NODE_TOKEN, HFL_API_BASE, HFL_WSS_URL
  HFL_INSECURE_TLS       Default 1 (skip TLS verify for dev/self-signed)
`)
}

func parseFromFlag(args []string) string {
	for i, arg := range args {
		if arg == "--from" && i+1 < len(args) {
			return strings.TrimSpace(args[i+1])
		}
		if strings.HasPrefix(arg, "--from=") {
			return strings.TrimSpace(strings.TrimPrefix(arg, "--from="))
		}
	}
	return ""
}

func hasFlag(args []string, name string) bool {
	for _, arg := range args {
		if arg == name {
			return true
		}
	}
	return false
}

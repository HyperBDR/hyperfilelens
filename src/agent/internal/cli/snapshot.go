package cli

import (
	"context"
	"flag"
	"fmt"
	"os"
)

func runSnapshot(ctx context.Context, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: hfl-agent snapshot list|create")
	}
	switch args[0] {
	case "list", "ls":
		return snapshotList(ctx, args[1:])
	case "create":
		return snapshotCreate(ctx, args[1:])
	default:
		return fmt.Errorf("unknown snapshot command %q", args[0])
	}
}

func snapshotList(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("snapshot list", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	var (
		configFile string
		repoName   string
		asJSON     bool
		dataDir    string
	)
	fs.StringVar(&configFile, "config-file", "", "kopia repository config file")
	fs.StringVar(&repoName, "repo", "", "registered repo alias")
	fs.BoolVar(&asJSON, "json", false, "print JSON result")
	fs.StringVar(&dataDir, "data-dir", "", "override HFL_DATA_DIR")
	if err := fs.Parse(args); err != nil {
		return err
	}

	cfgPath, err := resolveKopiaConfig(ctx, dataDir, repoName, configFile)
	if err != nil {
		return err
	}
	store, err := openConfigStore(ctx, dataDir)
	if err != nil {
		return err
	}
	return runEngineCommand(ctx, store, "snapshot.list", map[string]any{
		"config_file": cfgPath,
	}, asJSON, false)
}

func snapshotCreate(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("snapshot create", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	var (
		configFile string
		repoName   string
		asJSON     bool
		quiet      bool
		dataDir    string
	)
	fs.StringVar(&configFile, "config-file", "", "kopia repository config file")
	fs.StringVar(&repoName, "repo", "", "registered repo alias")
	fs.BoolVar(&asJSON, "json", false, "print JSON result")
	fs.BoolVar(&quiet, "quiet", false, "suppress progress on stderr")
	fs.StringVar(&dataDir, "data-dir", "", "override HFL_DATA_DIR")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 1 {
		return fmt.Errorf("usage: hfl-agent snapshot create <path> [--repo NAME | --config-file PATH]")
	}

	cfgPath, err := resolveKopiaConfig(ctx, dataDir, repoName, configFile)
	if err != nil {
		return err
	}
	store, err := openConfigStore(ctx, dataDir)
	if err != nil {
		return err
	}
	return runEngineCommand(ctx, store, "backup", map[string]any{
		"config_file": cfgPath,
		"path":        fs.Arg(0),
	}, asJSON, quiet)
}

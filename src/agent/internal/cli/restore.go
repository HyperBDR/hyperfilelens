package cli

import (
	"context"
	"flag"
	"fmt"
	"os"
)

func runRestore(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("restore", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	var (
		configFile string
		repoName   string
		snapshotID string
		asJSON     bool
		quiet      bool
		dataDir    string
	)
	fs.StringVar(&configFile, "config-file", "", "kopia repository config file")
	fs.StringVar(&repoName, "repo", "", "registered repo alias (see: hfl-agent repo list)")
	fs.StringVar(&snapshotID, "snapshot", "latest", "snapshot ID or 'latest'")
	fs.BoolVar(&asJSON, "json", false, "print JSON result")
	fs.BoolVar(&quiet, "quiet", false, "suppress progress on stderr")
	fs.StringVar(&dataDir, "data-dir", "", "override HFL_DATA_DIR")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 1 {
		return fmt.Errorf("usage: hfl-agent restore <target-path> [--repo NAME | --config-file PATH] [--snapshot ID]")
	}

	cfgPath, err := resolveKopiaConfig(ctx, dataDir, repoName, configFile)
	if err != nil {
		return err
	}

	store, err := openConfigStore(ctx, dataDir)
	if err != nil {
		return err
	}
	return runEngineCommand(ctx, store, "restore", map[string]any{
		"config_file": cfgPath,
		"path":        fs.Arg(0),
		"snapshot_id": snapshotID,
	}, asJSON, quiet)
}

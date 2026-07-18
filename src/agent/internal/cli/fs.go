package cli

import (
	"context"
	"flag"
	"fmt"
	"os"
)

func runFS(ctx context.Context, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: hfl-agent fs ls <path> [--json]")
	}
	switch args[0] {
	case "ls", "list":
		return fsList(ctx, args[1:])
	default:
		return fmt.Errorf("unknown fs command %q", args[0])
	}
}

func fsList(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("fs ls", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	var (
		asJSON  bool
		dataDir string
	)
	fs.BoolVar(&asJSON, "json", false, "print JSON result")
	fs.StringVar(&dataDir, "data-dir", "", "override HFL_DATA_DIR")
	if err := fs.Parse(args); err != nil {
		return err
	}
	path := "."
	if fs.NArg() > 0 {
		path = fs.Arg(0)
	}

	store, err := openConfigStore(ctx, dataDir)
	if err != nil {
		return err
	}
	return runEngineCommand(ctx, store, "browse", map[string]any{"path": path}, asJSON, false)
}

package config

import (
	"context"
	"fmt"
	"os"
	"strings"
)

// RunCLI handles `hfl-agent config show|set|paths` subcommands.
func RunCLI(ctx context.Context, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: hfl-agent config show|set|paths")
	}
	switch args[0] {
	case "show":
		return runConfigShow(ctx, args[1:])
	case "set":
		return runConfigSet(ctx, args[1:])
	case "paths":
		return runConfigPaths(ctx)
	default:
		return fmt.Errorf("unknown config command %q", args[0])
	}
}

func runConfigShow(ctx context.Context, args []string) error {
	opts, err := overridesFromCLI(nil)
	if err != nil {
		return err
	}
	store, err := NewStore(ctx, LoadOptions{Overrides: opts})
	if err != nil {
		return err
	}
	text, err := DumpText(store.Current())
	if err != nil {
		return err
	}
	_, err = fmt.Print(text)
	return err
}

func runConfigSet(ctx context.Context, args []string) error {
	if len(args) != 1 {
		return fmt.Errorf("usage: hfl-agent config set HFL_KEY=value")
	}
	pair := strings.TrimSpace(args[0])
	key, val, ok := strings.Cut(pair, "=")
	if !ok {
		return fmt.Errorf("expected KEY=value, got %q", pair)
	}
	opts, err := overridesFromCLI(nil)
	if err != nil {
		return err
	}
	store, err := NewStore(ctx, LoadOptions{Overrides: opts})
	if err != nil {
		return err
	}
	if err := store.SetEnv(ctx, key, val); err != nil {
		return err
	}
	envPath, jsonPath := store.Paths()
	fmt.Fprintf(os.Stdout, "updated %s (also see %s)\n", envPath, jsonPath)
	text, err := DumpText(store.Current())
	if err != nil {
		return err
	}
	_, err = fmt.Fprint(os.Stdout, text)
	return err
}

func runConfigPaths(ctx context.Context) error {
	opts, err := overridesFromCLI(nil)
	if err != nil {
		return err
	}
	store, err := NewStore(ctx, LoadOptions{Overrides: opts})
	if err != nil {
		return err
	}
	envPath, jsonPath := store.Paths()
	fmt.Printf("env_file=%s\njson_file=%s\nreload_interval=%s\n", envPath, jsonPath, defaultReloadInterval)
	return nil
}

// overridesFromCLI builds Overrides from process env only (config subcommands).
func overridesFromCLI(_ []string) (Overrides, error) {
	return Overrides{}, nil
}

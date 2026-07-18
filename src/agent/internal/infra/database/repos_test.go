package database

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRepoRepoConnectListDisconnect(t *testing.T) {
	ctx := t.Context()
	dir := t.TempDir()
	cfgFile := filepath.Join(dir, "repo.config")
	if err := os.WriteFile(cfgFile, []byte("dummy"), 0o644); err != nil {
		t.Fatal(err)
	}

	db, err := Open(ctx, filepath.Join(dir, "agent.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	repos := NewRepoRepo(db)
	if err := repos.Connect(ctx, ConnectInput{
		Name:        "main",
		ConfigFile:  cfgFile,
		Description: "primary",
	}); err != nil {
		t.Fatal(err)
	}

	got, err := repos.Get(ctx, "main")
	if err != nil {
		t.Fatal(err)
	}
	if got.ConfigFile != cfgFile || got.Description != "primary" {
		t.Fatalf("got %+v", got)
	}

	list, err := repos.List(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 1 || list[0].Name != "main" {
		t.Fatalf("list = %+v", list)
	}

	if err := repos.Disconnect(ctx, "main"); err != nil {
		t.Fatal(err)
	}
	list, err = repos.List(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 0 {
		t.Fatalf("expected empty list, got %d", len(list))
	}
}

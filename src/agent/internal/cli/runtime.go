package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"hyperfilelens/agent/internal/app"
	"hyperfilelens/agent/internal/infra/config"
	"hyperfilelens/agent/internal/infra/database"
	"hyperfilelens/agent/internal/model"
)

type runtime struct {
	store *config.Store
	db    *database.DB
	tasks *database.TaskRepo
}

func openRuntime(ctx context.Context, dataDirOverride string) (*runtime, error) {
	opts := config.LoadOptions{}
	if dataDirOverride = strings.TrimSpace(dataDirOverride); dataDirOverride != "" {
		opts.Overrides.DataDir = dataDirOverride
	}
	store, err := config.NewStore(ctx, opts)
	if err != nil {
		return nil, err
	}
	cfg := store.Current()
	dataRoot, _, _, err := app.ResolveLayout(cfg)
	if err != nil {
		return nil, err
	}
	db, err := database.Open(ctx, database.DefaultPath(dataRoot))
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	return &runtime{
		store: store,
		db:    db,
		tasks: database.NewTaskRepo(db),
	}, nil
}

func (r *runtime) close() {
	if r != nil && r.db != nil {
		_ = r.db.Close()
	}
}

func (r *runtime) dbPath() string {
	if r == nil || r.db == nil {
		return ""
	}
	return r.db.Path()
}

func loadResultJSON(pathOrInline string) (map[string]any, error) {
	raw := strings.TrimSpace(pathOrInline)
	if raw == "" {
		return map[string]any{}, nil
	}
	if strings.HasPrefix(raw, "@") {
		b, err := os.ReadFile(filepath.Clean(strings.TrimPrefix(raw, "@")))
		if err != nil {
			return nil, err
		}
		raw = string(b)
	}
	var out map[string]any
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return nil, err
	}
	if out == nil {
		out = map[string]any{}
	}
	return out, nil
}

func modelStatusFromWire(wireStatus string) model.TaskStatus {
	if wireStatus == "success" {
		return model.TaskStatusSucceeded
	}
	return model.TaskStatusFailed
}

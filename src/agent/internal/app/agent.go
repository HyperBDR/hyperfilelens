package app

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"hyperfilelens/agent/internal/controller"
	"hyperfilelens/agent/internal/infra/config"
	"hyperfilelens/agent/internal/infra/database"
	"hyperfilelens/agent/internal/infra/monitor"
	"hyperfilelens/agent/internal/remote"
	"hyperfilelens/agent/internal/selfupdate"
	"hyperfilelens/agent/internal/wire"
)

const controlPlanePollInterval = 5 * time.Second

// Agent is the runtime composition root coordinating module startup and shutdown.
type Agent struct {
	store     *config.Store
	db        *database.DB
	connector *remote.Connector
	wire      *wire.Handler
	sender    *remote.Sender
	scheduler *controller.Scheduler
	tracker   *controller.Tracker
	taskFixer *controller.TaskFixer
	monitor   *monitor.Collector

	idleLogged bool
}

// New creates an Agent instance backed by a hot-reloadable config Store.
func New(store *config.Store) *Agent {
	return &Agent{
		store:     store,
		sender:    remote.NewSender(),
		scheduler: controller.NewScheduler(2),
		tracker:   controller.NewTracker(),
		monitor:   monitor.NewCollector(),
	}
}

// Startup performs environment checks, opens local DB, repairs stale tasks, and starts subsystems.
func (a *Agent) Startup(ctx context.Context) error {
	cfg := a.store.Current()
	if err := Setup(ctx, cfg); err != nil {
		return err
	}

	dataRoot, logDir, _, err := ResolveLayout(cfg)
	if err != nil {
		return err
	}
	db, err := database.Open(ctx, database.DefaultPath(dataRoot))
	if err != nil {
		return fmt.Errorf("open task database: %w", err)
	}
	a.db = db
	slog.Info("task database ready", "path", db.Path())

	repo := database.NewTaskRepo(db)
	a.wire = wire.NewHandler(a.store, a.tracker, repo)
	a.taskFixer = controller.NewTaskFixer(repo, a.tracker, dataRoot, logDir)

	if _, err := a.taskFixer.RepairRunning(ctx); err != nil {
		return err
	}

	wss := strings.TrimSpace(cfg.WSSURL)
	slog.Info("agent starting",
		"version", selfupdate.Version,
		"commit", selfupdate.Commit,
		"role", cfg.Role,
		"wss_configured", wss != "",
	)
	if wss == "" {
		slog.Info("control plane idle: set HFL_WSS_URL in agent.env or `hfl-agent config set` to connect")
		a.idleLogged = true
	}
	envPath, jsonPath := a.store.Paths()
	slog.Info("config files", "env_file", envPath, "json_file", jsonPath)

	return nil
}

// Run blocks until ctx is cancelled.
func (a *Agent) Run(ctx context.Context) error {
	if err := a.Startup(ctx); err != nil {
		return err
	}
	defer a.Shutdown(context.Background())

	for {
		if err := ctx.Err(); err != nil {
			return err
		}

		wss := strings.TrimSpace(a.store.Current().WSSURL)
		if wss == "" {
			a.waitControlPlaneConfig(ctx)
			continue
		}
		a.idleLogged = false

		if a.connector == nil {
			a.connector = remote.NewConnector(a.store)
			a.sender.Bind(a.connector)
			a.connector.SetHeartbeatHook(func(ctx context.Context) map[string]any {
				sample, err := a.monitor.SampleOnce(ctx)
				if err != nil {
					slog.Debug("monitor sample failed", "err", err)
					return nil
				}
				return map[string]any{"metrics": sample.ToPayload()}
			})
		}

		if err := remote.EnsureNodeRegistered(ctx, a.store, a.store); err != nil {
			slog.Warn("node registration before websocket failed", "err", err)
		}

		err := a.connector.Run(ctx,
			func(ctx context.Context, msg []byte) error {
				return a.wire.Handle(ctx, msg, a.connector)
			},
			func(ctx context.Context) error {
				if a.taskFixer != nil {
					if _, err := a.taskFixer.RepairRunning(ctx); err != nil {
						slog.Warn("connect lifecycle repair failed", "err", err)
					}
				}
				if err := a.wire.FlushUnreportedResults(ctx, a.connector); err != nil {
					return err
				}
				if err := remote.SendInventory(ctx, a.connector, a.store); err != nil {
					return err
				}
				go a.deferredLifecycleRepair(context.WithoutCancel(ctx))
				return nil
			},
		)
		if errors.Is(err, context.Canceled) {
			return err
		}
		if err != nil {
			slog.Warn("websocket session ended", "err", err)
		}

		if strings.TrimSpace(a.store.Current().WSSURL) == "" {
			a.connector = nil
		}
	}
}

func (a *Agent) waitControlPlaneConfig(ctx context.Context) {
	if !a.idleLogged {
		slog.Info("control plane idle: HFL_WSS_URL not set; waiting for configuration")
		a.idleLogged = true
	}
	select {
	case <-ctx.Done():
	case <-time.After(controlPlanePollInterval):
	}
}

// deferredLifecycleRepair re-checks detached upgrade/uninstall tasks after reconnect.
// Startup repair can run while install.ps1 is still executing; this flushes success once logs exist.
func (a *Agent) deferredLifecycleRepair(ctx context.Context) {
	delays := []time.Duration{10 * time.Second, 25 * time.Second}
	for _, delay := range delays {
		select {
		case <-ctx.Done():
			return
		case <-time.After(delay):
		}
		if a.taskFixer == nil || a.wire == nil || a.connector == nil {
			return
		}
		repaired, err := a.taskFixer.RepairRunning(ctx)
		if err != nil {
			slog.Warn("deferred lifecycle repair failed", "err", err)
			continue
		}
		if len(repaired) == 0 {
			continue
		}
		if err := a.wire.FlushUnreportedResults(ctx, a.connector); err != nil {
			slog.Warn("flush deferred lifecycle repair failed", "err", err)
		}
	}
}

// Shutdown stops active tasks and releases resources.
func (a *Agent) Shutdown(ctx context.Context) {
	_ = ctx
	for _, task := range a.tracker.Active() {
		_ = a.tracker.Cancel(ctx, task.ID)
	}
	if a.db != nil {
		_ = a.db.Close()
		a.db = nil
	}
}

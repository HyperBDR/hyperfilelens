package wire

import (
	"context"
	"log/slog"
	"strings"
	"time"

	"hyperfilelens/agent/internal/controller"
	"hyperfilelens/agent/internal/engine"
	"hyperfilelens/agent/internal/infra/config"
	"hyperfilelens/agent/internal/infra/database"
	"hyperfilelens/agent/internal/infra/logging"
	"hyperfilelens/agent/internal/model"
)

// Handler routes downlink task frames to the engine and sends uplink progress/result.
type Handler struct {
	provider config.Provider
	tracker  *controller.Tracker
	tasks    *database.TaskRepo
}

// NewHandler returns a protocol handler bound to config, tracker, and local task storage.
func NewHandler(provider config.Provider, tracker *controller.Tracker, tasks *database.TaskRepo) *Handler {
	return &Handler{provider: provider, tracker: tracker, tasks: tasks}
}

// Handle parses one inbound WebSocket text frame and dispatches by type.
func (h *Handler) Handle(ctx context.Context, raw []byte, sink Sender) error {
	dl, err := ParseDownlink(raw)
	if err != nil {
		slog.Warn("wire downlink parse failed", "err", err)
		return nil
	}

	switch dl.Type {
	case TypeTaskCommand:
		if dl.TaskCommand == nil || dl.TaskCommand.TaskID == "" {
			slog.Warn("task.command missing task_id")
			return nil
		}
		cmd := dl.TaskCommand
		logging.InfoTask(ctx, "task.command received", cmd.NodeID, cmd.TaskID, cmd.Kind,
			"trace_id", cmd.TraceID,
			"correlation_id", cmd.CorrelationID,
		)
		go h.runTask(context.WithoutCancel(ctx), sink, cmd)
		return nil
	case TypeTaskCancel:
		if dl.TaskCancel == nil || dl.TaskCancel.TaskID == "" {
			return nil
		}
		logging.InfoTask(ctx, "task.cancel received", dl.TaskCancel.NodeID, dl.TaskCancel.TaskID, "cancel")
		engine.New(h.provider).Cancel()
		_ = h.tracker.Cancel(ctx, dl.TaskCancel.TaskID)
		if h.tasks != nil {
			_ = h.tasks.MarkCancelled(ctx, dl.TaskCancel.TaskID)
		}
		return nil
	default:
		if dl.Type != "" {
			slog.Debug("wire downlink ignored", "type", dl.Type)
		}
		return nil
	}
}

// FlushUnreportedResults sends task.result for finished tasks not yet acknowledged upstream.
func (h *Handler) FlushUnreportedResults(ctx context.Context, sink Sender) error {
	if h.tasks != nil && sink != nil {
		if err := h.ReattachRunningTasks(ctx, sink); err != nil {
			slog.Warn("reattach running tasks failed", "err", err)
		}
	}
	if h.tasks == nil || sink == nil {
		return nil
	}
	pending, err := h.tasks.ListUnreported(ctx)
	if err != nil {
		return err
	}
	for _, task := range pending {
		wireStatus := database.WireStatus(task.Status)
		errMsg := task.Error
		if errMsg == "" && wireStatus == "failed" {
			errMsg = string(task.Status)
		}
		if err := SendTaskResult(ctx, sink, task.ID, wireStatus, task.Result, errMsg); err != nil {
			slog.Warn("flush task.result failed", "task_id", task.ID, "err", err)
			continue
		}
		if err := h.tasks.MarkResultReported(ctx, task.ID); err != nil {
			slog.Warn("mark result reported failed", "task_id", task.ID, "err", err)
		} else {
			slog.Info("flushed task.result", "task_id", task.ID, "status", wireStatus)
		}
	}
	return nil
}

// ReattachRunningTasks re-publishes in-flight backup progress after reconnect.
func (h *Handler) ReattachRunningTasks(ctx context.Context, sink Sender) error {
	if h.tasks == nil || sink == nil {
		return nil
	}
	tasks, err := h.tasks.ListIncomplete(ctx)
	if err != nil {
		return err
	}
	for _, task := range tasks {
		if task.Status != model.TaskStatusRunning {
			continue
		}
		kind := strings.ToLower(strings.TrimSpace(task.Kind))
		if kind != "backup.run" && kind != "backup" && kind != "restore.run" {
			continue
		}
		progress := map[string]any{
			"phase":    "running",
			"status":   "running",
			"reattach": true,
		}
		if len(task.Result) > 0 {
			if last, ok := task.Result["last_progress"].(map[string]any); ok {
				for key, value := range last {
					progress[key] = value
				}
			}
		}
		if err := SendTaskProgress(ctx, sink, task.ID, progress); err != nil {
			slog.Warn("reattach task.progress failed", "task_id", task.ID, "err", err)
			continue
		}
		slog.Info("reattached running task progress", "task_id", task.ID, "kind", task.Kind)
	}
	return nil
}

func (h *Handler) runTask(ctx context.Context, sink Sender, cmd *TaskCommand) {
	taskCtx, cancel := context.WithCancel(ctx)
	taskCtx = logging.WithTraceID(taskCtx, cmd.TraceID)
	defer cancel()

	logging.InfoTask(taskCtx, "task execution started", cmd.NodeID, cmd.TaskID, cmd.Kind)

	eng := engine.New(h.provider)

	now := time.Now().UTC()
	if h.tasks != nil {
		if err := h.tasks.RecordCommand(taskCtx, database.RecordInput{
			TaskID:    cmd.TaskID,
			JobID:     cmd.JobID(),
			Kind:      cmd.Kind,
			Payload:   cmd.Payload,
			Source:    string(engine.SourceWebSocket),
			StartedAt: &now,
		}); err != nil {
			slog.Warn("persist task.command failed", "task_id", cmd.TaskID, "err", err)
		}
	}

	task := model.Task{
		ID:        cmd.TaskID,
		JobID:     cmd.JobID(),
		Kind:      cmd.Kind,
		Status:    model.TaskStatusRunning,
		Payload:   cmd.Payload,
		StartedAt: &now,
		Source:    string(engine.SourceWebSocket),
	}
	h.tracker.Register(task, cancel)
	defer h.tracker.Unregister(cmd.TaskID)

	_ = SendTaskProgress(taskCtx, sink, cmd.TaskID, map[string]any{
		"phase":  "started",
		"kind":   cmd.Kind,
		"status": "running",
	})

	progressDone := make(chan struct{})
	go h.progressLoop(taskCtx, sink, cmd.TaskID, progressDone)
	defer close(progressDone)

	aliveDone := make(chan struct{})
	go h.aliveLoop(taskCtx, sink, cmd.TaskID, aliveDone)
	defer close(aliveDone)

	wsSink := websocketSink{sink: sink, taskID: cmd.TaskID}
	out := eng.Run(taskCtx, engine.Command{
		ID:      cmd.TaskID,
		JobID:   cmd.JobID(),
		Kind:    cmd.Kind,
		Payload: cmd.Payload,
		Source:  engine.SourceWebSocket,
	}, wsSink)

	status := out.Status
	result := out.Result
	errMsg := out.Error
	if taskCtx.Err() != nil {
		status = "failed"
		errMsg = "canceled"
	}

	if status == "success" {
		logging.InfoTask(taskCtx, "task execution finished", cmd.NodeID, cmd.TaskID, cmd.Kind, "status", status)
	} else {
		logging.WarnTask(taskCtx, "task execution finished", cmd.NodeID, cmd.TaskID, cmd.Kind, "status", status, "err", errMsg)
	}

	if status == "running" {
		if h.tasks != nil {
			if err := h.tasks.UpdateRunning(taskCtx, cmd.TaskID, result); err != nil {
				slog.Warn("persist running task failed", "task_id", cmd.TaskID, "err", err)
			}
		}
		if err := SendTaskResult(taskCtx, sink, cmd.TaskID, status, result, errMsg); err != nil {
			slog.Warn("send task.result failed", "task_id", cmd.TaskID, "err", err)
		} else if h.tasks != nil {
			_ = h.tasks.MarkResultReported(taskCtx, cmd.TaskID)
		}
		return
	}

	localStatus := model.TaskStatusFailed
	if status == "success" {
		localStatus = model.TaskStatusSucceeded
	}
	if errMsg == "canceled" {
		localStatus = model.TaskStatusCancelled
	}

	if h.tasks != nil {
		if err := h.tasks.Finish(taskCtx, cmd.TaskID, localStatus, result, errMsg); err != nil {
			slog.Warn("persist task result failed", "task_id", cmd.TaskID, "err", err)
		}
	}

	if err := SendTaskResult(taskCtx, sink, cmd.TaskID, status, result, errMsg); err != nil {
		slog.Warn("send task.result failed", "task_id", cmd.TaskID, "err", err)
	} else if h.tasks != nil {
		_ = h.tasks.MarkResultReported(taskCtx, cmd.TaskID)
	}
}

func (h *Handler) progressLoop(ctx context.Context, sink Sender, taskID string, done <-chan struct{}) {
	t := time.NewTicker(TaskProgressInterval)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-done:
			return
		case <-t.C:
			_ = SendTaskProgress(ctx, sink, taskID, map[string]any{
				"phase":  "running",
				"status": "running",
			})
		}
	}
}

func (h *Handler) aliveLoop(ctx context.Context, sink Sender, taskID string, done <-chan struct{}) {
	t := time.NewTicker(TaskAliveInterval)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-done:
			return
		case <-t.C:
			_ = SendTaskAlive(ctx, sink, taskID)
		}
	}
}

type websocketSink struct {
	sink   Sender
	taskID string
}

func (w websocketSink) OnProgress(ctx context.Context, progress map[string]any) error {
	return SendTaskProgress(ctx, w.sink, w.taskID, progress)
}

package logging

import (
	"context"
	"fmt"
	"log/slog"
)

// TaskAttrs returns standard agent task log attributes.
func TaskAttrs(nodeID int64, taskID, kind string, extra ...any) []any {
	attrs := []any{
		"node_id", formatNodeID(nodeID),
		"task_id", taskID,
		"kind", kind,
	}
	return append(attrs, extra...)
}

func formatNodeID(nodeID int64) string {
	if nodeID > 0 {
		return fmt.Sprintf("%d", nodeID)
	}
	return "-"
}

// InfoTask logs an INFO line with task context and trace from ctx.
func InfoTask(ctx context.Context, msg string, nodeID int64, taskID, kind string, extra ...any) {
	slog.InfoContext(ctx, msg, TaskAttrs(nodeID, taskID, kind, extra...)...)
}

// WarnTask logs a WARN line with task context and trace from ctx.
func WarnTask(ctx context.Context, msg string, nodeID int64, taskID, kind string, extra ...any) {
	slog.WarnContext(ctx, msg, TaskAttrs(nodeID, taskID, kind, extra...)...)
}

// ErrorTask logs an ERROR line with task context and trace from ctx.
func ErrorTask(ctx context.Context, msg string, nodeID int64, taskID, kind string, extra ...any) {
	slog.ErrorContext(ctx, msg, TaskAttrs(nodeID, taskID, kind, extra...)...)
}

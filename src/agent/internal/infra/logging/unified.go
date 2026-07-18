package logging

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

type ctxKey string

const (
	traceIDKey ctxKey = "trace_id"
	userIDKey  ctxKey = "user_id"
)

const serviceName = "agent-go"

var (
	defaultOrgKey string
	hostPID       string
)

// WithTraceID attaches a trace id to ctx for unified log lines.
func WithTraceID(ctx context.Context, traceID string) context.Context {
	if strings.TrimSpace(traceID) == "" {
		return ctx
	}
	return context.WithValue(ctx, traceIDKey, strings.TrimSpace(traceID))
}

// WithUserID attaches a user id to ctx for unified log lines.
func WithUserID(ctx context.Context, userID string) context.Context {
	if strings.TrimSpace(userID) == "" {
		return ctx
	}
	return context.WithValue(ctx, userIDKey, strings.TrimSpace(userID))
}

func traceIDFrom(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if v, ok := ctx.Value(traceIDKey).(string); ok {
		return v
	}
	return ""
}

func userIDFrom(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if v, ok := ctx.Value(userIDKey).(string); ok {
		return v
	}
	return ""
}

func formatTraceID(raw string) string {
	id := strings.TrimSpace(raw)
	if id == "" {
		return "-"
	}
	if strings.HasPrefix(id, "t-") {
		return id
	}
	return "t-" + id
}

func formatOrgUser(orgKey, userID string) string {
	orgPart := "-"
	if strings.TrimSpace(orgKey) != "" {
		orgPart = "org-" + strings.TrimSpace(orgKey)
	}
	userPart := "-"
	if strings.TrimSpace(userID) != "" {
		userPart = "u-" + strings.TrimSpace(userID)
	}
	return orgPart + "/" + userPart
}

func formatTimestamp(t time.Time) string {
	t = t.UTC()
	return fmt.Sprintf("%s.%03dZ", t.Format("2006-01-02T15:04:05"), t.Nanosecond()/1e6)
}

func sourceLocation(pc uintptr) (string, int) {
	if pc == 0 {
		return "unknown", 0
	}
	frames := runtime.CallersFrames([]uintptr{pc})
	frame, _ := frames.Next()
	return filepath.Base(frame.File), frame.Line
}

func buildMessage(msg string, attrs []slog.Attr) string {
	if len(attrs) == 0 {
		return msg
	}
	payload := attrsToMap(attrs)
	raw, err := json.Marshal(payload)
	if err != nil {
		return msg
	}
	if strings.TrimSpace(msg) == "" {
		return string(raw)
	}
	return msg + ": " + string(raw)
}

func attrsToMap(attrs []slog.Attr) map[string]any {
	out := make(map[string]any, len(attrs))
	for _, attr := range attrs {
		out[attr.Key] = attr.Value.Any()
	}
	return out
}

type unifiedHandler struct {
	opts slog.HandlerOptions
	w    io.Writer
	mu   sync.Mutex
}

func newUnifiedHandler(w io.Writer, opts *slog.HandlerOptions) *unifiedHandler {
	if opts == nil {
		opts = &slog.HandlerOptions{}
	}
	return &unifiedHandler{opts: *opts, w: w}
}

func (h *unifiedHandler) Enabled(_ context.Context, level slog.Level) bool {
	minLevel := slog.LevelInfo
	if h.opts.Level != nil {
		minLevel = h.opts.Level.Level()
	}
	return level >= minLevel
}

func (h *unifiedHandler) Handle(ctx context.Context, r slog.Record) error {
	file, line := sourceLocation(r.PC)
	level := strings.ToUpper(r.Level.String())
	traceID := formatTraceID(traceIDFrom(ctx))
	orgUser := formatOrgUser(defaultOrgKey, userIDFrom(ctx))

	attrs := make([]slog.Attr, 0, r.NumAttrs())
	r.Attrs(func(attr slog.Attr) bool {
		attrs = append(attrs, attr)
		return true
	})

	lineText := fmt.Sprintf(
		"[%s] [%s] [%s] [%s] [%s] [%s(%s:%d)] - %s\n",
		formatTimestamp(r.Time),
		level,
		hostPID,
		traceID,
		orgUser,
		serviceName,
		file,
		line,
		buildMessage(r.Message, attrs),
	)

	h.mu.Lock()
	defer h.mu.Unlock()
	_, err := h.w.Write([]byte(lineText))
	return err
}

func (h *unifiedHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	// Attrs are folded into the message body by Handle; no persistent attrs needed.
	return h
}

func (h *unifiedHandler) WithGroup(_ string) slog.Handler {
	return h
}

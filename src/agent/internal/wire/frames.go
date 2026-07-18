package wire

// Downlink is a normalized control-plane → Agent frame.
type Downlink struct {
	Type Type

	// TaskCommand is set when Type == TypeTaskCommand.
	TaskCommand *TaskCommand
	// TaskCancel is set when Type == TypeTaskCancel.
	TaskCancel *TaskCancel
}

// TaskCommand is the task.command payload from the control plane.
type TaskCommand struct {
	TaskID          string
	Kind            string
	NodeID          int64
	Payload         map[string]any
	CorrelationType string
	CorrelationID   string
	TraceID         string
}

// TaskCancel requests cancellation of a running task.
type TaskCancel struct {
	TaskID string
	NodeID int64
}

// JobID returns the best-effort job correlation id from a task.command frame.
func (c *TaskCommand) JobID() string {
	if c == nil {
		return ""
	}
	if c.CorrelationID != "" {
		return c.CorrelationID
	}
	return c.CorrelationType
}

// --- Uplink frames (Agent → control plane) ---

// Heartbeat is the periodic liveness frame (optional payload carries host inventory).
type Heartbeat struct {
	Type    Type           `json:"type"`
	Payload map[string]any `json:"payload,omitempty"`
}

// TaskProgress renews the control-plane task watchdog.
type TaskProgress struct {
	Type     Type           `json:"type"`
	TaskID   string         `json:"task_id"`
	Progress map[string]any `json:"progress"`
}

// TaskAlive is a lightweight watchdog renewal during long work.
type TaskAlive struct {
	Type   Type   `json:"type"`
	TaskID string `json:"task_id"`
}

// TaskResult completes a runtime task.
type TaskResult struct {
	Type   Type           `json:"type"`
	TaskID string         `json:"task_id"`
	Status string         `json:"status"`
	Result map[string]any `json:"result,omitempty"`
	Error  string         `json:"error,omitempty"`
}

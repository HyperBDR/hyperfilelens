package engine

// Source identifies who initiated a command.
type Source string

const (
	SourceWebSocket Source = "websocket"
	SourceCLI       Source = "cli"
)

// Command is the unified in-process request for backup, browse, and maintenance work.
type Command struct {
	ID        string
	JobID     string
	Kind      string
	Payload   map[string]any
	Source    Source
}

// Result is the terminal outcome of a command execution.
type Result struct {
	Status string
	Result map[string]any
	Error  string
}

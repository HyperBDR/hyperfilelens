package wire

import "time"

// Type is the top-level JSON "type" field on every WebSocket text frame.
type Type string

const (
	TypeHeartbeat     Type = "heartbeat"
	TypeTaskCommand   Type = "task.command"
	TypeTaskCancel    Type = "task.cancel"
	TypeTaskProgress  Type = "task.progress"
	TypeTaskAlive     Type = "task.alive"
	TypeTaskResult    Type = "task.result"
	TypeTaskResultAck Type = "task.result.ack"
)

// TaskResultAckSubprotocol enables durable task.result acknowledgement.
const TaskResultAckSubprotocol = "hfl.task-result-ack.v1"

// Task lifecycle uplink intervals (Agent → control plane).
const (
	TaskProgressInterval = 3 * time.Second
	TaskAliveInterval    = 5 * time.Second
	HeartbeatInterval    = 30 * time.Second
)

func (t Type) String() string { return string(t) }

func parseType(raw string) (Type, bool) {
	switch Type(raw) {
	case TypeHeartbeat, TypeTaskCommand, TypeTaskCancel, TypeTaskProgress, TypeTaskAlive, TypeTaskResult, TypeTaskResultAck:
		return Type(raw), true
	default:
		return "", false
	}
}

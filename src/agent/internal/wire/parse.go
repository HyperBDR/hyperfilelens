package wire

import (
	"encoding/json"
	"strings"
)

// LoadsJSON parses a text frame into a generic map (returns nil on invalid JSON).
func LoadsJSON(text string) map[string]any {
	var data map[string]any
	if err := json.Unmarshal([]byte(text), &data); err != nil {
		return nil
	}
	return data
}

// DumpsWire serializes a wire message to JSON text.
func DumpsWire(message any) ([]byte, error) {
	return json.Marshal(message)
}

// ParseDownlink unmarshals a control-plane → Agent text frame.
func ParseDownlink(raw []byte) (Downlink, error) {
	var body map[string]json.RawMessage
	if err := json.Unmarshal(raw, &body); err != nil {
		return Downlink{}, err
	}

	msgType, ok := parseType(strings.ToLower(strings.TrimSpace(rawString(body["type"]))))
	if !ok {
		return Downlink{Type: Type(rawString(body["type"]))}, nil
	}

	switch msgType {
	case TypeTaskCommand:
		cmd := &TaskCommand{
			TaskID:          firstNonEmpty(rawString(body["task_id"]), rawString(body["delivery_id"])),
			Kind:            rawString(body["kind"]),
			CorrelationType: rawString(body["correlation_type"]),
			CorrelationID:   rawString(body["correlation_id"]),
			TraceID:         firstNonEmpty(rawString(body["trace_id"]), rawString(body["correlation_id"])),
		}
		if v := body["node_id"]; len(v) > 0 {
			var nodeID int64
			_ = json.Unmarshal(v, &nodeID)
			cmd.NodeID = nodeID
		}
		if v := body["payload"]; len(v) > 0 {
			_ = json.Unmarshal(v, &cmd.Payload)
		}
		return Downlink{Type: msgType, TaskCommand: cmd}, nil

	case TypeTaskCancel:
		cancel := &TaskCancel{TaskID: rawString(body["task_id"])}
		if v := body["node_id"]; len(v) > 0 {
			var nodeID int64
			_ = json.Unmarshal(v, &nodeID)
			cancel.NodeID = nodeID
		}
		return Downlink{Type: msgType, TaskCancel: cancel}, nil

	default:
		return Downlink{Type: msgType}, nil
	}
}

func rawString(v json.RawMessage) string {
	if len(v) == 0 {
		return ""
	}
	var s string
	if err := json.Unmarshal(v, &s); err == nil {
		return strings.TrimSpace(s)
	}
	return ""
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v)
		}
	}
	return ""
}

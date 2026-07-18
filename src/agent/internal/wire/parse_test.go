package wire

import (
	"testing"
)

func TestParseDownlinkTaskCommand(t *testing.T) {
	raw := []byte(`{
		"type": "task.command",
		"task_id": "abc-123",
		"kind": "backup",
		"node_id": 42,
		"correlation_id": "job-9",
		"payload": {"path": "/data"}
	}`)
	dl, err := ParseDownlink(raw)
	if err != nil {
		t.Fatal(err)
	}
	if dl.Type != TypeTaskCommand {
		t.Fatalf("type = %q", dl.Type)
	}
	if dl.TaskCommand == nil {
		t.Fatal("nil TaskCommand")
	}
	cmd := dl.TaskCommand
	if cmd.TaskID != "abc-123" || cmd.Kind != "backup" || cmd.NodeID != 42 {
		t.Fatalf("cmd = %+v", cmd)
	}
	if cmd.JobID() != "job-9" {
		t.Fatalf("job_id = %q", cmd.JobID())
	}
	if cmd.Payload["path"] != "/data" {
		t.Fatalf("payload = %v", cmd.Payload)
	}
}

func TestParseDownlinkTaskCancel(t *testing.T) {
	raw := []byte(`{"type":"task.cancel","task_id":"x1","node_id":1}`)
	dl, err := ParseDownlink(raw)
	if err != nil {
		t.Fatal(err)
	}
	if dl.Type != TypeTaskCancel || dl.TaskCancel == nil || dl.TaskCancel.TaskID != "x1" {
		t.Fatalf("dl = %+v", dl)
	}
}

func TestUplinkFrames(t *testing.T) {
	hb := NewHeartbeat()
	if hb.Type != TypeHeartbeat {
		t.Fatalf("heartbeat type = %q", hb.Type)
	}
	prog := NewTaskProgress("t1", map[string]any{"phase": "running"})
	if prog.TaskID != "t1" || prog.Type != TypeTaskProgress {
		t.Fatalf("progress = %+v", prog)
	}
	res := NewTaskResult("t1", "success", map[string]any{"ok": true}, "")
	if res.Status != "success" || res.Type != TypeTaskResult {
		t.Fatalf("result = %+v", res)
	}
}

func TestDumpsWire(t *testing.T) {
	b, err := DumpsWire(NewTaskAlive("tid"))
	if err != nil {
		t.Fatal(err)
	}
	if string(b) != `{"type":"task.alive","task_id":"tid"}` {
		t.Fatalf("json = %s", b)
	}
}

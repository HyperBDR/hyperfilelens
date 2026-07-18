package engine

import (
	"context"
	"log/slog"

	"hyperfilelens/agent/internal/service/nas"
)

func logNasTask(ctx context.Context, event string, taskID string, spec nas.Spec, extra ...any) {
	args := append([]any{
		"event", event,
		"protocol", spec.Protocol,
		"server", spec.Server,
		"mount_point", spec.MountPoint,
		"resource_id", spec.ResourceID,
	}, extra...)
	if taskID != "" {
		args = append(args, "task_id", taskID)
	}
	slog.InfoContext(ctx, "nas task", args...)
}

func parseNASSpec(raw any) (nas.Spec, bool, error) {
	data, ok := raw.(map[string]any)
	if !ok || len(data) == 0 {
		return nas.Spec{}, false, nil
	}
	spec, err := nas.ParseSpec(data)
	if err != nil {
		return nas.Spec{}, false, err
	}
	spec.MountPoint = nas.ResolvedMountPoint(spec.MountPoint)
	return spec, true, nil
}

func nasResult(spec nas.Spec, info nas.SpaceInfo) map[string]any {
	return map[string]any{
		"mount_point":  spec.MountPoint,
		"mount_status": "mounted",
		"protocol":     spec.Protocol,
		"server":       spec.Server,
		"space_info": map[string]any{
			"total_bytes": info.TotalBytes,
			"used_bytes":  info.UsedBytes,
			"free_bytes":  info.FreeBytes,
		},
	}
}

func (e *Engine) ensureNASMounted(ctx context.Context, p Payload) error {
	spec, ok, err := parseNASSpec(p.Extra["nas"])
	if err != nil {
		return err
	}
	if !ok {
		return nil
	}
	return nas.NewService().EnsureMounted(ctx, spec)
}

func (e *Engine) runNasMount(ctx context.Context, p Payload) (string, map[string]any, string) {
	spec, ok, err := parseNASSpec(p.Extra["nas"])
	if err != nil {
		return "failed", nil, err.Error()
	}
	if !ok {
		if _, hasRaw := p.Extra["nas"]; hasRaw {
			return "failed", nil, "invalid nas payload"
		}
		spec, err = nas.ParseSpec(p.Extra)
		if err != nil {
			return "failed", nil, err.Error()
		}
	}
	logNasTask(ctx, "mount_start", "", spec)
	info, err := nas.NewService().Mount(ctx, spec)
	if err != nil {
		logNasTask(ctx, "mount_failed", "", spec, "err", err.Error())
		return "failed", nil, err.Error()
	}
	logNasTask(ctx, "mount_ok", "", spec, "total_bytes", info.TotalBytes)
	return "success", nasResult(spec, info), ""
}

func (e *Engine) runNasUnmount(ctx context.Context, p Payload) (string, map[string]any, string) {
	mountPoint := stringValue(p.Extra["mount_point"])
	if mountPoint == "" {
		if spec, ok, err := parseNASSpec(p.Extra["nas"]); err != nil {
			return "failed", nil, err.Error()
		} else if ok {
			mountPoint = spec.MountPoint
		}
	}
	if mountPoint == "" {
		spec, err := nas.ParseSpec(p.Extra)
		if err != nil {
			return "failed", nil, err.Error()
		}
		mountPoint = spec.MountPoint
	}
	if mountPoint == "" {
		return "failed", nil, "mount_point is required"
	}
	logNasTask(ctx, "unmount_start", "", nas.Spec{MountPoint: mountPoint}, "mount_point", mountPoint)
	if err := nas.NewService().Unmount(ctx, mountPoint); err != nil {
		logNasTask(ctx, "unmount_failed", "", nas.Spec{MountPoint: mountPoint}, "err", err.Error())
		return "failed", nil, err.Error()
	}
	logNasTask(ctx, "unmount_ok", "", nas.Spec{MountPoint: mountPoint})
	return "success", map[string]any{
		"mount_point":  mountPoint,
		"mount_status": "unmounted",
	}, ""
}

func (e *Engine) runNasTest(ctx context.Context, p Payload) (string, map[string]any, string) {
	spec, ok, err := parseNASSpec(p.Extra["nas"])
	if err != nil {
		return "failed", nil, err.Error()
	}
	if !ok {
		spec, err = nas.ParseSpec(p.Extra)
		if err != nil {
			return "failed", nil, err.Error()
		}
	}
	logNasTask(ctx, "test_start", "", spec)
	info, err := nas.NewService().Test(ctx, spec)
	if err != nil {
		logNasTask(ctx, "test_failed", "", spec, "err", err.Error())
		return "failed", map[string]any{
			"storage_type": "nas",
			"protocol":     spec.Protocol,
			"server":       spec.Server,
		}, err.Error()
	}
	result := nasResult(spec, info)
	result["storage_type"] = "nas"
	logNasTask(ctx, "test_ok", "", spec, "total_bytes", info.TotalBytes)
	return "success", result, ""
}

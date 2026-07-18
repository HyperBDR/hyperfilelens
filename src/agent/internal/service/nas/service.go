package nas

import (
	"context"
	"fmt"

	"hyperfilelens/agent/internal/platform/disk"
)

// SpaceInfo describes filesystem usage for a mounted NAS path.
type SpaceInfo struct {
	TotalBytes uint64
	UsedBytes  uint64
	FreeBytes  uint64
}

// Service mounts and validates NAS shares on the local host.
type Service struct{}

func NewService() *Service {
	return &Service{}
}

// EnsureMounted mounts the NAS share when the mount point is not active yet.
func (s *Service) EnsureMounted(ctx context.Context, spec Spec) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	spec.MountPoint = ResolvedMountPoint(spec.MountPoint)
	if spec.MountPoint == "" {
		return fmt.Errorf("invalid mount_point")
	}
	if isMounted(spec.MountPoint) {
		return nil
	}
	_, err := s.Mount(ctx, spec)
	return err
}

// Mount creates the mount point and mounts the NAS share.
func (s *Service) Mount(ctx context.Context, spec Spec) (SpaceInfo, error) {
	if err := ctx.Err(); err != nil {
		return SpaceInfo{}, err
	}
	spec.MountPoint = ResolvedMountPoint(spec.MountPoint)
	if spec.MountPoint == "" {
		return SpaceInfo{}, fmt.Errorf("invalid mount_point")
	}
	if err := mountShare(ctx, spec); err != nil {
		return SpaceInfo{}, err
	}
	info, err := s.spaceInfo(spec.MountPoint)
	if err != nil {
		return SpaceInfo{}, fmt.Errorf("mounted at %s but failed to read space info: %w", spec.MountPoint, err)
	}
	return info, nil
}

// Unmount removes the NAS mount from the local host.
func (s *Service) Unmount(ctx context.Context, mountPoint string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	mountPoint = ResolvedMountPoint(mountPoint)
	if mountPoint == "" {
		return fmt.Errorf("invalid mount_point")
	}
	if !isMounted(mountPoint) {
		return nil
	}
	return unmountShare(ctx, mountPoint)
}

// Test mounts the share when needed and returns space information.
func (s *Service) Test(ctx context.Context, spec Spec) (SpaceInfo, error) {
	return s.Mount(ctx, spec)
}

func (s *Service) spaceInfo(path string) (SpaceInfo, error) {
	total, used, free, err := disk.Usage(path)
	if err != nil {
		return SpaceInfo{}, err
	}
	return SpaceInfo{
		TotalBytes: total,
		UsedBytes:  used,
		FreeBytes:  free,
	}, nil
}

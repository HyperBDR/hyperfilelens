"""Source resource domain constants."""


class Availability:
    ONLINE = "online"
    OFFLINE = "offline"

    CHOICES = (
        (ONLINE, "Online"),
        (OFFLINE, "Offline"),
    )


class ResourceType:
    NAS = "nas"
    NFS = "nfs"
    CIFS = "cifs"
    S3 = "s3"
    LOCAL = "local"

    CHOICES = (
        (NAS, "NAS"),
        (NFS, "NFS"),
        (CIFS, "CIFS/SMB"),
        (S3, "Object Storage"),
        (LOCAL, "Local Filesystem"),
    )

    REQUIRES_MOUNT = {NAS, NFS, CIFS}


class MountStatus:
    UNMOUNTED = "unmounted"
    MOUNTED = "mounted"
    ERROR = "error"

    CHOICES = (
        (UNMOUNTED, "Unmounted"),
        (MOUNTED, "Mounted"),
        (ERROR, "Mount Error"),
    )


class ConnectionTestStatus:
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    CHOICES = (
        (IDLE, "Idle"),
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
    )

    ACTIVE = frozenset({PENDING, RUNNING})


class ResourceStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    REMOVING = "removing"
    REMOVE_FAILED = "remove_failed"
    REMOVED = "removed"

    CHOICES = (
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
        (ERROR, "Error"),
        (REMOVING, "Removing"),
        (REMOVE_FAILED, "Remove failed"),
        (REMOVED, "Removed"),
    )


class SelectableSourceKind:
    AGENT = "agent"
    NAS = "nas"

    CHOICES = (
        (AGENT, "Agent"),
        (NAS, "NAS"),
    )


class PipelineStep:
    """Protection wizard steps for real backup-selectable sources."""

    SOURCE_POOL = 1
    CONFIG = 2
    READY = 3

    CHOICES = (
        (SOURCE_POOL, "Backup source pool"),
        (CONFIG, "Backup configuration"),
        (READY, "Ready to run backup"),
    )

    VALID = frozenset({SOURCE_POOL, CONFIG, READY})

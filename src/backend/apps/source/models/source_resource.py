"""Source resource models — backup data origins (NAS/NFS/CIFS/S3/local)."""

from django.conf import settings
from django.db import models

from apps.node import agent_paths
from apps.node.models.base import OrganizationScopedModel
from apps.source.constants import MountStatus, ResourceStatus, ResourceType


class SourceResource(OrganizationScopedModel):
    """Organization-scoped backup source (aligned with xxz SourceResource)."""

    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="source_resources",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.CHOICES,
        default=ResourceType.NFS,
        db_index=True,
    )
    config = models.JSONField(default=dict, blank=True)
    credentials = models.JSONField(default=dict, blank=True)

    bound_node = models.ForeignKey(
        "node.Node",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_resources",
    )

    mount_status = models.CharField(
        max_length=20,
        choices=MountStatus.CHOICES,
        default=MountStatus.UNMOUNTED,
    )
    mount_point = models.CharField(max_length=512, blank=True, default="")
    mount_error = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=ResourceStatus.CHOICES,
        default=ResourceStatus.ACTIVE,
        db_index=True,
    )
    status_message = models.TextField(blank=True, default="")

    last_connection_test = models.DateTimeField(null=True, blank=True)
    connection_test_result = models.TextField(blank=True, default="")

    total_size = models.BigIntegerField(default=0)
    used_size = models.BigIntegerField(default=0)
    free_size = models.BigIntegerField(default=0)
    file_count = models.BigIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_source_resources",
    )

    class Meta:
        db_table = "source_resource"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_source_resource_org_name",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "resource_type"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["bound_node"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.resource_type})"

    @property
    def requires_mount(self) -> bool:
        return self.resource_type in ResourceType.REQUIRES_MOUNT

    def effective_mount_point(self) -> str:
        config_path = str((self.config or {}).get("path") or "").strip()
        if config_path:
            try:
                return agent_paths.require_agent_mount_path(config_path)
            except ValueError:
                pass
        stored = str(self.mount_point or "").strip()
        if stored:
            try:
                return agent_paths.require_agent_mount_path(stored)
            except ValueError:
                pass
        return agent_paths.source_mount_point(self.id)

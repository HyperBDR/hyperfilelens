"""Node registry model."""

from django.db import models

from .base import NodeRole, OrganizationScopedModel


class Node(OrganizationScopedModel):
    """Registered Agent endpoint (agent, proxy, or gateway)."""

    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    Role = NodeRole

    id = models.BigAutoField(primary_key=True)

    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=Role.choices)
    version = models.CharField(max_length=50, blank=True, default="")
    os_name = models.CharField(max_length=80, blank=True, default="")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OFFLINE,
        db_index=True,
    )
    last_seen_at = models.DateTimeField(blank=True, null=True, db_index=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Agent-reported extension data (labels, env, install hints, etc.)."
        ),
    )

    class Meta:
        db_table = "node_nodes"
        ordering = ["organization_id", "name", "id"]
        indexes = [
            models.Index(
                fields=["organization", "role", "status"],
                name="node_nd_org_role_st_idx",
            ),
            models.Index(
                fields=["organization", "last_seen_at"],
                name="node_nd_org_seen_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"

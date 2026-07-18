"""Time-series samples for control-plane host monitoring."""

import uuid

from django.db import models


class SystemMetric(models.Model):
    """Host resource snapshot (CPU, memory, disk, network) for the System Monitor page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        "monitor.DeploymentHost",
        on_delete=models.CASCADE,
        related_name="metrics",
        null=True,
        blank=True,
        db_index=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    cpu = models.JSONField(default=dict, blank=True)
    memory = models.JSONField(default=dict, blank=True)
    swap = models.JSONField(default=dict, blank=True)
    disks = models.JSONField(default=list, blank=True)
    disk_io = models.JSONField(default=list, blank=True)
    networks = models.JSONField(default=list, blank=True)
    load_average = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "monitor_system_metrics"
        ordering = ["-timestamp"]
        verbose_name = "System metric"
        verbose_name_plural = "System metrics"

    def __str__(self) -> str:
        return str(self.timestamp)

"""Registered control-plane deployment hosts sharing one database."""

import uuid

from django.db import models


class DeploymentHost(models.Model):
    """A physical or virtual host running the control-plane application."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    platform = models.CharField(max_length=255, blank=True, default="")
    python_version = models.CharField(max_length=64, blank=True, default="")
    app_version = models.CharField(max_length=64, blank=True, default="")
    boot_time = models.FloatField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monitor_deployment_hosts"
        ordering = ["-last_seen_at", "hostname"]
        verbose_name = "Deployment host"
        verbose_name_plural = "Deployment hosts"

    def __str__(self) -> str:
        return self.name or self.hostname

from django.contrib import admin

from apps.monitor.models import DeploymentHost, ResourceMetric, SystemMetric


@admin.register(DeploymentHost)
class DeploymentHostAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "platform", "app_version", "last_seen_at")
    ordering = ("-last_seen_at",)
    readonly_fields = ("created_at", "last_seen_at")


@admin.register(SystemMetric)
class SystemMetricAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "host", "id")
    ordering = ("-timestamp",)
    readonly_fields = (
        "timestamp",
        "cpu",
        "memory",
        "swap",
        "disks",
        "disk_io",
        "networks",
        "load_average",
        "metadata",
    )


@admin.register(ResourceMetric)
class ResourceMetricAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "organization", "resource_type", "resource_id", "source")
    list_filter = ("resource_type", "source")
    ordering = ("-timestamp",)

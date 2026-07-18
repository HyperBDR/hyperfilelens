"""Shared constants for the alert center."""

from django.db import models


class AlertType(models.TextChoices):
    METRIC = "metric", "Metric Alert"
    AVAILABILITY = "availability", "Availability Alert"
    TASK = "task", "Task Alert"
    EVENT = "event", "Event Alert"
    SYSTEM = "system", "System Alert"


class AlertSeverity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    WARNING = "warning", "Warning"
    INFO = "info", "Info"


class AlertStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    FIRING = "firing", "Firing"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    RESOLVED = "resolved", "Resolved"


class ResourceType(models.TextChoices):
    SYSTEM = "system", "System"
    SYNC_PROXY = "sync_proxy", "Sync Proxy"
    GATEWAY = "gateway", "Gateway"
    AGENT_PROXY = "agent_proxy", "Agent Proxy"
    BACKUP_REPOSITORY = "backup_repository", "Backup Repository"
    SOURCE_RESOURCE = "source_resource", "Source Resource"
    TARGET_STORAGE = "target_storage", "Target Storage"
    TASK = "task", "Task"
    SYSTEM_SERVICE = "system_service", "System Service"
    LICENSE = "license", "License"
    USER = "user", "User"


class PolicyScope(models.TextChoices):
    ALL = "all", "All"
    SELECTED = "selected", "Selected"


class NotificationLogStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class NotificationLogType(models.TextChoices):
    FIRING = "firing", "Firing"
    RESOLVED = "resolved", "Resolved"


METRICS_BY_RESOURCE_TYPE = {
    ResourceType.SYSTEM: [
        "cpu_usage",
        "memory_usage",
        "swap_usage",
        "disk_usage",
        "disk_read_bytes",
        "disk_write_bytes",
        "network_rx",
        "network_tx",
        "load_1m",
        "load_5m",
        "load_15m",
    ],
    ResourceType.SYNC_PROXY: [
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        "network_rx",
        "network_tx",
    ],
    ResourceType.GATEWAY: [
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        "network_rx",
        "network_tx",
    ],
    ResourceType.AGENT_PROXY: [
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        "network_rx",
        "network_tx",
    ],
    ResourceType.BACKUP_REPOSITORY: ["capacity_usage", "used_size", "free_size"],
    ResourceType.SOURCE_RESOURCE: ["capacity_usage", "data_size", "file_count"],
    ResourceType.TARGET_STORAGE: ["capacity_usage", "used_size", "free_size"],
}

AVAILABILITY_CHECK_TYPES = ["heartbeat", "connection", "api_health"]
TASK_TYPES = ["backup", "restore", "repository_operation"]
TASK_EVENT_TYPES = ["task_failed", "task_timeout", "retry_exceeded", "partial_success"]
EVENT_CATEGORIES = ["user", "license", "repository", "configuration", "security"]
EVENT_TYPES = {
    "user": [
        "user_created",
        "user_deleted",
        "user_disabled",
        "user_enabled",
        "password_changed",
        "user_role_changed",
        "login_success",
        "login_failed",
        "logout",
    ],
    "license": [
        "license_added",
        "license_updated",
        "license_expired",
        "license_near_expiration",
        "license_capacity_exceeded",
    ],
    "repository": [
        "repository_created",
        "repository_deleted",
        "repository_updated",
        "repository_unreachable",
        "repository_readonly",
        "repository_capacity_low",
    ],
    "configuration": [
        "configuration_changed",
        "notification_channel_changed",
        "alert_policy_changed",
        "repository_config_changed",
        "proxy_config_changed",
    ],
    "security": [
        "multiple_login_failures",
        "api_token_created",
        "api_token_deleted",
        "permission_changed",
    ],
}
SYSTEM_CHECK_TYPES = [
    "api_service_down",
    "database_unreachable",
    "celery_worker_down",
    "scheduler_down",
    "disk_space_low",
    "service_health",
]

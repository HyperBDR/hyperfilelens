"""Subscription / license domain constants."""

# Community default: do not hard-block create paths without a QuotaProvider.
# Plugin builds enforce via SPI regardless; tests may override settings.
QUOTA_ENFORCEMENT_ENABLED = False

LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_REVOKED = "revoked"

CHANGE_INITIAL = "initial"
CHANGE_RENEWAL = "renewal"
CHANGE_UPGRADE = "upgrade"
CHANGE_DOWNGRADE = "downgrade"
CHANGE_REVOKED = "revoked"

UNLIMITED = -1

# Canonical org-level quota keys (EffectiveQuota / UI / enforcement).
# max_workloads (design primary meter) maps to protected sources for now.
QUOTA_KEYS = (
    "max_source_hosts",
    "max_source_nas",
    "max_protected_sources",
    "max_proxies",
    "max_gateways",
    "max_object_storage",
    "max_target_nas",
    "max_standalone_disk",
    "max_storage_gb",
    "max_users",
    "ai_requests",
    "gateway_select_max_files",
    "gateway_select_max_bytes",
)

QUOTA_UNITS: dict[str, str] = {
    "max_storage_gb": "gb",
    "gateway_select_max_bytes": "bytes",
    "ai_requests": "count",
}

# Map quota key -> collect_usage_stats() field. None = policy-only (no lifetime used).
USAGE_KEY_BY_QUOTA: dict[str, str | None] = {
    "max_source_hosts": "agents_count",
    "max_source_nas": "source_nas_count",
    "max_protected_sources": "protected_sources_count",
    "max_proxies": "proxies_count",
    "max_gateways": "gateways_count",
    "max_object_storage": "object_storage_count",
    "max_target_nas": "target_nas_count",
    "max_standalone_disk": "standalone_disk_count",
    "max_storage_gb": "storage_used_gb",
    "max_users": "users_count",
    "ai_requests": "ai_requests_used",
    "gateway_select_max_files": None,
    "gateway_select_max_bytes": None,
}

DEFAULT_LIMITS = {
    "max_organizations": 1,
    "max_users": 50,
    "max_nodes": 20,
    "max_storage_gb": 500,
    "max_gateways": 5,
    "ai_insights_quota": 500,
    "max_tasks": 50,
    "max_alert_policies": 50,
    "max_source_hosts": 100,
    "max_source_nas": 100,
    "max_source_proxies": 100,
    "max_object_storage": 100,
    "max_target_nas": 100,
    "max_standalone_disk": 100,
    "max_protected_sources": 100,
    "gateway_select_max_files": UNLIMITED,
    "gateway_select_max_bytes": UNLIMITED,
}

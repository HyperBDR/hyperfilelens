"""Subscription / license domain constants."""

# Development: do not block API operations based on license quotas.
QUOTA_ENFORCEMENT_ENABLED = False

LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_EXPIRED = "expired"
LICENSE_STATUS_REVOKED = "revoked"

CHANGE_INITIAL = "initial"
CHANGE_RENEWAL = "renewal"
CHANGE_UPGRADE = "upgrade"
CHANGE_DOWNGRADE = "downgrade"
CHANGE_REVOKED = "revoked"

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
}

UNLIMITED = -1

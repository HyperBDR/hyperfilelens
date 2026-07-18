"""Default backup/storage policy (code defaults; overridable via GlobalConfig)."""

CONFIG_KEY_RETENTION = "backup.retention.default"
CONFIG_KEY_FILTERS = "backup.filters.default"

DEFAULT_RETENTION = {
    "type": "gfs",
    "daily": 7,
    "weekly": 4,
    "monthly": 12,
}

DEFAULT_FILTERS = {
    "exclude": ["/tmp", "/var/cache"],
    "include": [],
}

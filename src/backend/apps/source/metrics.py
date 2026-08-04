"""Low-cardinality metrics for Backup Wizard source-query rollout."""

from prometheus_client import Counter, Histogram


BACKUP_SELECTABLE_QUERY_REQUESTS = Counter(
    "hfl_backup_selectable_query_requests_total",
    "Backup-selectable list requests by rollout mode.",
    ("mode",),
)
BACKUP_SELECTABLE_QUERY_DURATION = Histogram(
    "hfl_backup_selectable_query_duration_seconds",
    "Backup-selectable selector duration by engine.",
    ("engine",),
)
BACKUP_SELECTABLE_SHADOW_COMPARISONS = Counter(
    "hfl_backup_selectable_shadow_comparisons_total",
    "Shadow comparison outcomes without tenant or search labels.",
    ("outcome",),
)

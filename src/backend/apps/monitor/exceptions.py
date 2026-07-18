"""Monitor domain exceptions."""


class MonitorError(Exception):
    """Base monitor error."""


class MetricCollectionError(MonitorError):
    """Failed to collect or persist metrics."""

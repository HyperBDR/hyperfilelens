"""Alert domain exceptions."""


class AlertError(Exception):
    """Base alert error."""


class AlertPolicyError(AlertError):
    """Invalid or missing alert policy."""


class AlertEvaluationError(AlertError):
    """Policy evaluation failure."""

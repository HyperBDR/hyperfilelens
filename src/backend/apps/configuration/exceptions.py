"""Configuration domain errors."""


class ConfigurationError(Exception):
    """Base error for configuration center."""


class UnknownConfigKeyError(ConfigurationError):
    """Raised when strict registry validation rejects an unknown key."""


class ConfigValidationError(ConfigurationError):
    """Raised when value does not match declared value_type."""

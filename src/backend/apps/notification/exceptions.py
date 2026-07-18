"""Notification domain exceptions."""


class NotificationError(Exception):
    """Base notification error."""


class ChannelError(NotificationError):
    """Outbound channel failure."""


class ChannelConfigError(ChannelError):
    """Invalid or incomplete channel configuration."""


class RenderError(NotificationError):
    """Template rendering failure."""

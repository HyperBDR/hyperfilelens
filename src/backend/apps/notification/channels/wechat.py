"""WeCom application message webhook."""

from apps.notification.channels.webhook import WebhookChannel


class WeComChannel(WebhookChannel):
    """WeCom uses the same webhook adapter with config.url / webhook_url."""

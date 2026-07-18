"""DingTalk robot webhook (HTTP JSON)."""

from apps.notification.channels.webhook import WebhookChannel


class DingTalkChannel(WebhookChannel):
    """DingTalk uses the same webhook adapter with config.url."""

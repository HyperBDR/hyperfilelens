"""Notification domain constants."""

from django.db import models


class ChannelType(models.TextChoices):
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    WEBHOOK = "webhook", "Webhook"
    DINGTALK = "dingtalk", "DingTalk"
    WECOM = "wecom", "WeCom"


class NotificationLogStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class NotificationLogType(models.TextChoices):
    FIRING = "firing", "Firing"
    RESOLVED = "resolved", "Resolved"

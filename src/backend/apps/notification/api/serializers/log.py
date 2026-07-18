from rest_framework import serializers

from apps.notification.models import NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "organization",
            "channel",
            "alert_record_id",
            "event_type",
            "notification_type",
            "status",
            "error_message",
            "sent_at",
        ]
        read_only_fields = fields

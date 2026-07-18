from django.contrib import admin

from apps.alert.models import AlertPolicy, AlertRecord


@admin.register(AlertPolicy)
class AlertPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "type", "severity", "enabled", "updated_at")
    list_filter = ("type", "severity", "enabled")
    search_fields = ("name",)


@admin.register(AlertRecord)
class AlertRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "severity", "status", "last_triggered_at")
    list_filter = ("status", "severity", "type")
    search_fields = ("title", "resource_name")


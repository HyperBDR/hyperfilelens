from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("organization", "action", "target_type", "target_id", "user", "created_at")
    list_filter = ("organization", "action", "target_type")
    search_fields = ("target_id", "metadata")
    ordering = ("-created_at", "-id")


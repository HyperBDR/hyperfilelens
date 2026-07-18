from django.contrib import admin

from apps.configuration.models import GlobalConfig


class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "scope",
        "tenant_key",
        "category",
        "value_type",
        "is_active",
        "updated_at",
    )
    list_filter = ("scope", "category", "value_type", "is_active")
    search_fields = ("key", "tenant_key", "category")
    ordering = ("category", "key", "scope", "tenant_key")


# Idempotent: autoregister or a prior admin import may register GlobalConfig first.
if admin.site.is_registered(GlobalConfig):
    admin.site.unregister(GlobalConfig)
admin.site.register(GlobalConfig, GlobalConfigAdmin)

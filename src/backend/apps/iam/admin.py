from django.contrib import admin

from apps.iam.models import Membership, Organization, PersonalApiKey


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("key", "name")
    ordering = ("key", "id")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("organization__key", "user__username", "user__email")


@admin.register(PersonalApiKey)
class PersonalApiKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email", "name")

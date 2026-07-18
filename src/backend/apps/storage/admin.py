from django.contrib import admin

from apps.storage.repositories.models import Credential, Repository


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "organization_id", "credential_type", "updated_at")
    list_filter = ("credential_type",)
    search_fields = ("credential_type",)


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("name", "organization_id", "repo_type", "status", "health", "updated_at")
    list_filter = ("repo_type", "status", "health")
    search_fields = ("name", "s3_bucket")

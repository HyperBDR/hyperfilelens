from django.contrib import admin

from apps.storage.repositories.models import Credential, Repository
from apps.storage.provider_catalog.models import (
    StorageProviderOverride,
    StorageProviderRegionValidation,
    StorageProviderValidationRun,
)


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


@admin.register(StorageProviderOverride)
class StorageProviderOverrideAdmin(admin.ModelAdmin):
    list_display = ("provider_id", "schema_version", "checksum", "updated_at")
    readonly_fields = ("checksum", "updated_at")
    search_fields = ("provider_id",)


@admin.register(StorageProviderValidationRun)
class StorageProviderValidationRunAdmin(admin.ModelAdmin):
    list_display = ("id", "provider_id", "status", "updated_at")
    list_filter = ("status",)
    readonly_fields = ("id", "task_id", "created_at", "updated_at")
    search_fields = ("provider_id", "id")


@admin.register(StorageProviderRegionValidation)
class StorageProviderRegionValidationAdmin(admin.ModelAdmin):
    list_display = ("run", "region_id", "status", "current_step", "updated_at")
    list_filter = ("status", "current_step")
    search_fields = (
        "run__provider_id",
        "region_id",
        "region_group",
        "external_endpoint",
        "internal_endpoint",
    )

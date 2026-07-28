from django.db import migrations, models


def _normalize_endpoint(value):
    endpoint = str(value or "").strip()
    lower = endpoint.lower()
    if lower.startswith("https://"):
        endpoint = endpoint[8:]
    elif lower.startswith("http://"):
        endpoint = endpoint[7:]
    return endpoint.strip().rstrip("/").lower().rstrip(".")


def _repository_endpoint_values(repository):
    config = repository.config if isinstance(repository.config, dict) else {}
    legacy = _normalize_endpoint(config.get("endpoint"))
    platform = str(
        getattr(repository, "s3_platform", None) or config.get("s3_platform") or ""
    ).strip().lower()
    if platform == "custom":
        endpoint = legacy or _normalize_endpoint(config.get("external_endpoint"))
        return endpoint, endpoint, "external"

    external = _normalize_endpoint(config.get("external_endpoint")) or legacy
    internal = _normalize_endpoint(config.get("internal_endpoint")) or external
    selected = str(config.get("endpoint_type") or "external").strip().lower()
    if selected != "internal" or not internal or internal == external:
        selected = "external"
    return external, internal, selected


def migrate_repository_endpoints(apps, _schema_editor):
    BackupConfig = apps.get_model("protection", "BackupConfig")
    Repository = apps.get_model("storage", "Repository")
    repositories = {
        repository.id: repository
        for repository in Repository.objects.filter(repo_type="s3")
    }

    for backup_config in BackupConfig.objects.all().iterator():
        repository = repositories.get(backup_config.repository_id)
        endpoint_type = "external"
        if repository is not None:
            _external, _internal, endpoint_type = _repository_endpoint_values(repository)
        backup_config.repository_endpoint_type = endpoint_type
        backup_config.save(update_fields=["repository_endpoint_type"])

    for repository in repositories.values():
        original = repository.config if isinstance(repository.config, dict) else {}
        config = dict(original)
        external, internal, _selected = _repository_endpoint_values(repository)
        if not external:
            raise RuntimeError(f"S3 Repository {repository.id} has no usable Endpoint.")

        platform = str(repository.s3_platform or config.get("s3_platform") or "").strip().lower()
        if platform == "huawei":
            repository.s3_platform = "huaweicloud"
        if config.get("s3_platform") == "huawei":
            config["s3_platform"] = "huaweicloud"

        config["endpoint"] = external
        config.pop("endpoint_type", None)
        config.pop("external_endpoint", None)
        config.pop("internal_endpoint", None)
        if platform != "custom" and internal != external:
            config["external_endpoint"] = external
            config["internal_endpoint"] = internal

        update_fields = []
        if config != original:
            repository.config = config
            update_fields.append("config")
        if str(repository.s3_platform or "") != platform:
            update_fields.append("s3_platform")
        if update_fields:
            repository.save(update_fields=[*update_fields, "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0015_normalize_kopia_snapshot_ids"),
        ("storage", "0011_provider_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupconfig",
            name="repository_endpoint_type",
            field=models.CharField(
                choices=[("external", "External"), ("internal", "Internal")],
                default="external",
                max_length=16,
            ),
        ),
        migrations.RunPython(migrate_repository_endpoints, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="backupconfig",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    repository_endpoint_type__in=["external", "internal"]
                ),
                name="prot_bcfg_repo_endpoint_valid",
            ),
        ),
    ]

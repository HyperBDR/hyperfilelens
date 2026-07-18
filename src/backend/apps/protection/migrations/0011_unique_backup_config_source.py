from django.db import migrations, models
from django.db.models import Count


def fail_on_duplicate_backup_config_sources(apps, schema_editor):
    BackupConfig = apps.get_model("protection", "BackupConfig")
    duplicates = list(
        BackupConfig.objects.values("organization_id", "source_type", "source_ref_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .order_by("organization_id", "source_type", "source_ref_id")
    )
    if not duplicates:
        return

    details = []
    for item in duplicates[:20]:
        ids = list(
            BackupConfig.objects.filter(
                organization_id=item["organization_id"],
                source_type=item["source_type"],
                source_ref_id=item["source_ref_id"],
            )
            .order_by("id")
            .values_list("id", flat=True)
        )
        details.append(
            "org={org} source={source_type}:{source_ref_id} config_ids={ids}".format(
                org=item["organization_id"],
                source_type=item["source_type"],
                source_ref_id=item["source_ref_id"],
                ids=",".join(str(value) for value in ids),
            )
        )

    suffix = ""
    if len(duplicates) > 20:
        suffix = f" (+{len(duplicates) - 20} more)"
    raise RuntimeError(
        "Cannot add one-backup-config-per-source constraint; duplicate backup configs exist: "
        + "; ".join(details)
        + suffix
    )


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0010_backup_directory_progress_sample"),
    ]

    operations = [
        migrations.RunPython(fail_on_duplicate_backup_config_sources, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="backupconfig",
            constraint=models.UniqueConstraint(
                fields=["organization_id", "source_type", "source_ref_id"],
                name="uniq_prot_bcfg_org_source",
            ),
        ),
    ]

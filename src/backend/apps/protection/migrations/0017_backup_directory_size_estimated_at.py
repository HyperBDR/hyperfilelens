from django.db import migrations, models
from django.db.models import F


def preserve_verified_legacy_estimates(apps, _schema_editor):
    BackupConfigDirectory = apps.get_model("protection", "BackupConfigDirectory")
    BackupConfigDirectory.objects.filter(estimated_size_bytes__gt=0).update(
        size_estimated_at=F("updated_at")
    )


class Migration(migrations.Migration):
    dependencies = [("protection", "0016_backup_config_repository_endpoint")]

    operations = [
        migrations.AddField(
            model_name="backupconfigdirectory",
            name="size_estimated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            preserve_verified_legacy_estimates,
            migrations.RunPython.noop,
        ),
    ]

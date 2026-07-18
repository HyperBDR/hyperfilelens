from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0003_snapshot_capacity_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="backupsourcesnapshot",
            name="repository_delta_bytes",
        ),
        migrations.RemoveField(
            model_name="backupsourcesnapshotdirectory",
            name="repository_delta_bytes",
        ),
        migrations.RemoveField(
            model_name="backupsourcesnapshotdirectory",
            name="total_size_bytes",
        ),
    ]

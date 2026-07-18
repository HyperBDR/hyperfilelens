from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0002_snapshot_download_artifact"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupsourcesnapshot",
            name="repository_delta_bytes",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="repository_delta_bytes",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="total_size_bytes",
            field=models.BigIntegerField(default=0),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restore", "0005_restore_execution_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="restorerecorditem",
            name="terminal_projection_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]

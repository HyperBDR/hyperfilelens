from django.db import migrations, models


def promote_connection_status_to_lifecycle(apps, schema_editor):
    del schema_editor
    Node = apps.get_model("node", "Node")
    Node.objects.filter(status__in=("online", "offline")).update(status="active")


class Migration(migrations.Migration):
    dependencies = [("node", "0010_enrollment_sessions_and_credentials")]

    operations = [
        migrations.RunPython(promote_connection_status_to_lifecycle, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="node",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("upgrading", "Upgrading"),
                    ("restarting", "Restarting"),
                    ("verifying", "Verifying"),
                    ("verification_pending", "Verification pending"),
                    ("removing", "Removing"),
                    ("cleaning_up", "Cleaning up"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
    ]

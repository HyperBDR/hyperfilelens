from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("node", "0011_node_lifecycle_status")]

    operations = [
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
                    ("upgrade_failed", "Upgrade Failed"),
                    ("deregistration_failed", "Deregistration Failed"),
                ],
                db_index=True,
                default="active",
                max_length=32,
            ),
        ),
    ]

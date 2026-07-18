from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lens_bridge", "0012_lens_identity_and_gateway_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssessionlink",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("provisioning", "Provisioning"),
                    ("ready", "Ready"),
                    ("failed", "Failed"),
                    ("deleting", "Deleting"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="ready",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="lifecycle_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="lenssessionlink",
            name="sl_session_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
        migrations.AddIndex(
            model_name="lenssessionlink",
            index=models.Index(
                fields=["organization", "lifecycle_status"],
                name="lens_bsess_org_lc_idx",
            ),
        ),
    ]

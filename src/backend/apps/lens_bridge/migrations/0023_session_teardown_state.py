from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0022_workspace_binding"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensknowledgesource",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("ready", "Ready"),
                    ("deleting", "Deleting"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="ready",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="teardown_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="teardown_claim_token",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="teardown_claimed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="teardown_next_retry_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="teardown_state_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_state_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_claim_token",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_claimed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_next_retry_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="teardown_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="teardown_claim_token",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="teardown_claimed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="teardown_next_retry_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="teardown_state_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0024_gateway_default_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensgatewaylink",
            name="lensnode_provision_state_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="lensgatewaylink",
            name="lensnode_provision_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="lensgatewaylink",
            name="lensnode_provision_claim_token",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="lensgatewaylink",
            name="lensnode_provision_claimed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensassistantlink",
            name="lifecycle_owner",
            field=models.CharField(
                choices=[
                    ("manual", "Manual assistant management"),
                    ("chat", "Chat lifecycle"),
                ],
                db_index=True,
                default="manual",
                max_length=16,
            ),
        ),
    ]

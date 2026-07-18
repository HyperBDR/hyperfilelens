import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0017_session_unread_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LensUsageLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("sl_user_id", models.IntegerField(db_index=True)),
                ("sl_run_uuid", models.UUIDField(db_index=True, unique=True)),
                ("sl_session_uuid", models.UUIDField(blank=True, db_index=True, null=True)),
                ("chat_title", models.CharField(blank=True, default="", max_length=160)),
                ("question", models.TextField(blank=True, default="")),
                ("backup_config_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("backup_source_name", models.CharField(blank=True, default="", max_length=255)),
                ("backup_source_snapshot_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("snapshot_created_at", models.DateTimeField(blank=True, null=True)),
                ("source_scopes_json", models.JSONField(blank=True, default=list)),
                ("gateway_selection_mode", models.CharField(blank=True, default="auto", max_length=16)),
                ("gateway_name", models.CharField(blank=True, default="", max_length=160)),
                ("run_status", models.CharField(blank=True, db_index=True, default="queued", max_length=24)),
                ("prompt_tokens", models.BigIntegerField(default=0)),
                ("completion_tokens", models.BigIntegerField(default=0)),
                ("cached_tokens", models.BigIntegerField(default=0)),
                ("reasoning_tokens", models.BigIntegerField(default=0)),
                ("total_tokens", models.BigIntegerField(default=0)),
                ("model_calls", models.PositiveIntegerField(default=0)),
                ("estimated_cost", models.DecimalField(blank=True, decimal_places=8, max_digits=18, null=True)),
                ("cost_currency", models.CharField(blank=True, default="USD", max_length=10)),
                ("call_details_json", models.JSONField(blank=True, default=list)),
                ("run_error", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("hfl_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lens_usage_records", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="iam.organization")),
                ("session_link", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_records", to="lens_bridge.lenssessionlink")),
            ],
            options={
                "db_table": "lens_bridge_usage_ledger",
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="lensusageledger",
            index=models.Index(fields=["organization", "hfl_user", "occurred_at"], name="lens_busg_org_usr_time_idx"),
        ),
        migrations.AddIndex(
            model_name="lensusageledger",
            index=models.Index(fields=["organization", "sl_user_id", "occurred_at"], name="lens_busg_org_slusr_time_idx"),
        ),
    ]

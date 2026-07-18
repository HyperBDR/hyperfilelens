from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0014_gateway_catalog_ownership"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssessionlink",
            name="backup_config_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="backup_source_snapshot_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="source_scopes_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="gateway_link",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="session_links", to="lens_bridge.lensgatewaylink"),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="gateway_selection_mode",
            field=models.CharField(choices=[("auto", "Auto"), ("manual", "Manual")], default="auto", max_length=16),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_phase",
            field=models.CharField(choices=[("queued", "Queued"), ("restoring", "Restoring backup data"), ("creating_knowledge_source", "Creating knowledge source"), ("creating_assistant", "Creating assistant"), ("granting_assistant", "Granting assistant"), ("creating_session", "Creating chat session"), ("ready", "Ready"), ("cleaning_up", "Cleaning up"), ("deleting", "Deleting"), ("deleted", "Deleted")], db_index=True, default="ready", max_length=32),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="provision_detail",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddIndex(
            model_name="lenssessionlink",
            index=models.Index(fields=["organization", "hfl_user", "provision_phase"], name="lens_bsess_org_user_ph_idx"),
        ),
    ]

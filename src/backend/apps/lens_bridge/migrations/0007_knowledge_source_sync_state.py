from django.db import migrations, models


def migrate_legacy_statuses(apps, schema_editor):
    LensKnowledgeSource = apps.get_model("lens_bridge", "LensKnowledgeSource")
    LensKnowledgeSource.objects.filter(
        status__in=("draft", "provisioning", "learning")
    ).update(status="syncing")


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0006_knowledge_source_scopes"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensknowledgesource",
            name="sync_state_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="last_restore_record_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="lensknowledgesource",
            name="status",
            field=models.CharField(
                choices=[
                    ("syncing", "Syncing"),
                    ("ready", "Ready"),
                    ("degraded", "Degraded"),
                    ("error", "Error"),
                    ("paused", "Paused"),
                ],
                db_index=True,
                default="syncing",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_legacy_statuses, migrations.RunPython.noop),
    ]
